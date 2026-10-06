"""Real Tk checks for Image panel presentation and semantic input boundaries."""

from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch
import tkinter

from today import machine, tk


def settle_image_geometry():
    tk.g["root"].after(180, tk.g["root"].quit)
    tk.g["root"].mainloop()


def drain_events():
    events = []
    while not tk.g["outgoing-events"].empty():
        events.append(tk.g["outgoing-events"].get_nowait())
    return events


def main():
    machine.a_thread_died_unexpectedly.clear()
    tk.g["outgoing-events"] = Queue()
    tk.g["incoming-commands"] = Queue()
    tk.g["closing"] = False
    tk.build_today_window()
    root = tk.g["root"]
    root.withdraw()
    window = tkinter.Toplevel(root)
    window.geometry("440x340")
    host = tkinter.Frame(window, background=tk.COLORS["panel"])
    host.pack(fill="both", expand=True)
    tk.position_widgets["image-position"] = {
        "host": host, "panel-id": None, "panel-widgets": None,
    }
    command = {
        "position-id": "image-position", "panel-id": "image-panel",
        "panel-type": "IMAGE", "panel-label": "Image", "image-asset": None,
        "image-busy": False, "image-error": None,
    }
    try:
        tk.render_hosted_panel(command)
        settle_image_geometry()
        panel = tk.position_widgets["image-position"]["panel-widgets"]
        assert panel["image-canvas"].winfo_ismapped()
        assert drain_events() == []

        tk.handle_when_user_pastes_image(panel)
        assert drain_events() == [{
            "type": "IMPORT_IMAGE", "panel-id": "image-panel",
            "source": {"kind": "clipboard"},
        }]
        assert all(button["state"] == "disabled" for button in panel["image-buttons"])
        tk.handle_when_user_clears_image(panel)
        assert drain_events() == [{"type": "CLEAR_IMAGE", "panel-id": "image-panel"}]
        tk.render_image_view(command)

        path = "C:/example/image with spaces.png"
        with patch.object(tk.filedialog, "askopenfilename", return_value=path):
            tk.handle_when_user_browses_for_image(panel)
        assert drain_events()[0]["source"] == {"kind": "file", "path": path}
        tk.render_image_view(command)

        assert tk.handle_when_user_drops_image(SimpleNamespace(data="{a.png} {b.png}"), panel) == "none"
        assert drain_events() == []
        assert "one image" in panel["image-status"]["text"]
        assert tk.handle_when_user_drops_image(SimpleNamespace(data="{" + path + "}"), panel) == "copy"
        assert drain_events()[0]["source"]["path"] == path

        occupied = dict(command, **{"image-asset": "assets/example.png"})
        tk.render_image_view(occupied)
        settle_image_geometry()
        request = drain_events()[-1]
        assert request["type"] == "REQUEST_IMAGE_PREVIEW"
        preview = {
            "type": "SET_IMAGE_PREVIEW", "panel-id": "image-panel",
            "image-asset": occupied["image-asset"], "width": 2, "height": 2,
            "request-width": request["width"], "request-height": request["height"],
            "pixels": bytes([255, 0, 0, 255]) * 4,
        }
        tk.realize_core_command(preview)
        assert panel["image-photo"].width() == 2
        photo = panel["image-photo"]
        tk.set_image_preview(dict(preview, **{"image-asset": "assets/obsolete.png"}))
        assert panel["image-photo"] is photo
        tk.set_image_preview(dict(preview, **{"request-width": request["width"] + 1}))
        assert panel["image-photo"] is photo

        tk.render_image_view(command)
        assert panel["image-photo"] is None
        tk.set_image_preview(preview)
        assert panel["image-photo"] is None
        tk.handle_when_image_space_resizes(panel)
        assert panel["image-resize-id"] is not None
        tk.clear_position_host("image-position")
        assert panel["image-resize-id"] is None
        assert not panel["image-active"]
        settle_image_geometry()
        print("Image Tk smoke passed: inputs, busy/clear, preview, stale results, teardown.")
    finally:
        root.destroy()
        tk.panel_widgets.clear()
        tk.position_widgets.clear()


if __name__ == "__main__":
    main()
