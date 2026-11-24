"""Hold a Mem commit, edit again, close mid-stroke, restart; isolated database."""

import json
from pathlib import Path
from contextlib import nullcontext
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, enumerate as threads
from time import monotonic
from unittest.mock import patch

from PIL import Image
from today import core, disk, machine, main, mem, mobile_stacks, tk


def run_phase(mode, directory):
    build = tk.build_today_window
    update = mem.handle_when_mem_receives_update_panel
    entered, release = Event(), Event()
    errors = []
    stage = {"step": "load"}
    deadline = monotonic() + 8

    def hold_first_drawing_commit():
        proposed = mobile_stacks.get_register("proposed-panel")
        if proposed["type"] == "IMAGE" and not entered.is_set():
            entered.set()
            assert release.wait(5), "test did not release held Mem commit"
        update()

    def check_saved_close_is_waiting():
        try:
            assert core.g["shutdown-requested"]
            assert not machine.shutdown_started.is_set(), "workers stopped before latest commit"
            assert main.worker_threads["CORE"].is_alive()
            assert tk.g["root"].winfo_exists()
        except BaseException as error:
            errors.append(error)
        finally:
            release.set()

    def check_application():
        try:
            assert monotonic() < deadline, stage
            images = [p for p in core.visible_panels.values() if p["type"] == "IMAGE"]
            if not images or not tk.panel_widgets.get(images[0]["id"]):
                tk.g["root"].after(20, check_application)
                return
            panel_id = images[0]["id"]
            panel = tk.panel_widgets[panel_id][0]
            canvas = panel["image-canvas"]
            if stage["step"] == "load" and panel["image-photo"] is not None:
                if mode == "reload":
                    assert len(images[0]["image-strokes"]) == 2
                    assert len(canvas.find_withtag("image-ink")) == 2
                    tk.handle_when_user_requests_window_close()
                    return
                panel["image-pen"].invoke()
                x, y = canvas.winfo_width() // 2, canvas.winfo_height() // 2
                canvas.event_generate("<ButtonPress-1>", x=x - 20, y=y - 10)
                canvas.event_generate("<ButtonRelease-1>", x=x + 20, y=y + 10)
                tk.submit_image_save(panel_id)
                stage["step"] = "held"
            elif stage["step"] == "held" and entered.is_set():
                x, y = canvas.winfo_width() // 2, canvas.winfo_height() // 2
                canvas.event_generate("<ButtonPress-1>", x=x, y=y)
                canvas.event_generate("<B1-Motion>", x=x + 30, y=y + 10)
                tk.handle_when_user_requests_window_close()
                tk.g["root"].after(100, check_saved_close_is_waiting)
                return
            tk.g["root"].after(20, check_application)
        except BaseException as error:
            errors.append(error)
            release.set()
            machine.when_thread_dies_unexpectedly()

    def instrument_window():
        build()
        tk.g["root"].report_callback_exception = lambda *error: errors.append(error)
        tk.g["root"].after(20, check_application)

    def fail_final_write():
        raise OSError("injected final day-save failure")

    failed_exit = False
    with patch.object(tk, "build_today_window", instrument_window), \
            patch.object(mem, "handle_when_mem_receives_update_panel", hold_first_drawing_commit), \
            (patch.object(disk, "handle_when_disk_receives_write_day", fail_final_write)
             if mode == "save-failure" else nullcontext()):
        try:
            main.main(data_root=directory)
        except SystemExit as error:
            if mode == "save-failure":
                assert error.code == 1
                failed_exit = True
            elif not errors:
                raise
    assert not errors, errors
    assert not [thread for thread in threads() if thread.name.startswith("Today")]
    assert not machine.machines
    if mode == "save-failure":
        assert failed_exit and machine.a_thread_died_unexpectedly.is_set()
        print("IMAGE DRAWING ROUNDTRIP PASS", mode)
        return
    assert not machine.a_thread_died_unexpectedly.is_set()
    bundle = json.loads(next(Path(directory).glob("*/*/*/*.json")).read_text(encoding="utf-8"))
    image_panel = next(p for p in bundle["panels"].values() if p["type"] == "IMAGE")
    assert len(image_panel["image-strokes"]) == 2
    asset = disk.get_image_asset_path(bundle["day"]["id"], image_panel["image-asset"])
    assert asset.read_bytes() == (Path(directory) / "source with spaces.png").read_bytes()
    print("IMAGE DRAWING ROUNDTRIP PASS", mode)


def run_roundtrip():
    with TemporaryDirectory() as directory:
        Image.new("RGB", (640, 320), "blue").save(Path(directory) / "source with spaces.png")
        commands = [([str(Path(__file__).with_name("gui_image_roundtrip.py")), "import", directory]),
                    [__file__, "draw", directory], [__file__, "reload", directory],
                    [__file__, "save-failure", directory]]
        for command in commands:
            result = subprocess.run([sys.executable, *command], capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.splitlines()[-1])


if __name__ == "__main__":
    if len(sys.argv) == 3:
        run_phase(sys.argv[1], sys.argv[2])
    else:
        run_roundtrip()
