"""The Tk machine: widgets, bindings, events, and Core commands."""

import tkinter
from queue import Empty
from tkinter import ttk


COLORS = {
    "app": "#081522",
    "top": "#0C1D2E",
    "panel": "#102438",
    "control": "#182E45",
    "editor": "#0C1925",
    "border": "#29577F",
    "divider": "#1A3A55",
    "primary-text": "#E8EEF7",
    "secondary-text": "#9FB4CC",
    "muted-text": "#7289A1",
    "accent-blue": "#4C9BFF",
    "accent-purple": "#A66BFF",
    "accent-green": "#65D18A",
    "row-controls": "#0C1D2E",
    "row-controls-hover": "#182E45",
    "row-controls-text": "#9FB4CC",
}

g = {
    "root": None,
    "closing": False,
    "rendering-text": False,
    "rendering-history": False,
    "selecting-tab": False,
    "text-debounce-ids": {},
    "scroll-save-ids": {},
    "outgoing-events": None,
    "incoming-commands": None,
}

widgets = {}
tab_widgets = {}
row_widgets = {}
panel_widgets = {}
position_widgets = {}


def build_today_window():
    g["root"] = tkinter.Tk()
    g["root"].title("Today")
    g["root"].minsize(700, 500)
    g["root"].geometry("1100x760")
    g["root"].configure(background=COLORS["app"])
    g["root"].protocol("WM_DELETE_WINDOW", handle_when_user_requests_window_close)
    g["root"].bind("<<CoreMailAvailable>>", handle_when_core_mail_arrives)

    style = ttk.Style(g["root"])
    style.theme_use("clam")
    g["root"].option_add("*TCombobox*Listbox.background", COLORS["control"])
    g["root"].option_add("*TCombobox*Listbox.foreground", COLORS["primary-text"])
    g["root"].option_add("*TCombobox*Listbox.selectBackground", COLORS["accent-blue"])
    g["root"].option_add("*TCombobox*Listbox.selectForeground", COLORS["primary-text"])
    style.configure("Page.TNotebook", background=COLORS["app"], borderwidth=0)
    style.configure(
        "Page.TNotebook.Tab",
        background=COLORS["top"],
        foreground=COLORS["secondary-text"],
        padding=(8, 5),
    )
    style.map(
        "Page.TNotebook.Tab",
        background=[("selected", COLORS["control"]), ("active", COLORS["panel"])],
        foreground=[("selected", COLORS["primary-text"]), ("active", COLORS["primary-text"])],
    )
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["primary-text"])
    style.configure(
        "PanelTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["primary-text"],
        font=("TkDefaultFont", 10, "bold"),
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=COLORS["control"],
        background=COLORS["control"],
        foreground=COLORS["primary-text"],
        arrowcolor=COLORS["secondary-text"],
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", COLORS["control"])],
        foreground=[("readonly", COLORS["primary-text"])],
    )
    style.configure(
        "Page.TPanedwindow",
        background=COLORS["divider"],
        sashwidth=6,
        relief="flat",
    )
    style.configure("Page.TPanedwindow.Sash", background=COLORS["divider"])
    style.map(
        "Page.TPanedwindow.Sash",
        background=[("active", COLORS["border"])],
    )

    g["root"].columnconfigure(0, weight=1)
    g["root"].rowconfigure(1, weight=1)

    top = tkinter.Frame(g["root"], background=COLORS["top"], padx=12, pady=10)
    top.grid(row=0, column=0, sticky="ew")
    make_day_navigation_button(top, "<", handle_when_user_clicks_previous_day_button)
    widgets["date"] = tkinter.Label(
        top,
        background=COLORS["top"],
        foreground=COLORS["primary-text"],
        font=("TkDefaultFont", 18, "bold"),
        width=10,
        anchor="center",
    )
    widgets["date"].pack(side="left", padx=2)
    make_day_navigation_button(top, "今", handle_when_user_clicks_today_button)
    make_day_navigation_button(top, ">", handle_when_user_clicks_next_day_button)

    widgets["tabs"] = ttk.Notebook(g["root"], style="Page.TNotebook")
    widgets["tabs"].grid(row=1, column=0, sticky="nsew")
    widgets["tabs"].bind("<<NotebookTabChanged>>", handle_when_user_selects_tab)
    widgets["tabs"].bind("<Double-1>", handle_when_notebook_is_double_clicked, add="+")

    widgets["status"] = tkinter.Label(
        g["root"],
        text="Ready.",
        anchor="w",
        background=COLORS["top"],
        foreground=COLORS["secondary-text"],
        padx=7,
        pady=3,
    )
    widgets["status"].grid(row=2, column=0, sticky="ew")


def handle_when_text_widget_changes(event, panel_id):
    event.widget.edit_modified(False)
    if g["rendering-text"]:
        return
    g["outgoing-events"].put(
        {
            "type": "TEXT_CHANGED",
            "panel-id": panel_id,
            "text": event.widget.get("1.0", "end-1c"),
        }
    )
    schedule_text_debounce_for_panel(panel_id)


def handle_when_user_selects_panel_for_empty_position(position_id):
    panel_id = position_widgets[position_id]["choice"].get()
    if panel_id == "":
        return
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put(
        {"type": "HOST_PANEL", "position-id": position_id, "panel-id": panel_id}
    )


def make_day_navigation_button(parent, text, command):
    tkinter.Button(
        parent,
        text=text,
        background=COLORS["control"],
        foreground=COLORS["secondary-text"],
        activebackground=COLORS["divider"],
        activeforeground=COLORS["primary-text"],
        relief="flat",
        borderwidth=0,
        padx=7,
        pady=3,
        command=command,
    ).pack(side="left")


def handle_when_user_clicks_previous_day_button():
    send_text_debounce_if_one_is_waiting()
    send_tab_scroll_position_if_one_is_waiting()
    g["outgoing-events"].put({"type": "SELECT_PREVIOUS_DAY"})


def handle_when_user_clicks_next_day_button():
    send_text_debounce_if_one_is_waiting()
    send_tab_scroll_position_if_one_is_waiting()
    g["outgoing-events"].put({"type": "SELECT_NEXT_DAY"})


def handle_when_user_clicks_today_button():
    send_text_debounce_if_one_is_waiting()
    send_tab_scroll_position_if_one_is_waiting()
    g["outgoing-events"].put({"type": "SELECT_TODAY"})


def handle_when_user_clicks_unhost_panel_button(position_id):
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put({"type": "UNHOST_PANEL", "position-id": position_id})


def handle_when_user_selects_tab(event):
    if g["selecting-tab"]:
        return
    page = event.widget.select()
    if page == str(widgets["plus-tab"]):
        g["outgoing-events"].put({"type": "CREATE_TAB"})
        return
    for tab_id, tab in tab_widgets.items():
        if str(tab["page"]) == page:
            g["outgoing-events"].put({"type": "SELECT_TAB", "tab-id": tab_id})
            g["root"].after_idle(update_global_status_from_visible_whiteboard)
            return


def handle_when_user_clicks_move_row_button(tab_id, row_id, direction):
    g["outgoing-events"].put(
        {"type": "MOVE_ROW", "tab-id": tab_id, "row-id": row_id, "direction": direction}
    )


def handle_when_user_clicks_add_row_button(tab_id):
    g["outgoing-events"].put({"type": "ADD_ROW", "tab-id": tab_id})


def handle_when_user_clicks_delete_row_button(tab_id, row_id):
    g["outgoing-events"].put({"type": "DELETE_ROW", "tab-id": tab_id, "row-id": row_id})


def handle_when_user_clicks_set_row_column_count_button(row_id, column_count):
    g["outgoing-events"].put(
        {"type": "SET_ROW_COLUMN_COUNT", "row-id": row_id, "column-count": column_count}
    )


def handle_when_notebook_is_double_clicked(event):
    notebook = widgets["tabs"]
    if notebook.identify(event.x, event.y) != "label":
        return
    try:
        page = notebook.tabs()[notebook.index(f"@{event.x},{event.y}")]
    except tkinter.TclError:
        return
    if page == str(widgets["plus-tab"]):
        return "break"
    for tab_id, tab in tab_widgets.items():
        if page == str(tab["page"]):
            open_tab_editor(tab_id)
            return "break"


def open_tab_editor(tab_id):
    dialog = tkinter.Toplevel(g["root"])
    dialog.title("Edit Tab")
    dialog.configure(background=COLORS["panel"])
    dialog.transient(g["root"])
    dialog.resizable(False, False)
    tkinter.Label(
        dialog,
        text="Tab name:",
        background=COLORS["panel"],
        foreground=COLORS["primary-text"],
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 4))
    label = tkinter.StringVar(value=widgets["tabs"].tab(tab_widgets[tab_id]["page"], "text"))
    entry = tkinter.Entry(
        dialog,
        textvariable=label,
        background=COLORS["editor"],
        foreground=COLORS["primary-text"],
        insertbackground=COLORS["primary-text"],
        relief="solid",
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent-blue"],
        width=30,
    )
    entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))

    def handle_when_tab_rename_is_confirmed():
        if label.get().strip():
            g["outgoing-events"].put(
                {"type": "RENAME_TAB", "tab-id": tab_id, "label": label.get().strip()}
            )
            dialog.destroy()

    def handle_when_tab_delete_is_confirmed():
        g["outgoing-events"].put({"type": "DELETE_TAB", "tab-id": tab_id})
        dialog.destroy()

    rename_button = tkinter.Button(
        dialog,
        text="Rename",
        command=handle_when_tab_rename_is_confirmed,
    )
    rename_button.grid(row=2, column=0, padx=(12, 4), pady=(0, 12))
    delete_button = tkinter.Button(dialog, text="Delete", command=handle_when_tab_delete_is_confirmed)
    delete_button.grid(row=2, column=1, padx=4, pady=(0, 12))
    if len(tab_widgets) == 1:
        delete_button.configure(state="disabled")
    tkinter.Button(dialog, text="Cancel", command=dialog.destroy).grid(
        row=2, column=2, padx=(4, 12), pady=(0, 12)
    )
    entry.focus_set()
    entry.selection_range(0, "end")
    dialog.bind("<Return>", lambda event: handle_when_tab_rename_is_confirmed())
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    dialog.grab_set()


def handle_when_tab_canvas_resizes(event, tab_id):
    tab_widgets[tab_id]["canvas"].itemconfigure(tab_widgets[tab_id]["scroll-window"], width=event.width)


def handle_when_tab_workspace_changes(event, tab_id):
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    tab["scroll-geometry-generation"] += 1
    canvas = tab["canvas"]
    canvas.configure(scrollregion=canvas.bbox("all"))
    if tab["scroll-restoration-pending"]:
        schedule_tab_scroll_restoration(tab_id)


def handle_when_tab_scrolls(tab_id, first, last):
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    tab["scrollbar"].set(first, last)
    if tab["applying-scroll-position"]:
        return
    if tab_id in g["scroll-save-ids"]:
        g["root"].after_cancel(g["scroll-save-ids"][tab_id])
    g["scroll-save-ids"][tab_id] = g["root"].after(
        250,
        lambda: send_tab_scroll_position(tab_id),
    )


def send_tab_scroll_position(tab_id):
    g["scroll-save-ids"].pop(tab_id, None)
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    g["outgoing-events"].put(
        {
            "type": "SET_TAB_SCROLL_POSITION",
            "tab-id": tab_id,
            "scroll-position": tab["canvas"].yview()[0],
        }
    )


def send_tab_scroll_position_if_one_is_waiting():
    for tab_id, after_id in list(g["scroll-save-ids"].items()):
        g["root"].after_cancel(after_id)
        send_tab_scroll_position(tab_id)


def apply_tab_scroll_position(tab_id):
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    tab["scroll-restoration-pending"] = True
    schedule_tab_scroll_restoration(tab_id)


def schedule_tab_scroll_restoration(tab_id):
    tab = tab_widgets.get(tab_id)
    if tab is None or tab["scroll-restoration-id"] is not None:
        return
    generation = tab["scroll-geometry-generation"]
    tab["scroll-restoration-id"] = g["root"].after_idle(
        lambda: restore_tab_scroll_position_after_layout(tab_id, generation)
    )


def restore_tab_scroll_position_after_layout(tab_id, generation):
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    tab["scroll-restoration-id"] = None
    if generation != tab["scroll-geometry-generation"]:
        schedule_tab_scroll_restoration(tab_id)
        return
    tab["applying-scroll-position"] = True
    tab["canvas"].configure(scrollregion=tab["canvas"].bbox("all"))
    tab["canvas"].yview_moveto(tab["scroll-position"])
    g["root"].after_idle(lambda: finish_tab_scroll_restoration(tab_id, generation))


def finish_tab_scroll_restoration(tab_id, generation):
    tab = tab_widgets.get(tab_id)
    if tab is None:
        return
    if generation != tab["scroll-geometry-generation"]:
        schedule_tab_scroll_restoration(tab_id)
        return
    tab["applying-scroll-position"] = False
    tab["scroll-restoration-pending"] = False


def handle_when_user_releases_pane_sash(event, row_id):
    pane = row_widgets[row_id]["pane"]
    width = pane.winfo_width()
    if width <= 1:
        return
    sash_proportions = [
        pane.sashpos(index) / width
        for index in range(len(row_widgets[row_id]["sash-proportions"]))
    ]
    g["outgoing-events"].put(
        {"type": "SET_SASH_PROPORTIONS", "row-id": row_id, "sash-proportions": sash_proportions}
    )


def handle_when_user_releases_row_sash(event, tab_id):
    for row_id in tab_widgets[tab_id]["row-ids"]:
        g["outgoing-events"].put(
            {
                "type": "SET_ROW_HEIGHT",
                "row-id": row_id,
                "height": row_widgets[row_id]["frame"].winfo_height(),
            }
        )


def handle_when_user_moves_history_cursor(value, panel_id):
    if g["rendering-history"]:
        return
    g["outgoing-events"].put(
        {
            "type": "HISTORY_CURSOR_CHANGED",
            "panel-id": panel_id,
            "history-cursor": int(float(value)),
        }
    )


def handle_when_user_clicks_snapshot_button(panel_id):
    g["outgoing-events"].put({"type": "SNAPSHOT", "panel-id": panel_id})


def schedule_text_debounce_for_panel(panel_id):
    if panel_id in g["text-debounce-ids"]:
        g["root"].after_cancel(g["text-debounce-ids"][panel_id])
    g["text-debounce-ids"][panel_id] = g["root"].after(
        1000,
        lambda: handle_when_text_debounce_expires(panel_id),
    )


def handle_when_text_debounce_expires(panel_id):
    g["text-debounce-ids"].pop(panel_id, None)
    g["outgoing-events"].put({"type": "TEXT_DEBOUNCE", "panel-id": panel_id})


def send_text_debounce_if_one_is_waiting():
    for panel_id, after_id in list(g["text-debounce-ids"].items()):
        g["root"].after_cancel(after_id)
        handle_when_text_debounce_expires(panel_id)


def handle_when_user_requests_window_close():
    if g["closing"]:
        return

    g["closing"] = True
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put({"type": "SHUTDOWN"})


def enqueue_core_command_and_wake_tk(command):
    g["incoming-commands"].put(command)
    g["root"].event_generate("<<CoreMailAvailable>>", when="tail")


def realize_core_command(command):
    if command["type"] == "RENDER_TODAY":
        widgets["date"].configure(text=command["today-id"])
        build_today_tabs(command)
        return

    if command["type"] == "RENDER_POSITION":
        clear_position_host(command["position-id"])
        if command["panel-id"] is None:
            render_empty_position(command)
        else:
            render_hosted_panel(command)
        return

    if command["type"] == "RENDER_WHITEBOARD_VIEW":
        render_whiteboard_view(command)
        return

    if command["type"] == "SET_WHITEBOARD_HISTORY_CURSOR":
        render_whiteboard_history_controls(command)
        return

    if command["type"] == "SET_PANEL_LABEL":
        for panel in panel_widgets[command["panel-id"]]:
            panel["label"].configure(text=command["panel-label"])
        return

    if command["type"] == "SET_TAB_LABEL":
        widgets["tabs"].tab(tab_widgets[command["tab-id"]]["page"], text=command["tab-label"])
        return

    if command["type"] == "SET_SELECTED_TAB":
        select_tab(command["tab-id"])
        return

    if command["type"] == "SET_ROW_HEIGHT":
        row_widgets[command["row-id"]]["height"] = command["height"]
        apply_tab_row_heights(row_widgets[command["row-id"]]["tab-id"])
        return

    if command["type"] == "SET_SASH_PROPORTIONS":
        row_widgets[command["row-id"]]["sash-proportions"] = command["sash-proportions"]
        apply_row_sash_proportions(command["row-id"])
        return

    if command["type"] == "SET_TAB_SCROLL_POSITION":
        tab_widgets[command["tab-id"]]["scroll-position"] = command["scroll-position"]
        apply_tab_scroll_position(command["tab-id"])
        return

    if command["type"] == "SHUTDOWN_COMPLETE":
        g["root"].destroy()


def build_today_tabs(command):
    for after_id in g["scroll-save-ids"].values():
        g["root"].after_cancel(after_id)
    g["scroll-save-ids"].clear()
    for child in widgets["tabs"].winfo_children():
        child.destroy()
    tab_widgets.clear()
    row_widgets.clear()
    panel_widgets.clear()
    position_widgets.clear()

    for tab in command["tabs"]:
        page = tkinter.Frame(widgets["tabs"], background=COLORS["app"])
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        widgets["tabs"].add(page, text=tab["tab-label"])
        canvas = tkinter.Canvas(
            page,
            background=COLORS["app"],
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = tkinter.Scrollbar(
            page,
            orient="vertical",
            command=canvas.yview,
            background=COLORS["control"],
            activebackground=COLORS["border"],
            troughcolor=COLORS["top"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        workspace = tkinter.Frame(canvas, background=COLORS["app"], padx=12, pady=12)
        scroll_window = canvas.create_window((0, 0), window=workspace, anchor="nw")
        tab_widgets[tab["tab-id"]] = {
            "page": page,
            "canvas": canvas,
            "scrollbar": scrollbar,
            "scroll-window": scroll_window,
            "scroll-position": tab["scroll-position"],
            "applying-scroll-position": True,
            "scroll-geometry-generation": 0,
            "scroll-restoration-id": None,
            "scroll-restoration-pending": True,
            "row-ids": [],
        }
        canvas.configure(
            yscrollcommand=lambda first, last, tab_id=tab["tab-id"]: handle_when_tab_scrolls(
                tab_id, first, last
            )
        )
        canvas.bind(
            "<Configure>",
            lambda event, tab_id=tab["tab-id"]: handle_when_tab_canvas_resizes(event, tab_id),
        )
        workspace.bind(
            "<Configure>",
            lambda event, tab_id=tab["tab-id"]: handle_when_tab_workspace_changes(event, tab_id),
        )
        build_tab_workspace(tab, workspace)
        g["root"].after_idle(lambda tab_id=tab["tab-id"]: apply_tab_scroll_position(tab_id))

    widgets["plus-tab"] = tkinter.Frame(widgets["tabs"], background=COLORS["app"])
    widgets["tabs"].add(widgets["plus-tab"], text="+")
    select_tab(command["selected-tab-id"])


def select_tab(tab_id):
    g["selecting-tab"] = True
    widgets["tabs"].select(tab_widgets[tab_id]["page"])
    g["root"].after_idle(handle_after_selecting_tab)


def handle_after_selecting_tab():
    g["selecting-tab"] = False
    update_global_status_from_visible_whiteboard()


def make_row_rail_button(button):
    tkinter.Button(
        button["parent"],
        text=button["text"],
        width=1,
        padx=0,
        pady=1,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        background=COLORS["row-controls"],
        foreground=COLORS["row-controls-text"],
        activebackground=COLORS["row-controls-hover"],
        activeforeground="#E5EBF1",
        command=button.get("command"),
    ).grid(row=button["row"], column=0, pady=button.get("pady", 1))


def get_panel_accent(panel_id):
    if panel_id.endswith("b"):
        return COLORS["accent-purple"]
    return COLORS["accent-blue"]


def build_tab_workspace(command, workspace):
    rows_container = tkinter.Frame(workspace, background=COLORS["app"])
    rows_container.pack(fill="x", expand=False)
    tab_widgets[command["tab-id"]]["rows-container"] = rows_container

    for row_number, row in enumerate(command["rows"]):
        row_frame = tkinter.Frame(rows_container, height=row["height"], background=COLORS["app"])
        row_frame.pack(fill="x", expand=False)
        row_frame.grid_propagate(False)
        tab_widgets[command["tab-id"]]["row-ids"].append(row["row-id"])
        controls = tkinter.Frame(
            row_frame,
            width=24,
            background=COLORS["row-controls"],
        )
        controls.grid(row=0, column=0, sticky="ns", padx=(0, 4))
        controls.grid_propagate(False)
        make_row_rail_button(
            {
                "parent": controls,
                "text": "↑",
                "row": 0,
                "command": lambda tab_id=command["tab-id"], row_id=row["row-id"]: handle_when_user_clicks_move_row_button(
                    tab_id, row_id, -1
                ),
            }
        )
        for column_count in range(1, 4):
            make_row_rail_button(
                {
                    "parent": controls,
                    "text": str(column_count),
                    "row": column_count,
                    "command": lambda row_id=row["row-id"], column_count=column_count: handle_when_user_clicks_set_row_column_count_button(
                        row_id, column_count
                    ),
                }
            )
        make_row_rail_button(
            {
                "parent": controls,
                "text": "x",
                "row": 4,
                "pady": (6, 1),
                "command": lambda tab_id=command["tab-id"], row_id=row["row-id"]: handle_when_user_clicks_delete_row_button(
                    tab_id, row_id
                ),
            }
        )
        make_row_rail_button(
            {
                "parent": controls,
                "text": "↓",
                "row": 5,
                "pady": (6, 1),
                "command": lambda tab_id=command["tab-id"], row_id=row["row-id"]: handle_when_user_clicks_move_row_button(
                    tab_id, row_id, 1
                ),
            }
        )
        if row_number == len(command["rows"]) - 1:
            make_row_rail_button(
                {
                    "parent": controls,
                    "text": "+",
                    "row": 6,
                    "pady": (6, 1),
                    "command": lambda tab_id=command["tab-id"]: handle_when_user_clicks_add_row_button(tab_id),
                }
            )
        has_multiple_positions = len(row["positions"]) > 1
        if has_multiple_positions:
            row_pane = ttk.Panedwindow(row_frame, orient="horizontal", style="Page.TPanedwindow")
        else:
            row_pane = tkinter.Frame(row_frame, background=COLORS["app"])
        row_pane.grid(row=0, column=1, sticky="nsew")
        row_frame.columnconfigure(1, weight=1)
        row_frame.rowconfigure(0, weight=1)
        if has_multiple_positions:
            row_pane.bind(
                "<ButtonRelease-1>",
                lambda event, row_id=row["row-id"]: handle_when_user_releases_pane_sash(event, row_id),
            )
        row_widgets[row["row-id"]] = {
            "tab-id": command["tab-id"],
            "frame": row_frame,
            "pane": row_pane,
            "height": row["height"],
            "sash-proportions": row["sash-proportions"],
        }

        for column_number, position in enumerate(row["positions"]):
            card_border = tkinter.Frame(row_pane, background=COLORS["border"])
            if has_multiple_positions:
                row_pane.add(card_border, weight=1)
            else:
                card_border.pack(fill="both", expand=True)
            host = ttk.Frame(
                card_border,
                style="Panel.TFrame",
                padding=16,
            )
            host.pack(fill="both", expand=True, padx=1, pady=1)
            position_widgets[position["position-id"]] = {
                "host": host,
                "panel-id": None,
                "panel-widgets": None,
            }
            if position["panel-id"] is None:
                render_empty_position(position)
            else:
                render_hosted_panel(position)

        build_row_resize_handle(rows_container, row["row-id"])

    g["root"].after_idle(lambda tab_id=command["tab-id"]: apply_tab_geometry(tab_id))


def apply_tab_geometry(tab_id):
    apply_tab_row_heights(tab_id)
    for row_id in tab_widgets[tab_id]["row-ids"]:
        apply_row_sash_proportions(row_id)


def apply_tab_row_heights(tab_id):
    for row_id in tab_widgets[tab_id]["row-ids"]:
        row_widgets[row_id]["frame"].configure(height=row_widgets[row_id]["height"])


def apply_row_sash_proportions(row_id):
    pane = row_widgets[row_id]["pane"]
    if not row_widgets[row_id]["sash-proportions"]:
        return
    if pane.winfo_width() <= 1:
        return
    for index, proportion in enumerate(row_widgets[row_id]["sash-proportions"]):
        pane.sashpos(index, int(pane.winfo_width() * proportion))


def build_row_resize_handle(parent, row_id):
    resize_handle = tkinter.Frame(
        parent,
        height=6,
        background=COLORS["divider"],
        cursor="sb_v_double_arrow",
    )
    resize_handle.pack(fill="x", expand=False)
    drag = {"start-y": None, "start-height": None}

    def handle_when_row_resize_starts(event):
        drag["start-y"] = event.y_root
        drag["start-height"] = row_widgets[row_id]["frame"].winfo_height()

    def handle_when_row_resize_moves(event):
        if drag["start-y"] is None:
            return
        row_widgets[row_id]["frame"].configure(
            height=max(80, drag["start-height"] + event.y_root - drag["start-y"])
        )

    def handle_when_row_resize_ends(event):
        if drag["start-y"] is None:
            return
        g["outgoing-events"].put(
            {
                "type": "SET_ROW_HEIGHT",
                "row-id": row_id,
                "height": row_widgets[row_id]["frame"].winfo_height(),
            }
        )
        drag["start-y"] = None

    resize_handle.bind("<ButtonPress-1>", handle_when_row_resize_starts)
    resize_handle.bind("<B1-Motion>", handle_when_row_resize_moves)
    resize_handle.bind("<ButtonRelease-1>", handle_when_row_resize_ends)


def clear_position_host(position_id):
    position = position_widgets[position_id]
    if position["panel-id"] is not None:
        panel_widgets[position["panel-id"]].remove(position["panel-widgets"])
        if not panel_widgets[position["panel-id"]]:
            panel_widgets.pop(position["panel-id"])
    for child in position["host"].winfo_children():
        child.destroy()
    position["panel-id"] = None
    position["panel-widgets"] = None


def render_empty_position(command):
    position = position_widgets[command["position-id"]]
    host = position["host"]
    host.columnconfigure(0, weight=1)
    choice = ttk.Combobox(
        host,
        values=command["available-panel-ids"],
        state="readonly",
        style="Dark.TCombobox",
    )
    choice.grid(row=0, column=0, sticky="ew")
    choice.set("Choose existing panel")
    choice.bind(
        "<<ComboboxSelected>>",
        lambda event, position_id=command["position-id"]: handle_when_user_selects_panel_for_empty_position(
            position_id
        ),
    )
    position["choice"] = choice


def render_hosted_panel(command):
    position = position_widgets[command["position-id"]]
    host = position["host"]
    position["panel-id"] = command["panel-id"]
    host.columnconfigure(1, weight=1)
    host.rowconfigure(1, weight=1)

    tkinter.Frame(
        host,
        background=get_panel_accent(command["panel-id"]),
        width=5,
    ).grid(row=0, column=0, sticky="ns", padx=(0, 12))
    label = ttk.Label(host, text=command["panel-label"], style="PanelTitle.TLabel")
    label.grid(row=0, column=1, sticky="w")
    unhost_button = tkinter.Button(
        host,
        text="x",
        background=COLORS["control"],
        foreground=COLORS["secondary-text"],
        activebackground=COLORS["divider"],
        activeforeground=COLORS["primary-text"],
        relief="flat",
        borderwidth=0,
        width=2,
        padx=2,
        pady=3,
        command=lambda position_id=command["position-id"]: handle_when_user_clicks_unhost_panel_button(
            position_id
        ),
    )
    unhost_button.grid(row=0, column=2, sticky="e")
    controls = tkinter.Frame(host, background=COLORS["panel"])
    controls.grid(row=1, column=2, sticky="ns", padx=(12, 0), pady=(14, 0))
    controls.rowconfigure(1, weight=1)
    snapshot_button = tkinter.Button(
        controls,
        text="Snapshot",
        background=COLORS["accent-blue"],
        foreground=COLORS["primary-text"],
        activebackground="#347FD8",
        activeforeground=COLORS["primary-text"],
        relief="flat",
        borderwidth=0,
        padx=14,
        pady=6,
        command=lambda panel_id=command["panel-id"]: handle_when_user_clicks_snapshot_button(panel_id),
    )
    snapshot_button.grid(row=0, column=0, sticky="ew")
    text = tkinter.Text(
        host,
        height=10,
        wrap="word",
        background=COLORS["editor"],
        foreground=COLORS["primary-text"],
        insertbackground=COLORS["primary-text"],
        selectbackground=COLORS["accent-blue"],
        selectforeground=COLORS["primary-text"],
        relief="solid",
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent-blue"],
    )
    text.grid(row=1, column=1, sticky="nsew", pady=(14, 0))
    text.bind(
        "<<Modified>>",
        lambda event, panel_id=command["panel-id"]: handle_when_text_widget_changes(event, panel_id),
    )
    history_slider = tkinter.Scale(
        controls,
        from_=0,
        to=0,
        orient="vertical",
        showvalue=False,
        command=lambda value, panel_id=command["panel-id"]: handle_when_user_moves_history_cursor(
            value, panel_id
        ),
        background=COLORS["panel"],
        foreground=COLORS["secondary-text"],
        troughcolor=COLORS["control"],
        activebackground=COLORS["accent-blue"],
        highlightthickness=0,
        borderwidth=0,
        sliderrelief="flat",
    )
    history_slider.grid(row=1, column=0, sticky="ns", pady=(10, 0))

    g["rendering-text"] = True
    text.insert("1.0", command["panel-text"])
    text.edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    panel = {
        "label": label,
        "text": text,
        "history-slider": history_slider,
        "history-status": command["history-status"],
    }
    position["panel-widgets"] = panel
    panel_widgets.setdefault(command["panel-id"], []).append(panel)
    render_whiteboard_history_controls(command)


def handle_after_rendering_whiteboard_text():
    g["rendering-text"] = False


def render_whiteboard_view(command):
    g["rendering-text"] = True
    for panel in panel_widgets[command["panel-id"]]:
        panel["text"].delete("1.0", "end")
        panel["text"].insert("1.0", command["panel-text"])
        panel["text"].edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    render_whiteboard_history_controls(command)


def render_whiteboard_history_controls(command):
    g["rendering-history"] = True
    for panel in panel_widgets[command["panel-id"]]:
        panel["history-slider"].configure(to=command["history-size"])
        panel["history-slider"].set(command["history-cursor"])
        panel["history-status"] = command["history-status"]
    g["rendering-history"] = False
    g["root"].after_idle(update_global_status_from_visible_whiteboard)


def update_global_status_from_visible_whiteboard():
    for panels in panel_widgets.values():
        for panel in panels:
            if panel["text"].winfo_ismapped():
                widgets["status"].configure(text=panel["history-status"])
                return


def handle_when_core_mail_arrives(event):
    try:
        while True:
            command = g["incoming-commands"].get_nowait()
            print("Core -> Tk:", command)
            realize_core_command(command)
            if command["type"] == "SHUTDOWN_COMPLETE":
                return
    except Empty:
        pass


def run_tk_machine():
    g["root"].mainloop()
