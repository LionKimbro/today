"""Core image requests are revisioned and obsolete results cannot restore images."""

from queue import Queue
import unittest

from today import core, machine


class ImagePanelTests(unittest.TestCase):
    def setUp(self):
        machine.initialize_machine_system()
        machine.install_machine({"name": "CORE", "inbox": Queue(), "current-stack": None,
                                 "handlers": {}, "running": False})
        machine.claim_machine("CORE")
        core.visible_panels.clear()
        core.image_jobs.clear()
        core.image_errors.clear()
        core.image_previews.clear()
        core.g["pending-day-id"] = None
        core.g["current-day-id"] = "2026-10-06"
        core.install_panel_snapshot({
            "id": "image-1", "day-id": "2026-10-06", "type": "IMAGE",
            "label": "Image", "text": "", "image-asset": None, "revision": 1,
        })

    def tearDown(self):
        core.visible_panels.clear()
        core.image_jobs.clear()
        core.image_errors.clear()
        core.image_previews.clear()

    def start_import(self):
        effects = core.reduce_event({"type": "IMPORT_IMAGE", "panel-id": "image-1",
                                     "source": {"kind": "clipboard"}})
        return effects[-1]["request-id"]

    def imported(self, request_id):
        return {"type": "IMAGE_IMPORTED", "panel-id": "image-1",
                "day-id": "2026-10-06", "request-id": request_id,
                "image-result": {"status": "ok", "image-asset": "assets/image-" + "a" * 32 + ".png"}}

    def test_import_persists_only_relative_reference_and_clear_waits_for_revision(self):
        effects = core.reduce_event(self.imported(self.start_import()))
        update = effects[-1]
        self.assertEqual(update["type"], "UPDATE_PANEL")
        self.assertEqual(update["base-revision"], 1)
        self.assertNotIn("pixels", update["proposed-panel"])
        self.assertNotIn("image-busy", update["proposed-panel"])
        core.reduce_event({"type": "CLEAR_IMAGE", "panel-id": "image-1"})
        self.assertIsNone(core.visible_panels["image-1"]["image-asset"])
        next_update = core.reduce_event({
            "type": "TEXT_PANEL_UPDATE_ACCEPTED", "panel-id": "image-1",
            "accepted-revision": 2, "save-generation": update["save-generation"],
        })[0]
        self.assertEqual(next_update["base-revision"], 2)
        self.assertIsNone(next_update["proposed-panel"]["image-asset"])
        core.reduce_event({"type": "TEXT_PANEL_UPDATE_ACCEPTED", "panel-id": "image-1",
                           "accepted-revision": 3, "save-generation": next_update["save-generation"]})
        self.assertFalse(core.visible_panels["image-1"]["dirty"])

    def test_clear_and_delete_invalidate_import_before_result_arrives(self):
        for event_type in ("CLEAR_IMAGE", "DELETE_PANEL"):
            with self.subTest(event=event_type):
                token = self.start_import()
                core.reduce_event({"type": event_type, "panel-id": "image-1"})
                self.assertEqual(core.reduce_event(self.imported(token)), [])
                self.assertIsNone(core.visible_panels["image-1"]["image-asset"])

    def test_repeated_import_is_ignored_and_bad_input_is_an_ordinary_result(self):
        token = self.start_import()
        self.assertEqual(core.reduce_event({"type": "IMPORT_IMAGE", "panel-id": "image-1",
                                           "source": {"kind": "clipboard"}}), [])
        error = self.imported(token)
        error["image-result"] = {"status": "error", "error": "Clipboard is empty"}
        self.assertEqual(core.reduce_event(error), [{"type": "RENDER_IMAGE_PANEL", "panel-id": "image-1"}])
        self.assertEqual(core.get_image_panel_rendering("image-1")["image-error"], "Clipboard is empty")
        self.assertFalse(machine.a_thread_died_unexpectedly.is_set())
        self.assertFalse(core.visible_panels["image-1"]["dirty"])

    def test_preview_is_invalidated_by_clear_and_old_day_results_are_ignored(self):
        asset = "assets/image-" + "b" * 32 + ".png"
        core.visible_panels["image-1"]["image-asset"] = asset
        request = {"type": "REQUEST_IMAGE_PREVIEW", "panel-id": "image-1",
                   "image-asset": asset, "width": 200, "height": 100}
        effect = core.reduce_event(request)[0]
        self.assertEqual(core.reduce_event(request), [])
        core.reduce_event({"type": "CLEAR_IMAGE", "panel-id": "image-1"})
        returned = {**effect, "type": "IMAGE_PREVIEW_RECEIVED",
                    "image-result": {"status": "ok", "image-asset": asset,
                                     "width": 2, "height": 1, "pixels": b"12345678",
                                     "request-width": 200, "request-height": 100}}
        self.assertEqual(core.reduce_event(returned), [])
        token = self.start_import()
        wrong_day = self.imported(token)
        wrong_day["day-id"] = "2026-10-07"
        self.assertEqual(core.reduce_event(wrong_day), [])


if __name__ == "__main__":
    unittest.main()
