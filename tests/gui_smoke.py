"""Run in a fresh process with a real display: python tests/gui_smoke.py MODE.

Modes: normal, delayed, early-close, sentinel. No simulated Tk implementation.
"""

import sys
from threading import Event, enumerate as threads
from time import monotonic

from today import core, machine, main, mem, tk


mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
assert mode in {"normal", "delayed", "early-close", "sentinel"}
build = tk.build_today_window
get_panel = mem.handle_when_mem_receives_get_panel
release_mem = Event()
errors = []
observations = []


def delayed_get_panel():
    if not release_mem.wait(5):
        raise RuntimeError("GUI did not release Mem")
    get_panel()


if mode in {"delayed", "early-close"}:
    mem.handle_when_mem_receives_get_panel = delayed_get_panel


def instrument_window():
    build()
    root = tk.g["root"]
    root.report_callback_exception = lambda *error: errors.append(str(error))
    deadline = monotonic() + 5

    def check(condition, description):
        if not condition:
            errors.append(description)

    def startup():
        if mode in {"delayed", "early-close"}:
            check(tk.widgets["rename-button"].instate(["disabled"]), "rename enabled before load")
            tk.widgets["rename-button"].invoke()
            # Exercise a stale semantic event independently of the disabled widget.
            core_inbox = machine.machines["CORE"]["inbox"]
            core_inbox.put({"type": "RENAME_PANEL", "panel-id": "panel-1"})
            if mode == "early-close":
                tk.handle_when_user_requests_window_close()
                tk.handle_when_user_requests_window_close()
                release_mem.set()
                observations.append("closed with panel request outstanding")
                return
            release_mem.set()
        observe_render()

    def observe_render():
        if tk.widgets["panel-label"].cget("text") != "panel-1":
            if monotonic() > deadline:
                errors.append("panel never rendered")
                tk.handle_when_user_requests_window_close()
                return
            root.after(10, observe_render)
            return
        check(tk.widgets["rename-button"].instate(["!disabled"]), "rename disabled after load")
        check(tk.widgets["position"].cget("text") == "position-1", "wrong position")
        observations.append("rendered panel-1")
        tk.widgets["rename-button"].invoke()
        root.after(10, observe_rename)

    def observe_rename():
        if tk.widgets["panel-label"].cget("text") != "renamed panel":
            if monotonic() > deadline:
                errors.append("rename never rendered")
            else:
                root.after(10, observe_rename)
                return
        observations.append("renamed through widget callback")
        if mode == "sentinel":
            machine.machines["CORE"]["inbox"].put(None)
        else:
            tk.handle_when_user_requests_window_close()

    root.after(20, startup)


tk.build_today_window = instrument_window
main.main()
assert not errors, errors
assert not [t for t in threads() if t.name.startswith("Today")]
assert all(not runtime["running"] for runtime in machine.machines.values())
print("GUI PASS", mode, observations)
