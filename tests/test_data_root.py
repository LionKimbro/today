"""MachineRoot selection and test isolation at the startup boundary."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import machineroot
from today import disk, main, tk


class DataRootTests(unittest.TestCase):
    def setUp(self):
        self.previous_root = disk.g["data-root"]
        self.addCleanup(disk.g.update, {"data-root": self.previous_root})

    def test_default_root_appends_today_and_preserves_day_layout(self):
        with TemporaryDirectory() as directory, \
                patch.object(machineroot, "get", return_value=directory) as lookup:
            disk.initialize_data_root()
            lookup.assert_called_once_with("db-root-2026")
            folder, path = disk.get_day_paths("2026-10-05")
            self.assertEqual(folder, Path(directory) / "today/2026/2026-10/2026-10-05")
            self.assertEqual(path, folder / "2026-10-05.json")
            self.assertFalse(folder.exists())

    def test_explicit_root_bypasses_machine_root_and_has_no_suffix(self):
        with TemporaryDirectory() as directory, patch.object(machineroot, "get") as lookup:
            disk.initialize_data_root(directory)
            lookup.assert_not_called()
            self.assertEqual(disk.g["data-root"], Path(directory))

    def test_missing_registry_or_key_stops_before_window_or_workers(self):
        for error in (
            machineroot.MachineRootNotFoundError("no registry"),
            machineroot.MachineRootKeyError("db-root-2026"),
        ):
            with self.subTest(error=type(error).__name__), \
                    patch.object(machineroot, "get", side_effect=error), \
                    patch.object(tk, "build_today_window") as build, \
                    patch.object(main, "Thread") as worker:
                with self.assertRaises(type(error)):
                    main.main()
                build.assert_not_called()
                worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
