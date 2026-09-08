"""Behavioral checks for ownership, continuation passage, and the live workers."""

from queue import Queue
from threading import Thread
import unittest

from today import core, machine, mem, mobile_stacks


def runtime(name, handlers=None):
    return {"name": name, "inbox": Queue(), "current-stack": None,
            "handlers": handlers or {}, "running": False}


def stack(*frames, registers=None):
    return {"kind": "MOBILE_STACK", "frames": list(frames),
            "registers": registers or {}}


class MachineTests(unittest.TestCase):
    def setUp(self):
        machine.machines.clear()
        self.core = runtime("CORE", {"PANEL_RETURNED": core.handle_when_core_receives_panel_return})
        self.mem = runtime("MEM", {"GET_PANEL": mem.handle_when_mem_receives_get_panel})
        machine.install_machine(self.core)
        machine.install_machine(self.mem)
        machine.claim_machine("CORE")
        core.tabs.clear()
        core.positions.clear()
        core.visible_panels.clear()
        core.g["reducer-events"].clear()
        core.g["effects"].clear()
        mem.days.clear()
        mem.panels.clear()
        self.commands = Queue()
        core.g["send-tk-command"] = self.commands.put

    def test_mem_exports_independent_container(self):
        machine.claim_machine("MEM")
        mem.panels["panel-1"] = {"id": "panel-1", "data": {"text": ["original"]}}
        work = stack({"machine": "CORE", "entry": "PANEL_RETURNED"},
                     {"machine": "MEM", "entry": "GET_PANEL"},
                     registers={"panel-id": "panel-1"})
        machine.handle_received_mobile_stack(work)
        returned = self.core["inbox"].get_nowait()
        self.assertIs(returned, work)
        self.assertIsNone(self.mem["current-stack"])
        returned["registers"]["panel"]["data"]["text"].append("edited")
        self.assertEqual(mem.panels["panel-1"]["data"]["text"], ["original"])

    def test_core_delivery_survives_continuing_stack_mutation(self):
        work = stack({"machine": "MEM", "entry": "LATER"},
                     {"machine": "CORE", "entry": "PANEL_RETURNED"},
                     registers={"panel-id": "panel-1",
                                "panel": {"id": "panel-1", "data": {"text": ["received"]}}})
        machine.handle_received_mobile_stack(work)
        forwarded = self.mem["inbox"].get_nowait()
        self.assertIs(forwarded, work)
        self.assertIsNone(self.core["current-stack"])
        forwarded["registers"]["panel"]["data"]["text"].append("later")
        event = core.g["reducer-events"].pop()
        core.reduce_event(event)
        self.assertEqual(core.visible_panels["panel-1"]["data"]["text"], ["received"])

    def test_same_machine_continuation_is_queued_then_completed(self):
        visited = []
        self.core["handlers"] = {entry: lambda entry=entry: visited.append(entry)
                                 for entry in ("FIRST", "SECOND")}
        work = stack({"machine": "CORE", "entry": "SECOND"},
                     {"machine": "CORE", "entry": "FIRST"})
        machine.handle_received_mobile_stack(work)
        self.assertEqual(visited, ["FIRST"])
        self.assertIsNone(self.core["current-stack"])
        returned = self.core["inbox"].get_nowait()
        self.assertIs(returned, work)
        machine.handle_received_mobile_stack(returned)
        self.assertEqual(visited, ["FIRST", "SECOND"])
        self.assertEqual(work["frames"], [])
        self.assertIsNone(self.core["current-stack"])

    def test_active_stack_cannot_be_overwritten(self):
        mobile_stacks.create_stack()
        active = mobile_stacks.stack()
        with self.assertRaises(RuntimeError):
            mobile_stacks.create_stack()
        with self.assertRaises(RuntimeError):
            machine.handle_received_mobile_stack(stack())
        self.assertIs(mobile_stacks.stack(), active)

    def test_route_relinquishes_slot_before_publishing(self):
        published = []

        class ObservingInbox:
            def put(_, item):
                self.assertIsNone(self.core["current-stack"])
                published.append(item)

        self.mem["inbox"] = ObservingInbox()
        mobile_stacks.create_stack()
        mobile_stacks.push_frame({"machine": "MEM", "entry": "GET_PANEL"})
        active = mobile_stacks.stack()
        machine.route_current_stack()
        self.assertIs(published[0], active)

    def test_wrong_machine_does_not_dispatch(self):
        work = stack({"machine": "MEM", "entry": "GET_PANEL"})
        with self.assertRaisesRegex(RuntimeError, "frame for MEM received by CORE"):
            machine.handle_received_mobile_stack(work)

    def test_rename_before_delivery_is_ignored(self):
        self.assertEqual(core.reduce_event({"type": "RENAME_PANEL", "panel-id": "panel-1"}), [])

    def exercise_workers(self, shutdown):
        workers = [Thread(target=mem.run_mem_machine, daemon=True),
                   Thread(target=core.run_reducer_core, daemon=True)]
        for worker in workers:
            worker.start()
        try:
            render = self.commands.get(timeout=3)
            self.assertEqual(render["type"], "RENDER_TODAY")
            self.assertEqual(render["panel-label"], "panel-1")
            self.assertTrue(self.core["running"])
            self.assertTrue(self.mem["running"])
            self.core["inbox"].put({"type": "RENAME_PANEL", "panel-id": "panel-1"})
            renamed = self.commands.get(timeout=3)
            self.assertEqual(renamed["panel-label"], "renamed panel")
            self.core["inbox"].put(shutdown)
            self.assertEqual(self.commands.get(timeout=3), {"type": "SHUTDOWN_COMPLETE"})
        finally:
            self.core["inbox"].put(None)
            self.mem["inbox"].put(None)
            for worker in workers:
                worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertFalse(self.core["running"])
        self.assertFalse(self.mem["running"])
        self.assertIsNone(self.core["current-stack"])
        self.assertIsNone(self.mem["current-stack"])
        self.assertEqual(mem.panels["panel-1"]["label"], "panel-1")

    def test_workers_semantic_shutdown(self):
        self.exercise_workers({"type": "SHUTDOWN"})

    def test_workers_sentinel_shutdown(self):
        self.exercise_workers(None)


if __name__ == "__main__":
    unittest.main()
