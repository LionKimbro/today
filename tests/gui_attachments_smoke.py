"""Exercise an Attachments panel through real Tk and worker machines."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from today import main, tk


def run():
    with tempfile.TemporaryDirectory() as temp:
        original_build = tk.build_today_window
        failures = []
        opened = []
        def build_and_schedule():
            original_build()
            root = tk.g["root"]
            state = {"phase": 0, "attempts": 0}
            def step():
                try:
                    state["attempts"] += 1
                    if state["attempts"] > 300:
                        raise AssertionError("timed out")
                    if state["phase"] == 0 and tk.position_widgets:
                        position_id = next(iter(tk.position_widgets))
                        tk.g["outgoing-events"].put({"type": "CREATE_AND_HOST_PANEL", "position-id": position_id,
                                                     "panel-type": "ATTACHMENTS"})
                        state["phase"] = 1
                    elif state["phase"] == 1 and tk.attachments_session and tk.attachments_session["listing-request"] is None:
                        panel = tk.attachments_session["panels"][0]
                        assert panel["status"].cget("text") == "No attachments yet"
                        tk.handle_when_user_opens_attachments_folder()
                        state["phase"] = 2
                    elif state["phase"] == 2 and opened:
                        folder = Path(opened[0])
                        assert folder.name == "files" and folder.is_dir()
                        (folder / "test.txt").write_bytes(b"hello")
                        (folder / "subfolder").mkdir()
                        state["phase"] = 3
                    elif state["phase"] == 3:
                        panel = tk.attachments_session["panels"][0]
                        listing = panel["listing"]
                        names = [listing.item(item, "text") for item in listing.get_children()]
                        if names == ["subfolder", "test.txt"]:
                            assert listing.item(listing.get_children()[1], "values") == ("File", "5")
                            state["phase"] = 4
                            tk.handle_when_user_requests_window_close()
                            return
                    root.after(50, step)
                except Exception as error:
                    failures.append(error)
                    tk.handle_when_user_requests_window_close()
            root.after(50, step)
        with patch.object(tk, "build_today_window", side_effect=build_and_schedule), \
             patch.object(tk.os, "startfile", side_effect=opened.append):
            main.main(data_root=temp)
        if failures:
            raise failures[0]
        assert opened
        print("Attachments GUI and machine roundtrip passed")


if __name__ == "__main__":
    run()
