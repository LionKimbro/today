"""Startup and wiring for Today machines."""

from queue import Queue
from threading import Thread

from . import core, machine, mem, tk


def main():
    core_inbox = Queue()
    mem_inbox = Queue()
    core_to_tk = Queue()

    core_runtime = {
        "name": "CORE",
        "inbox": core_inbox,
        "current-stack": None,
        "handlers": {"PANEL_RETURNED": core.handle_when_core_receives_panel_return},
        "running": False,
    }
    mem_runtime = {
        "name": "MEM",
        "inbox": mem_inbox,
        "current-stack": None,
        "handlers": {"GET_PANEL": mem.handle_when_mem_receives_get_panel},
        "running": False,
    }
    machine.install_machine(core_runtime)
    machine.install_machine(mem_runtime)

    core.g["send-tk-command"] = tk.enqueue_core_command_and_wake_tk
    tk.g["outgoing-events"] = core_inbox
    tk.g["incoming-commands"] = core_to_tk

    tk.build_today_window()
    mem_thread = Thread(target=mem.run_mem_machine, name="Today Mem")
    core_thread = Thread(target=core.run_reducer_core, name="Today Reducer Core")
    mem_thread.start()
    core_thread.start()
    tk.run_tk_machine()
    core_thread.join()
    mem_thread.join()
