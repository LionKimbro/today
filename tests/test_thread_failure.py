"""Fatal shutdown wakes peers and abandons queued ordinary work."""

from contextlib import redirect_stderr
from io import StringIO
from queue import Queue
from threading import Barrier, Thread
from unittest.mock import patch
import unittest

from today import core, disk, machine, mem


class ThreadFailureTests(unittest.TestCase):
    def setUp(self):
        machine.a_thread_died_unexpectedly.clear()
        machine.machines.clear()
        for name in ("CORE", "MEM", "DISK"):
            machine.install_machine({
                "name": name, "inbox": Queue(), "current-stack": None,
                "handlers": {}, "running": False,
            })

    def tearDown(self):
        machine.a_thread_died_unexpectedly.clear()
        machine.machines.clear()

    def test_simultaneous_reports_wake_each_queue_once(self):
        ready = Barrier(3)

        def report_failure():
            ready.wait()
            machine.when_thread_dies_unexpectedly()

        reporters = [Thread(target=report_failure) for _ in range(2)]
        for reporter in reporters:
            reporter.start()
        ready.wait()
        for reporter in reporters:
            reporter.join(3)
            self.assertFalse(reporter.is_alive())
        self.assertTrue(machine.a_thread_died_unexpectedly.is_set())
        for runtime in machine.machines.values():
            self.assertIsNone(runtime["inbox"].get_nowait())
            self.assertTrue(runtime["inbox"].empty())

    def test_each_worker_failure_prints_traceback_and_wakes_blocked_peers(self):
        for failed_name in ("CORE", "MEM", "DISK"):
            with self.subTest(worker=failed_name):
                machine.a_thread_died_unexpectedly.clear()
                for runtime in machine.machines.values():
                    runtime["inbox"] = Queue()
                ready = Barrier(3)

                def peer_loop():
                    machine.get_current_runtime()["running"] = True
                    ready.wait()
                    machine.run_machine()

                def failing_loop():
                    ready.wait()
                    raise SystemExit("injected worker failure")

                workers = [Thread(target=machine.run_worker, args=(
                    name, failing_loop if name == failed_name else peer_loop,
                )) for name in machine.machines]
                errors = StringIO()
                with redirect_stderr(errors):
                    for worker in workers:
                        worker.start()
                    for worker in workers:
                        worker.join(3)
                self.assertFalse(any(worker.is_alive() for worker in workers))
                self.assertIn("Traceback (most recent call last)", errors.getvalue())
                self.assertIn("SystemExit: injected worker failure", errors.getvalue())
                self.assertTrue(machine.a_thread_died_unexpectedly.is_set())
                self.assertTrue(all(not r["running"] for r in machine.machines.values()))

    def test_fatal_signal_prevents_queued_work_and_mem_flush(self):
        machine.when_thread_dies_unexpectedly()
        with patch.object(machine, "handle_received_mobile_stack") as dispatch, \
                patch.object(mem, "flush_day_writes_when_due") as flush, \
                patch.object(core, "dispatch_effect") as effect:
            core.run_reducer_core()
            mem.run_mem_machine()
            disk.run_disk_machine()
            dispatch.assert_not_called()
            flush.assert_not_called()
            effect.assert_not_called()

    def test_fatal_signal_after_queue_wakeup_discards_returned_item(self):
        for name, worker_loop in (
            ("CORE", core.run_reducer_core),
            ("MEM", mem.run_mem_machine),
            ("DISK", disk.run_disk_machine),
        ):
            with self.subTest(worker=name):
                machine.a_thread_died_unexpectedly.clear()

                def wake_with_ordinary_work(*args, **kwargs):
                    machine.when_thread_dies_unexpectedly()
                    return {"type": "MUST_NOT_BE_PROCESSED"}

                with patch.object(machine.machines[name]["inbox"], "get",
                                  side_effect=wake_with_ordinary_work), \
                        patch.object(core, "process_reducer_events_until_quiet"), \
                        patch.object(machine, "handle_received_mobile_stack") as dispatch, \
                        patch.object(mem, "flush_day_writes_when_due") as flush:
                    worker_loop()
                    dispatch.assert_not_called()
                    flush.assert_not_called()
                self.assertFalse(machine.machines[name]["running"])


if __name__ == "__main__":
    unittest.main()
