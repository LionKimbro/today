"""Startup and wiring for Today machines."""

from queue import Queue

from . import core, disk, image, machine, mem, tk


worker_threads = {"CORE": None, "MEM": None, "DISK": None}


def finish_worker_shutdown():
    """Wait for all producers to stop before stopping Disk's consumer."""
    machine.begin_shutdown()
    worker_threads["CORE"].join()
    for runtime in machine.get_machine_runtimes():
        if runtime["dynamic"] and runtime["thread"] is not None:
            runtime["thread"].join()
    worker_threads["MEM"].join()
    machine.machines["DISK"]["inbox"].put(None)
    worker_threads["DISK"].join()
    machine.reap_exited_machines()


def main(data_root=None):
    disk.initialize_data_root(data_root)
    machine.initialize_machine_system()
    machine.install_machine_kind("IMAGE", image.HANDLERS)
    core_inbox = Queue()
    mem_inbox = Queue()
    disk_inbox = Queue()
    core_to_tk = Queue()

    core_runtime = {
        "name": "CORE",
        "inbox": core_inbox,
        "current-stack": None,
        "handlers": {
            "ATTACHMENTS_RETURNED": core.handle_when_core_receives_attachments_result,
            "IMAGE_IMPORTED": core.handle_when_core_receives_image_import,
            "IMAGE_PREVIEW_RETURNED": core.handle_when_core_receives_image_preview,
            "PANEL_RETURNED": core.handle_when_core_receives_panel_return,
            "PANEL_CREATED_RETURNED": core.handle_when_core_receives_created_panel,
            "PANEL_UPDATED": core.handle_when_core_receives_panel_update,
            "DAY_LAYOUT_RETURNED": core.handle_when_core_receives_day_layout,
            "HOSTING_RETURNED": core.handle_when_core_receives_hosting_update,
            "PANEL_DELETED_RETURNED": core.handle_when_core_receives_deleted_panel,
            "SELECTED_TAB_RETURNED": core.handle_when_core_receives_selected_tab,
            "ROW_LAYOUT_RETURNED": core.handle_when_core_receives_row_layout,
            "TAB_LAYOUT_RETURNED": core.handle_when_core_receives_tab_layout,
            "TAB_CREATED_RETURNED": core.handle_when_core_receives_created_tab,
            "TAB_RENAMED_RETURNED": core.handle_when_core_receives_renamed_tab,
            "TAB_DELETED_RETURNED": core.handle_when_core_receives_deleted_tab,
        },
        "running": False,
    }
    mem_runtime = {
        "name": "MEM",
        "inbox": mem_inbox,
        "current-stack": None,
        "handlers": {
            "DAY_BUNDLE_RETURNED": mem.handle_when_mem_receives_day_bundle,
            "GET_PANEL": mem.handle_when_mem_receives_get_panel,
            "CREATE_PANEL": mem.handle_when_mem_receives_create_panel,
            "SELECT_TAB": mem.handle_when_mem_receives_select_tab,
            "SET_ROW_HEIGHT": mem.handle_when_mem_receives_set_row_height,
            "SET_SASH_PROPORTIONS": mem.handle_when_mem_receives_set_sash_proportions,
            "SET_ROW_COLUMN_COUNT": mem.handle_when_mem_receives_set_row_column_count,
            "MOVE_ROW": mem.handle_when_mem_receives_move_row,
            "ADD_ROW": mem.handle_when_mem_receives_add_row,
            "DELETE_ROW": mem.handle_when_mem_receives_delete_row,
            "SET_TAB_SCROLL_POSITION": mem.handle_when_mem_receives_set_tab_scroll_position,
            "CREATE_TAB": mem.handle_when_mem_receives_create_tab,
            "RENAME_TAB": mem.handle_when_mem_receives_rename_tab,
            "DELETE_TAB": mem.handle_when_mem_receives_delete_tab,
            "UPDATE_PANEL": mem.handle_when_mem_receives_update_panel,
            "HOST_PANEL": mem.handle_when_mem_receives_host_panel,
            "UNHOST_PANEL": mem.handle_when_mem_receives_unhost_panel,
            "DELETE_PANEL": mem.handle_when_mem_receives_delete_panel,
        },
        "running": False,
    }
    disk_runtime = {
        "name": "DISK",
        "inbox": disk_inbox,
        "current-stack": None,
        "handlers": {
            "LIST_ATTACHMENTS": disk.handle_when_disk_receives_list_attachments,
            "OPEN_ATTACHMENTS": disk.handle_when_disk_receives_open_attachments,
            "WRITE_IMAGE_ASSET": disk.handle_when_disk_receives_write_image_asset,
            "READ_IMAGE_ASSET": disk.handle_when_disk_receives_read_image_asset,
            "LOAD_DAY": disk.handle_when_disk_receives_load_day,
            "WRITE_DAY": disk.handle_when_disk_receives_write_day,
        },
        "running": False,
    }
    machine.install_machine(core_runtime)
    machine.install_machine(mem_runtime)
    machine.install_machine(disk_runtime)

    core.g["send-tk-command"] = tk.enqueue_core_command_and_wake_tk
    tk.g["outgoing-events"] = core_inbox
    tk.g["incoming-commands"] = core_to_tk

    tk.build_today_window()
    worker_threads["DISK"] = machine.start_worker("DISK", disk.run_disk_machine)
    worker_threads["MEM"] = machine.start_worker("MEM", mem.run_mem_machine)
    worker_threads["CORE"] = machine.start_worker("CORE", core.run_reducer_core)
    tk.run_tk_machine()
    finish_worker_shutdown()
    if machine.a_thread_died_unexpectedly.is_set():
        raise SystemExit(1)
