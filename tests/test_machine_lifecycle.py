"""Dynamic machines survive continuations, retire explicitly, and are reaped."""

from queue import Queue
from threading import Event
from contextlib import redirect_stderr
from io import StringIO
import unittest

from today import machine, mobile_stacks


class MachineLifecycleTests(unittest.TestCase):
    def setUp(self):
        machine.initialize_machine_system()
        machine.install_machine({"name": "CORE", "inbox": Queue(),
                                 "current-stack": None, "handlers": {}, "running": False})
        machine.claim_machine("CORE")

    def tearDown(self):
        machine.begin_shutdown()
        for runtime in machine.get_machine_runtimes():
            if runtime["thread"] is not None:
                runtime["inbox"].put(None)
                runtime["thread"].join(3)
                self.assertFalse(runtime["thread"].is_alive())
        machine.reap_exited_machines()
        machine.initialize_machine_system()

    def send_new_machine(self, kind):
        mobile_stacks.create_stack()
        mobile_stacks.push_frame({"machine": "CORE", "entry": "RESULT"})
        frame = {"machine": {"new": kind}, "entry": "START"}
        mobile_stacks.push_frame(frame)
        machine.route_current_stack()
        return frame

    def test_machine_survives_visit_elsewhere_and_retires_after_return(self):
        def start():
            name = machine.get_current_runtime()["name"]
            machine.continue_with_frames([
                {"machine": name, "entry": "RESUME"},
                {"machine": "MEM", "entry": "LOOKUP"},
            ])

        def resume():
            self.assertEqual(mobile_stacks.get_register("value"), "from Mem")
            machine.request_machine_retirement()

        def lookup():
            mobile_stacks.set_register(("value", "from Mem"))

        machine.install_machine_kind("WORK", {"START": start, "RESUME": resume})
        machine.install_machine({"name": "MEM", "inbox": Queue(), "current-stack": None,
                                 "handlers": {"LOOKUP": lookup}, "running": False})
        frame = self.send_new_machine("WORK")
        work = machine.machines["MEM"]["inbox"].get(timeout=3)
        runtime = machine.machines[frame["machine"]]
        self.assertTrue(runtime["thread"].is_alive())
        self.assertEqual(runtime["lifecycle"], "running")
        machine.claim_machine("MEM")
        machine.handle_received_mobile_stack(work)
        returned = machine.machines["CORE"]["inbox"].get(timeout=3)
        runtime["thread"].join(3)
        self.assertFalse(runtime["thread"].is_alive())
        self.assertEqual(returned["registers"]["value"], "from Mem")
        self.assertEqual(runtime["lifecycle"], "exited")
        machine.reap_exited_machines()
        self.assertEqual(runtime["lifecycle"], "reaped")
        self.assertNotIn(frame["machine"], machine.machines)

    def test_machine_can_accept_second_independent_delivery(self):
        handled = Event()

        def start():
            handled.set()

        def stop():
            machine.request_machine_retirement()

        machine.install_machine_kind("WORK", {"START": start, "STOP": stop})
        frame = self.send_new_machine("WORK")
        machine.machines["CORE"]["inbox"].get(timeout=3)
        self.assertTrue(handled.is_set())
        runtime = machine.machines[frame["machine"]]
        self.assertTrue(runtime["thread"].is_alive())
        runtime["inbox"].put({"kind": "MOBILE_STACK", "registers": {}, "frames": [
            {"machine": "CORE", "entry": "RESULT"},
            {"machine": runtime["name"], "entry": "STOP"},
        ]})
        machine.machines["CORE"]["inbox"].get(timeout=3)
        runtime["thread"].join(3)
        self.assertEqual(runtime["lifecycle"], "exited")

    def test_shutdown_prevents_creation_and_wakes_waiting_instances(self):
        machine.install_machine_kind("WORK", {"START": lambda: None})
        frame = self.send_new_machine("WORK")
        machine.machines["CORE"]["inbox"].get(timeout=3)
        runtime = machine.machines[frame["machine"]]
        machine.begin_shutdown()
        runtime["thread"].join(3)
        self.assertFalse(runtime["thread"].is_alive())
        self.send_new_machine("WORK")
        self.assertEqual(len(machine.machines), 2)
        self.assertIsNone(machine.get_current_runtime()["current-stack"])

    def test_retired_destination_is_an_error_outside_shutdown(self):
        machine.install_machine_kind("WORK", {"START": machine.request_machine_retirement})
        frame = self.send_new_machine("WORK")
        machine.machines["CORE"]["inbox"].get(timeout=3)
        runtime = machine.machines[frame["machine"]]
        runtime["thread"].join(3)
        mobile_stacks.create_stack()
        mobile_stacks.push_frame({"machine": runtime["name"], "entry": "START"})
        with self.assertRaisesRegex(RuntimeError, "inactive machine"):
            machine.route_current_stack()
        machine.clear_current_stack()

    def test_shutdown_allows_late_return_to_reaped_machine_to_be_discarded(self):
        def start():
            machine.continue_with_frames([
                {"machine": machine.get_current_runtime()["name"], "entry": "RESUME"},
                {"machine": "MEM", "entry": "LOOKUP"},
            ])

        def resume():
            raise AssertionError("cancelled machine must not resume ordinary work")

        machine.install_machine_kind("WORK", {"START": start, "RESUME": resume})
        machine.install_machine({"name": "MEM", "inbox": Queue(), "current-stack": None,
                                 "handlers": {"LOOKUP": lambda: None}, "running": False})
        frame = self.send_new_machine("WORK")
        outstanding = machine.machines["MEM"]["inbox"].get(timeout=3)
        runtime = machine.machines[frame["machine"]]
        machine.begin_shutdown()
        runtime["thread"].join(3)
        self.assertFalse(runtime["thread"].is_alive())
        machine.reap_exited_machines(["dynamic"])
        machine.claim_machine("MEM")
        machine.handle_received_mobile_stack(outstanding)
        self.assertIsNone(machine.get_current_runtime()["current-stack"])
        self.assertTrue(machine.machines["CORE"]["inbox"].empty())
        self.assertFalse(machine.a_thread_died_unexpectedly.is_set())

    def test_dynamic_exception_is_fatal_and_wakes_another_dynamic_worker(self):
        machine.install_machine_kind("WAIT", {"START": lambda: None})
        waiting_frame = self.send_new_machine("WAIT")
        machine.machines["CORE"]["inbox"].get(timeout=3)
        waiting = machine.machines[waiting_frame["machine"]]

        def fail():
            raise ValueError("dynamic worker failure")

        machine.install_machine_kind("FAIL", {"START": fail})
        errors = StringIO()
        with redirect_stderr(errors):
            failed_frame = self.send_new_machine("FAIL")
            failed = machine.machines[failed_frame["machine"]]
            failed["thread"].join(3)
            waiting["thread"].join(3)
        self.assertFalse(failed["thread"].is_alive())
        self.assertFalse(waiting["thread"].is_alive())
        self.assertTrue(machine.a_thread_died_unexpectedly.is_set())
        self.assertIn("ValueError: dynamic worker failure", errors.getvalue())

    def test_periodic_reaping_keeps_permanent_addresses_for_final_shutdown(self):
        runtime = machine.machines["CORE"]
        runtime["inbox"].put(None)
        thread = machine.start_worker("CORE", machine.run_machine)
        thread.join(3)
        machine.reap_exited_machines(["dynamic"])
        self.assertIn("CORE", machine.machines)
        machine.reap_exited_machines()
        self.assertNotIn("CORE", machine.machines)
