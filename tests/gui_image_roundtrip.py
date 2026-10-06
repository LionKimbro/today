"""Real application import/restart/clear checks; all data stays in a temp root."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import enumerate as threads
from time import monotonic
from unittest.mock import patch

from PIL import Image
from today import core, disk, machine, main, mem, tk


def run_phase(mode, directory):
    original_build = tk.build_today_window
    errors = []
    deadline = monotonic() + 8
    stage = {"step": "load", "panel-id": None, "position-id": None}

    def check_application():
        try:
            if monotonic() > deadline:
                raise AssertionError(f"Image roundtrip timed out: {stage}")
            if stage["step"] == "load" and tk.position_widgets:
                if mode == "import":
                    stage["position-id"] = next(iter(tk.position_widgets))
                    tk.handle_when_user_clicks_unhost_panel_button(stage["position-id"])
                    stage["step"] = "empty-position"
                else:
                    panel_id = next(panel_id for panel_id, panel in core.visible_panels.items()
                                    if panel["type"] == "IMAGE")
                    stage["panel-id"] = panel_id
                    stage["step"] = "preview" if mode == "reload" else "clear"
            elif stage["step"] == "empty-position":
                if tk.position_widgets[stage["position-id"]]["panel-id"] is None:
                    tk.handle_when_user_creates_panel_for_empty_position(stage["position-id"], "IMAGE")
                    stage["step"] = "image-created"
            elif stage["step"] == "image-created":
                images = [panel_id for panel_id, panel in core.visible_panels.items()
                          if panel["type"] == "IMAGE" and tk.panel_widgets.get(panel_id)]
                if images:
                    stage["panel-id"] = images[0]
                    panel = tk.panel_widgets[images[0]][0]
                    with patch.object(tk.filedialog, "askopenfilename",
                                      return_value=str(Path(directory) / "source with spaces.png")):
                        tk.handle_when_user_browses_for_image(panel)
                    stage["step"] = "preview"
            elif stage["step"] == "preview":
                panel = tk.panel_widgets[stage["panel-id"]][0]
                if panel["image-photo"] is not None and not core.visible_panels[stage["panel-id"]]["dirty"]:
                    reference = mem.panels[stage["panel-id"]]["image-asset"]
                    assert reference.startswith("assets/image-")
                    assert disk.get_image_asset_path(core.g["current-day-id"], reference).is_file()
                    tk.handle_when_user_requests_window_close()
                    return
            elif stage["step"] == "clear":
                panel = tk.panel_widgets[stage["panel-id"]][0]
                tk.handle_when_user_clears_image(panel)
                stage["step"] = "cleared"
            elif stage["step"] == "cleared":
                panel = tk.panel_widgets[stage["panel-id"]][0]
                if (panel["image-asset"] is None
                        and not core.visible_panels[stage["panel-id"]]["dirty"]
                        and panel["image-empty-controls"].winfo_ismapped()):
                    assert panel["image-photo"] is None
                    assert panel["image-empty-controls"].winfo_ismapped()
                    assert mem.panels[stage["panel-id"]]["image-asset"] is None
                    tk.handle_when_user_requests_window_close()
                    return
            tk.g["root"].after(20, check_application)
        except BaseException as error:
            errors.append(error)
            machine.when_thread_dies_unexpectedly()

    def instrument_window():
        original_build()
        tk.g["root"].report_callback_exception = lambda *error: errors.append(error)
        tk.g["root"].after(20, check_application)

    with patch.object(tk, "build_today_window", instrument_window):
        try:
            main.main(data_root=directory)
        except SystemExit:
            if not errors:
                raise
    assert not errors, errors
    assert not [thread for thread in threads() if thread.name.startswith("Today")]
    assert not machine.machines, "final shutdown left unreaped machines"
    bundle = json.loads(next(Path(directory).glob("*/*/*/*.json")).read_text(encoding="utf-8"))
    images = [panel for panel in bundle["panels"].values() if panel["type"] == "IMAGE"]
    assert len(images) == 1
    assert (images[0]["image-asset"] is None) == (mode == "clear")
    assert not any("pixels" in panel or "image-busy" in panel for panel in bundle["panels"].values())
    print("IMAGE ROUNDTRIP PASS", mode)


def run_roundtrip():
    with TemporaryDirectory() as directory:
        Image.new("RGB", (640, 320), "#4C9BFF").save(Path(directory) / "source with spaces.png")
        for mode in ("import", "reload", "clear"):
            result = subprocess.run([sys.executable, __file__, mode, directory],
                                    capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            print(result.stdout.splitlines()[-1])
        assert list(Path(directory).glob("*/*/*/assets/*.png")), "clear deleted the saved asset"


if __name__ == "__main__":
    if len(sys.argv) == 3:
        run_phase(sys.argv[1], sys.argv[2])
    else:
        run_roundtrip()
