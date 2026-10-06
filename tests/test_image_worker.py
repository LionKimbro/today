"""Image stacks survive Disk round trips, then retire with portable assets."""

from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from PIL import Image

from today import disk, image, machine, mobile_stacks


class ImageWorkerTests(unittest.TestCase):
    def setUp(self):
        machine.initialize_machine_system()
        self.directory = TemporaryDirectory()
        self.original_root = disk.g["data-root"]
        disk.initialize_data_root(self.directory.name)
        for name, handlers in (
            ("CORE", {}),
            ("DISK", {
                "WRITE_IMAGE_ASSET": disk.handle_when_disk_receives_write_image_asset,
                "READ_IMAGE_ASSET": disk.handle_when_disk_receives_read_image_asset,
            }),
        ):
            machine.install_machine({
                "name": name, "inbox": Queue(), "current-stack": None,
                "handlers": handlers, "running": False,
            })
        machine.install_machine_kind("IMAGE", image.HANDLERS)
        machine.start_worker("DISK", disk.run_disk_machine)
        machine.claim_machine("CORE")

    def tearDown(self):
        machine.begin_shutdown()
        for runtime in machine.get_machine_runtimes():
            runtime["inbox"].put(None)
        for runtime in machine.get_machine_runtimes():
            if runtime["thread"]:
                runtime["thread"].join(3)
                self.assertFalse(runtime["thread"].is_alive())
        machine.initialize_machine_system()
        disk.g["data-root"] = self.original_root
        self.directory.cleanup()

    def run_image_request(self, entry, registers):
        mobile_stacks.create_stack()
        mobile_stacks.push_frame({"machine": "CORE", "entry": "RESULT"})
        creation = {"machine": {"new": "IMAGE"}, "entry": entry}
        mobile_stacks.push_frame(creation)
        mobile_stacks.stack()["registers"].update({
            "day-id": "2026-10-06", "panel-id": "panel-1", "request-id": "request-1",
            **registers,
        })
        machine.route_current_stack()
        runtime = machine.machines[creation["machine"]]
        returned = machine.machines["CORE"]["inbox"].get(timeout=3)
        runtime["thread"].join(3)
        self.assertFalse(runtime["thread"].is_alive())
        self.assertEqual(runtime["lifecycle"], "exited")
        self.assertFalse(machine.a_thread_died_unexpectedly.is_set())
        self.assertEqual(returned["frames"], [{"machine": "CORE", "entry": "RESULT"}])
        self.assertNotIn("image-bytes", returned["registers"])
        machine.reap_exited_machines()
        self.assertNotIn(runtime["name"], machine.machines)
        return returned["registers"]["image-result"]

    def test_file_import_preserves_source_and_preview_fits_bounds(self):
        for format_name in ("JPEG", "PNG", "GIF"):
            with self.subTest(format=format_name):
                source = Path(self.directory.name) / "source.data"
                Image.new("RGB", (400, 200), "red").save(source, format=format_name)
                original = source.read_bytes()
                result = self.run_image_request("IMPORT_IMAGE", {
                    "source": {"kind": "file", "path": str(source)},
                })
                self.assertEqual(result["status"], "ok")
                stored = disk.get_image_asset_path("2026-10-06", result["image-asset"])
                self.assertEqual(stored.read_bytes(), original)
                self.assertEqual(source.read_bytes(), original)
                preview = self.run_image_request("LOAD_PREVIEW", {
                    "image-asset": result["image-asset"], "width": 100, "height": 100,
                })
                self.assertEqual((preview["width"], preview["height"]), (100, 50))
                self.assertEqual((preview["request-width"], preview["request-height"]), (100, 100))
                self.assertEqual(len(preview["pixels"]), 100 * 50 * 4)

    def test_clipboard_pixels_are_acquired_on_worker_and_saved_png(self):
        from threading import current_thread, main_thread

        def read_clipboard():
            self.assertIsNot(current_thread(), main_thread())
            return Image.new("RGBA", (9, 7), "blue")

        with patch.object(image.ImageGrab, "grabclipboard", side_effect=read_clipboard):
            result = self.run_image_request("IMPORT_IMAGE", {"source": {"kind": "clipboard"}})
        self.assertTrue(result["image-asset"].endswith(".png"))
        with Image.open(disk.get_image_asset_path("2026-10-06", result["image-asset"])) as saved:
            self.assertEqual(saved.size, (9, 7))

    def test_clipboard_file_and_empty_clipboard(self):
        source = Path(self.directory.name) / "source.png"
        Image.new("RGB", (4, 4)).save(source)
        with patch.object(image.ImageGrab, "grabclipboard", return_value=[str(source)]):
            self.assertEqual(self.run_image_request("IMPORT_IMAGE", {
                "source": {"kind": "clipboard"},
            })["status"], "ok")
        for contents in (None, [], ["one", "two"]):
            with patch.object(image.ImageGrab, "grabclipboard", return_value=contents):
                self.assertEqual(self.run_image_request("IMPORT_IMAGE", {
                    "source": {"kind": "clipboard"},
                })["status"], "error")

    def test_bad_input_and_missing_asset_are_expected_errors(self):
        source = Path(self.directory.name) / "source.bmp"
        Image.new("RGB", (4, 4)).save(source)
        self.assertEqual(self.run_image_request("IMPORT_IMAGE", {
            "source": {"kind": "file", "path": str(source)},
        })["status"], "error")
        self.assertEqual(self.run_image_request("IMPORT_IMAGE", {
            "source": {"kind": "file", "path": str(source.with_name("missing.png"))},
        })["status"], "error")
        corrupt = Path(self.directory.name) / "corrupt.png"
        corrupt.write_bytes(b"\x89PNG\r\n\x1a\nnot a valid image")
        self.assertEqual(self.run_image_request("IMPORT_IMAGE", {
            "source": {"kind": "file", "path": str(corrupt)},
        })["status"], "error")
        for asset in ("../source.bmp", "assets/image-" + "0" * 32 + ".png"):
            self.assertEqual(self.run_image_request("LOAD_PREVIEW", {
                "image-asset": asset, "width": 100, "height": 100,
            })["status"], "error")


if __name__ == "__main__":
    unittest.main()
