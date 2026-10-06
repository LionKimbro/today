"""Fresh-process real Tk check: CORE|MEM|DISK|normal; database is isolated."""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import enumerate as threads
from unittest.mock import patch
import sys

from today import core, disk, machine, main, mem, tk


def fail_worker():
    raise RuntimeError("injected required worker failure")


def main_check():
    name = sys.argv[1]
    if name == "normal":
        build = tk.build_today_window

        def build_and_schedule_close():
            build()
            tk.g["root"].after(200, tk.handle_when_user_requests_window_close)

        with TemporaryDirectory() as directory, \
                patch.object(disk, "DATA_ROOT", Path(directory)), \
                patch.object(tk, "build_today_window", build_and_schedule_close):
            main.main()
            assert list(Path(directory).rglob("*.json")), "normal shutdown did not save"
        assert not machine.a_thread_died_unexpectedly.is_set()
    else:
        module, entry = {
            "CORE": (core, "handle_when_core_receives_day_layout"),
            "MEM": (mem, "handle_when_mem_receives_day_bundle"),
            "DISK": (disk, "handle_when_disk_receives_load_day"),
        }[name]
        with TemporaryDirectory() as directory, \
                patch.object(disk, "DATA_ROOT", Path(directory)), \
                patch.object(module, entry, fail_worker):
            try:
                main.main()
            except SystemExit as error:
                assert error.code == 1, error.code
            else:
                raise AssertionError("fatal shutdown did not report failure")
        assert machine.a_thread_died_unexpectedly.is_set()
    assert tk.g["closing"]
    assert not [worker for worker in threads() if worker.name.startswith("Today")]
    assert all(not runtime["running"] for runtime in machine.machines.values())
    print("GUI SHUTDOWN PASS", name)


if __name__ == "__main__":
    main_check()
