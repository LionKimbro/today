"""Stroke ownership, deferred commits, and the normal-close acceptance barrier."""

from copy import deepcopy
import unittest

from today import core


class ImageDrawingTests(unittest.TestCase):
    def setUp(self):
        core.visible_panels.clear()
        core.g["shutdown-requested"] = False
        core.g["pending-day-id"] = None
        core.g["current-day-id"] = "2026-10-06"
        self.asset = "assets/image-" + "c" * 32 + ".png"
        self.stroke = {"points": [[0.1, 0.2], [0.8, 0.9]], "color": "#FF3030", "width": 0.01}
        core.install_panel_snapshot({"id": "drawing", "day-id": "2026-10-06", "type": "IMAGE",
                                     "label": "Image", "text": "", "image-asset": self.asset,
                                     "revision": 1})

    def tearDown(self):
        core.visible_panels.clear()
        core.g["shutdown-requested"] = False
        core.g["pending-day-id"] = None

    def add_stroke(self):
        return core.reduce_event({"type": "IMAGE_STROKE_ADDED", "panel-id": "drawing",
                                  "image-asset": self.asset, "stroke": self.stroke})

    def save(self):
        return core.reduce_event({"type": "SAVE_IMAGE_DRAWING", "panel-id": "drawing"})

    def accept(self, update):
        return core.reduce_event({"type": "TEXT_PANEL_UPDATE_ACCEPTED", "panel-id": "drawing",
                                  "accepted-revision": update["base-revision"] + 1,
                                  "save-generation": update["save-generation"]})

    def test_old_panel_defaults_to_empty_strokes_and_edit_does_not_save_immediately(self):
        self.assertEqual(core.visible_panels["drawing"]["image-strokes"], [])
        self.assertEqual(self.add_stroke(), [{"type": "RENDER_IMAGE_PANEL", "panel-id": "drawing"}])
        self.assertTrue(core.visible_panels["drawing"]["dirty"])
        self.stroke["points"][0][0] = 0.5
        self.assertEqual(core.visible_panels["drawing"]["image-strokes"][0]["points"][0][0], 0.1)
        self.assertEqual(self.save()[0]["type"], "UPDATE_PANEL")

    def test_pending_save_is_frozen_and_newer_strokes_keep_their_debounce(self):
        self.add_stroke()
        old = self.save()[0]
        snapshot = deepcopy(old["proposed-panel"])
        self.add_stroke()
        self.assertEqual(old["proposed-panel"], snapshot)
        self.assertEqual(self.accept(old), [])
        self.assertTrue(core.visible_panels["drawing"]["dirty"])
        new = self.save()[0]
        self.assertEqual(new["base-revision"], 2)
        self.assertEqual(len(new["proposed-panel"]["image-strokes"]), 2)
        self.accept(new)
        self.assertFalse(core.visible_panels["drawing"]["dirty"])

    def test_flush_while_save_pending_commits_new_generation_after_acceptance(self):
        self.add_stroke()
        old = self.save()[0]
        self.add_stroke()
        self.assertEqual(self.save(), [])
        new = self.accept(old)[0]
        self.assertEqual(len(new["proposed-panel"]["image-strokes"]), 2)
        self.accept(new)
        self.assertFalse(core.visible_panels["drawing"]["dirty"])

    def test_tab_and_unhost_submit_without_waiting_for_acceptance(self):
        for navigation in ({"type": "SELECT_TAB", "tab-id": "other"},
                           {"type": "UNHOST_PANEL", "position-id": "position"}):
            with self.subTest(navigation=navigation):
                self.add_stroke()
                effects = core.reduce_event(navigation)
                self.assertEqual(effects[0]["type"], "UPDATE_PANEL")
                self.assertEqual(effects[-1], navigation)
                self.accept(effects[0])

    def test_day_navigation_saves_and_uses_existing_dirty_gate(self):
        self.add_stroke()
        effects = core.request_day_navigation("2026-10-07")
        self.assertEqual(len(effects), 1)
        self.assertEqual(self.accept(effects[0]), [{"type": "GET_DAY_LAYOUT", "day-id": "2026-10-07"}])

    def test_normal_close_waits_for_latest_generation_not_first_acknowledgement(self):
        self.add_stroke()
        old = self.save()[0]
        self.add_stroke()
        self.assertEqual(core.reduce_event({"type": "SHUTDOWN"}), [])
        new = self.accept(old)[0]
        self.assertEqual(new["type"], "UPDATE_PANEL")
        self.assertEqual(self.accept(new), [
            {"type": "STOP_CORE"}, {"type": "STOP_MEM"}, {"type": "SHUTDOWN_TK"},
        ])

    def test_close_forces_unsaved_strokes_and_conflict_cannot_report_saved_exit(self):
        self.add_stroke()
        effects = core.reduce_event({"type": "SHUTDOWN"})
        self.assertEqual([effect["type"] for effect in effects], ["UPDATE_PANEL"])
        with self.assertRaisesRegex(RuntimeError, "saved shutdown"):
            core.reduce_event({"type": "PANEL_UPDATE_CONFLICT", "panel-id": "drawing"})

    def test_clear_removes_strokes_and_obsolete_asset_stroke_is_ignored(self):
        self.add_stroke()
        effects = core.reduce_event({"type": "CLEAR_IMAGE", "panel-id": "drawing"})
        self.assertEqual(effects[-1]["proposed-panel"]["image-strokes"], [])
        self.assertEqual(self.add_stroke(), [])


if __name__ == "__main__":
    unittest.main()
