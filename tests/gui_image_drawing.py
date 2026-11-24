"""Real Tk ink feedback, scaling, idle timer, and leave/close event ordering."""

from copy import deepcopy
from queue import Queue
from types import SimpleNamespace
from time import monotonic
from unittest.mock import patch
import tkinter

from today import machine, tk


def drain_events():
    events = []
    while not tk.g["outgoing-events"].empty():
        events.append(tk.g["outgoing-events"].get_nowait())
    return events


def settle_geometry():
    deadline = monotonic() + 3
    while monotonic() < deadline:
        tk.g["root"].after(20, tk.g["root"].quit)
        tk.g["root"].mainloop()
        panel = tk.panel_widgets["ink"][0]
        if panel["image-canvas"].winfo_ismapped() and panel["image-requested"] is not None:
            return
    raise AssertionError("image geometry did not produce a preview request")


def main():
    machine.initialize_machine_system()
    tk.g["outgoing-events"] = Queue()
    tk.g["incoming-commands"] = Queue()
    tk.g["closing"] = False
    tk.build_today_window()
    root = tk.g["root"]
    root.withdraw()
    window = tkinter.Toplevel(root)
    window.geometry("440x340")
    host = tkinter.Frame(window)
    host.pack(fill="both", expand=True)
    tk.position_widgets["ink-position"] = {"host": host, "panel-id": None, "panel-widgets": None}
    command = {"position-id": "ink-position", "panel-id": "ink", "panel-type": "IMAGE",
               "panel-label": "Image", "image-asset": "assets/image.png", "image-strokes": []}
    try:
        tk.render_hosted_panel(command)
        settle_geometry()
        panel = tk.panel_widgets["ink"][0]
        canvas = panel["image-canvas"]
        request = drain_events()[-1]
        preview = {"panel-id": "ink", "image-asset": command["image-asset"],
                   "width": 80, "height": 40, "pixels": bytes([0, 0, 255, 255]) * 3200,
                   "request-width": request["width"], "request-height": request["height"]}
        tk.set_image_preview(preview)
        panel["image-pen"].invoke()
        assert panel["image-pen-enabled"]
        center = (canvas.winfo_width() / 2, canvas.winfo_height() / 2)
        canvas.event_generate("<ButtonPress-1>", x=int(center[0] - 20), y=int(center[1] - 10))
        canvas.event_generate("<B1-Motion>", x=int(center[0] + 20), y=int(center[1] + 10))
        with patch.object(root, "after", wraps=root.after) as timer:
            canvas.event_generate("<ButtonRelease-1>", x=int(center[0] + 20), y=int(center[1] + 10))
            assert timer.call_args_list[-1].args[0] == 60000
        events = drain_events()
        assert len(events) == 1 and events[0]["type"] == "IMAGE_STROKE_ADDED"
        stroke = events[0]["stroke"]
        assert abs(stroke["points"][0][0] - 0.25) < 0.02
        assert len(canvas.find_withtag("image-ink")) == 1
        assert "ink" in tk.image_save_ids

        # Metadata/late preview refresh does not erase the independent ink layer.
        command["image-strokes"] = [deepcopy(stroke)]
        tk.render_image_view(command)
        tk.set_image_preview(preview)
        assert len(canvas.find_withtag("image-ink")) == 1
        small = dict(preview, width=40, height=20, pixels=bytes([0, 0, 255, 255]) * 800)
        tk.set_image_preview(small)
        ink = canvas.find_withtag("image-ink")[0]
        assert abs(float(canvas.itemcget(ink, "width")) - 1.5) < 0.001
        assert abs(canvas.coords(ink)[0] - (center[0] - 10)) < 1

        # Saving by expiry is independent of the one-second text timers.
        tk.submit_image_save("ink")
        assert drain_events() == [{"type": "SAVE_IMAGE_DRAWING", "panel-id": "ink"}]
        assert not tk.image_save_ids

        # A press outside the fitted image cannot start ink.
        tk.handle_when_user_starts_image_stroke(SimpleNamespace(x=0, y=0), panel)
        assert panel["image-stroke"] is None
        canvas.event_generate("<ButtonPress-1>", x=int(center[0]), y=int(center[1]))
        canvas.event_generate("<ButtonRelease-1>", x=int(center[0]), y=int(center[1]))
        assert canvas.type(canvas.find_withtag("image-ink")[-1]) == "oval"
        drain_events()

        # Closing during another stroke finishes it, then flushes, then shuts down.
        canvas.event_generate("<ButtonPress-1>", x=int(center[0]), y=int(center[1]))
        assert not tk.image_save_ids  # Active drawing cancels idle save.
        canvas.event_generate("<B1-Motion>", x=int(center[0] + 5), y=int(center[1] + 5))
        tk.handle_when_user_requests_window_close()
        assert [event["type"] for event in drain_events()] == [
            "IMAGE_STROKE_ADDED", "SAVE_IMAGE_DRAWING", "SHUTDOWN",
        ]
        assert panel["image-stroke"] is None and not tk.image_save_ids
        print("IMAGE DRAWING TK PASS")
    finally:
        root.destroy()
        tk.panel_widgets.clear()
        tk.position_widgets.clear()
        tk.image_save_ids.clear()


if __name__ == "__main__":
    main()
