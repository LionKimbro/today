import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import patch

from today import disk, tk


class Widget:
    def __init__(self):
        self.options = {}
        self.rows = []

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get_children(self):
        return list(range(len(self.rows)))

    def delete(self, *items):
        self.rows.clear()

    def insert(self, parent, where, **kwargs):
        self.rows.append(kwargs)


class Root:
    def __init__(self):
        self.callbacks = {}
        self.number = 0

    def after(self, delay, callback):
        self.number += 1
        self.callbacks[self.number] = (delay, callback)
        return self.number

    def after_cancel(self, token):
        self.callbacks.pop(token, None)


class AttachmentTests(unittest.TestCase):
    def test_disk_listing_and_open_before_save(self):
        with tempfile.TemporaryDirectory() as temp:
            disk.initialize_data_root(temp)
            registers = {"day-id": "2026-09-17"}
            def set_register(pair):
                registers[pair[0]] = pair[1]
            with patch.object(disk.mobile_stacks, "get_register", side_effect=registers.__getitem__), \
                 patch.object(disk.mobile_stacks, "set_register", side_effect=set_register):
                disk.handle_when_disk_receives_list_attachments()
                self.assertEqual(registers["result"]["entries"], [])
                disk.handle_when_disk_receives_open_attachments()
                folder = Path(registers["result"]["path"])
                self.assertEqual(folder, Path(temp) / "2026" / "2026-09" / "2026-09-17" / "files")
                (folder / "z.txt").write_bytes(b"abc")
                (folder / "Alpha").mkdir()
                disk.handle_when_disk_receives_list_attachments()
                self.assertEqual(registers["result"]["entries"], [
                    {"name": "Alpha", "type": "Folder", "size": None},
                    {"name": "z.txt", "type": "File", "size": 3},
                ])
                (folder / "z.txt").unlink()
                disk.handle_when_disk_receives_list_attachments()
                self.assertEqual(len(registers["result"]["entries"]), 1)

    def test_pending_error_recovery_and_stale_reply(self):
        root = Root()
        panel = {"indicator": Widget(), "listing": Widget(), "status": Widget()}
        tk.g["root"] = root
        tk.g["outgoing-events"] = Queue()
        tk.attachments_session.clear()
        tk.attachments_session.update({"id": "session", "day-id": "2026-09-17", "panels": [panel],
                                       "timer": None, "listing-request": None, "open-requests": set()})
        try:
            tk.request_attachments_listing()
            request = tk.g["outgoing-events"].get_nowait()
            tk.request_attachments_listing()
            self.assertTrue(tk.g["outgoing-events"].empty())
            self.assertEqual(panel["indicator"].options["background"], "#000000")
            reply = {**request, "operation": "LIST_ATTACHMENTS", "result": {
                "error": None, "entries": [{"name": "a", "type": "File", "size": 4}]}}
            tk.handle_when_attachments_result_arrives({**reply, "session-id": "old"})
            self.assertEqual(panel["listing"].rows, [])
            tk.handle_when_attachments_result_arrives(reply)
            self.assertEqual(panel["listing"].rows[0]["text"], "a")
            self.assertNotEqual(panel["indicator"].options["background"], "#000000")
            self.assertGreater(int(panel["indicator"].options["background"][5:7], 16),
                               int(panel["indicator"].options["background"][1:3], 16))
            tk.g["root"].after_cancel(tk.attachments_session["timer"])
            tk.request_attachments_listing()
            request = tk.g["outgoing-events"].get_nowait()
            tk.handle_when_attachments_result_arrives({**request, "operation": "LIST_ATTACHMENTS",
                                                       "result": {"error": "denied"}})
            self.assertEqual(panel["listing"].rows[0]["text"], "a")
            self.assertEqual(panel["status"].options["text"], "denied")
            self.assertEqual(root.callbacks[tk.attachments_session["timer"]][0], 5000)
            tk.request_attachments_listing()
            request = tk.g["outgoing-events"].get_nowait()
            tk.handle_when_attachments_result_arrives({**request, "operation": "LIST_ATTACHMENTS",
                                                       "result": {"error": None, "entries": []}})
            self.assertEqual(panel["status"].options["text"], "No attachments yet")
            self.assertEqual(panel["listing"].rows, [])
            tk.stop_attachments_session()
            tk.handle_when_attachments_result_arrives(reply)
            self.assertEqual(panel["listing"].rows, [])
        finally:
            tk.stop_attachments_session()


if __name__ == "__main__":
    unittest.main()
