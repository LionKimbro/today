"""Behavioral checks for ownership, continuation passage, and the live workers."""

from queue import Queue
from threading import Thread
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import json
import unittest

from today import core, disk, machine, mem, mobile_stacks


def runtime(name, handlers=None):
    return {"name": name, "inbox": Queue(), "current-stack": None,
            "handlers": handlers or {}, "running": False}


def stack(*frames, registers=None):
    return {"kind": "MOBILE_STACK", "frames": list(frames),
            "registers": registers or {}}


class MachineTests(unittest.TestCase):
    def setUp(self):
        # Disk's production default points at the user's real Today database.
        # Every test replaces it with a fresh directory and restores it afterward.
        self.temporary_database = TemporaryDirectory()
        self.real_data_root = disk.DATA_ROOT
        disk.DATA_ROOT = Path(self.temporary_database.name)
        self.addCleanup(self.restore_database_root)

        machine.machines.clear()
        self.core = runtime("CORE", {
            "PANEL_RETURNED": core.handle_when_core_receives_panel_return,
            "DAY_LAYOUT_RETURNED": core.handle_when_core_receives_day_layout,
            "PANEL_UPDATED": core.handle_when_core_receives_panel_update,
        })
        self.mem = runtime("MEM", {
            "DAY_BUNDLE_RETURNED": mem.handle_when_mem_receives_day_bundle,
            "GET_PANEL": mem.handle_when_mem_receives_get_panel,
            "UPDATE_PANEL": mem.handle_when_mem_receives_update_panel,
        })
        self.disk = runtime("DISK", {
            "LOAD_DAY": disk.handle_when_disk_receives_load_day,
            "WRITE_DAY": disk.handle_when_disk_receives_write_day,
        })
        machine.install_machine(self.core)
        machine.install_machine(self.mem)
        machine.install_machine(self.disk)
        machine.claim_machine("CORE")
        core.tabs.clear()
        core.positions.clear()
        core.visible_panels.clear()
        core.g["reducer-events"].clear()
        core.g["effects"].clear()
        mem.initialize_mem_store()
        self.commands = Queue()
        core.g["send-tk-command"] = self.commands.put

    def restore_database_root(self):
        disk.DATA_ROOT = self.real_data_root
        self.temporary_database.cleanup()

    def test_mem_exports_independent_container(self):
        machine.claim_machine("MEM")
        mem.panels["panel-1"] = {
            "id": "panel-1",
            "day-id": "2026-09-17",
            "data": {"text": ["original"]},
        }
        work = stack({"machine": "CORE", "entry": "PANEL_RETURNED"},
                     {"machine": "MEM", "entry": "GET_PANEL"},
                     registers={"day-id": "2026-09-17", "panel-id": "panel-1"})
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

    def test_disk_round_trip_uses_the_isolated_database(self):
        day_id = "2026-09-17"
        bundle = {"day": {"id": day_id}, "panels": {}}
        machine.claim_machine("DISK")
        write = stack({"machine": "DISK", "entry": "WRITE_DAY"}, registers={"day-bundle": bundle})
        machine.handle_received_mobile_stack(write)

        _, path = disk.get_day_paths(day_id)
        self.assertTrue(path.is_file())
        self.assertTrue(path.is_relative_to(Path(self.temporary_database.name)))

        load = stack({"machine": "DISK", "entry": "LOAD_DAY"}, registers={"day-id": day_id})
        machine.handle_received_mobile_stack(load)
        self.assertEqual(load["registers"]["day-bundle"], bundle)

    def test_disk_load_of_an_absent_day_returns_none_without_creating_files(self):
        day_id = "2026-09-18"
        machine.claim_machine("DISK")
        load = stack({"machine": "DISK", "entry": "LOAD_DAY"}, registers={"day-id": day_id})

        machine.handle_received_mobile_stack(load)

        directory, path = disk.get_day_paths(day_id)
        self.assertIsNone(load["registers"]["day-bundle"])
        self.assertFalse(path.exists())
        self.assertFalse(directory.exists())

    def test_install_day_bundle_rejects_an_unsupported_format_without_mutation(self):
        mem.create_new_day("2026-09-17")
        bundle = mem.make_day_bundle("2026-09-17")
        bundle["format"] = "obsolete-format"
        before = (deepcopy(mem.days), deepcopy(mem.tabs), deepcopy(mem.rows),
                  deepcopy(mem.positions), deepcopy(mem.panels))

        with self.assertRaisesRegex(RuntimeError, "unsupported day bundle"):
            mem.install_day_bundle(bundle)

        self.assertEqual(
            (mem.days, mem.tabs, mem.rows, mem.positions, mem.panels), before
        )

    def test_install_day_bundle_rejects_cross_day_panel_without_mutation(self):
        day_id = "2026-09-17"
        mem.create_new_day(day_id)
        bundle = mem.make_day_bundle(day_id)
        next(iter(bundle["panels"].values()))["day-id"] = "2026-09-18"
        before = (deepcopy(mem.days), deepcopy(mem.tabs), deepcopy(mem.rows),
                  deepcopy(mem.positions), deepcopy(mem.panels))

        with self.assertRaisesRegex(RuntimeError, "panel ownership mismatch"):
            mem.install_day_bundle(bundle)

        self.assertEqual(
            (mem.days, mem.tabs, mem.rows, mem.positions, mem.panels), before
        )

    def test_mem_refuses_to_export_a_panel_owned_by_another_day(self):
        first_day, second_day = "2026-09-17", "2026-09-18"
        mem.create_new_day(first_day)
        mem.create_new_day(second_day)
        panel_id = next(iter(mem.make_day_bundle(first_day)["panels"]))
        machine.claim_machine("MEM")
        work = stack(
            {"machine": "MEM", "entry": "GET_PANEL"},
            registers={"day-id": second_day, "panel-id": panel_id},
        )

        with self.assertRaisesRegex(RuntimeError, "does not belong to day"):
            machine.handle_received_mobile_stack(work)

    def test_forced_mem_flush_writes_the_pending_day_to_isolated_disk(self):
        day_id = "2026-09-17"
        machine.claim_machine("MEM")
        mem.create_new_day(day_id)
        panel_id = next(iter(mem.make_day_bundle(day_id)["panels"]))
        mem.panels[panel_id]["label"] = "Saved from Mem"
        mem.mark_day_for_disk_save(day_id)

        mem.flush_day_writes_when_due(force=True)

        self.assertNotIn(day_id, mem.g["pending-day-writes"])
        write = self.disk["inbox"].get_nowait()
        machine.claim_machine("DISK")
        machine.handle_received_mobile_stack(write)
        _, path = disk.get_day_paths(day_id)
        with path.open(encoding="utf-8") as source:
            persisted = json.load(source)
        self.assertEqual(persisted["panels"][panel_id]["label"], "Saved from Mem")

    def exercise_workers(self, shutdown):
        workers = [Thread(target=disk.run_disk_machine, daemon=True),
                   Thread(target=mem.run_mem_machine, daemon=True),
                   Thread(target=core.run_reducer_core, daemon=True)]
        for worker in workers:
            worker.start()
        try:
            render = self.commands.get(timeout=3)
            self.assertEqual(render["type"], "RENDER_TODAY")
            self.assertEqual(render["today-id"], core.g["current-day-id"])
            self.assertTrue(self.core["running"])
            self.assertTrue(self.mem["running"])
            self.assertTrue(self.disk["running"])
            panel_id = next(iter(core.visible_panels))
            self.core["inbox"].put({"type": "RENAME_PANEL", "panel-id": panel_id})
            renamed = self.commands.get(timeout=3)
            self.assertEqual(renamed, {
                "type": "SET_PANEL_LABEL", "panel-id": panel_id, "panel-label": "renamed panel"
            })
            self.core["inbox"].put(shutdown)
            self.assertEqual(self.commands.get(timeout=3), {"type": "SHUTDOWN_COMPLETE"})
        finally:
            self.core["inbox"].put(None)
            self.mem["inbox"].put(None)
            self.disk["inbox"].put(None)
            for worker in workers:
                worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertFalse(self.core["running"])
        self.assertFalse(self.mem["running"])
        self.assertFalse(self.disk["running"])
        self.assertIsNone(self.core["current-stack"])
        self.assertIsNone(self.mem["current-stack"])
        self.assertIsNone(self.disk["current-stack"])
        _, saved_day = disk.get_day_paths(core.g["current-day-id"])
        with saved_day.open(encoding="utf-8") as source:
            saved_bundle = json.load(source)
        self.assertEqual(saved_bundle["panels"][panel_id]["label"], "renamed panel")

    def test_workers_semantic_shutdown(self):
        self.exercise_workers({"type": "SHUTDOWN"})

    def test_workers_sentinel_shutdown(self):
        self.exercise_workers(None)


if __name__ == "__main__":
    unittest.main()
