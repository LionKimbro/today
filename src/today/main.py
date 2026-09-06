"""Startup and wiring for Today."""

from queue import Queue
from threading import Thread

from . import core, tk


def main():
    tk_to_core = Queue()
    core_to_tk = Queue()

    core.g["incoming-events"] = tk_to_core
    core.g["send-tk-command"] = tk.enqueue_core_command_and_wake_tk
    tk.g["outgoing-events"] = tk_to_core
    tk.g["incoming-commands"] = core_to_tk

    tk.build_today_window()
    core_thread = Thread(target=core.run_reducer_core, name="Today Reducer Core")
    core_thread.start()
    tk.run_tk_machine()
    core_thread.join()
