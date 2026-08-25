"""Today combined model: logical workspace model plus Tk realization.

This experiment deliberately has three visible layers:

    logical date model -> reducer/event stage -> Tk reconciliation

The logical model knows nothing about Tkinter.  A position is a logical
address ``(tab_id, row_number, column_number)``.  A date owns its complete
workspace layout and its position-to-panel mapping.  Panel identities and
panel state are separate from positions and dates.
"""

from collections import deque
from copy import deepcopy
from datetime import date, timedelta
import tkinter as tk
import uuid
from tkinter import ttk


TODO = "TODO"
JOURNAL = "JOURNAL"
EMPTY = "EMPTY"

SELECT_PREVIOUS_DAY = "SELECT_PREVIOUS_DAY"
SELECT_NEXT_DAY = "SELECT_NEXT_DAY"
SELECT_TODAY = "SELECT_TODAY"
SECOND_ELAPSED = "SECOND_ELAPSED"
EDIT_ORIENTATION = "EDIT_ORIENTATION"
SELECT_TAB = "SELECT_TAB"
SET_PANE_COUNT = "SET_PANE_COUNT"
SET_SASH_PROPORTIONS = "SET_SASH_PROPORTIONS"
SET_ROW_HEIGHT = "SET_ROW_HEIGHT"
REPLACE_PANEL = "REPLACE_PANEL"
ADD_ROW = "ADD_ROW"
DELETE_ROW = "DELETE_ROW"
ADD_TAB = "ADD_TAB"
RENAME_TAB = "RENAME_TAB"
DELETE_TAB = "DELETE_TAB"
TOGGLE_TODO = "TOGGLE_TODO"
EDIT_JOURNAL = "EDIT_JOURNAL"


g = {
    "root": None,
    "window": None,
    "running": True,
    "processing_scheduled": False,
    "selected_day": date.today(),
    "heartbeat_count": 0,
    "orientation_text": "orientation",
}

reg = {"event": None, "model": None, "panel_id": None}

COLORS = {
    "top": "#081525",
    "middle": "#10243A",
    "panel": "#F3F6F8",
    "panel_text": "#162332",
    "separator": "#35516B",
    "status": "#0B1828",
    "status_text": "#D7E2EC",
}

PANEL_TITLES = {TODO: "Todo", JOURNAL: "Journal", EMPTY: "Empty Panel"}

# The application world is visible and inspectable.
day_models = {}
panels = {}
event_queue = deque()
widgets = {
    "notebook": None,
    "plus_frame": None,
    "top": {},
    "status": None,
    "tabs": {},
    "positions": {},
    "panels": {},
}


# ---------------------------------------------------------------------------
# Logical model


def make_panel(day, panel_kind):
    """Create one semantic panel record with globally unique identity."""
    panel_id = f"panel-{uuid.uuid4().hex[:10]}"
    panels[panel_id] = {
        "panel_id": panel_id,
        "panel_type": panel_kind,
        "state": {
            "items": [{"text": f"Try the event route on {day.isoformat()}", "done": False}]
            if panel_kind == TODO
            else [],
            "text": f"Write a thought for {day.isoformat()}." if panel_kind == JOURNAL else "",
        },
    }
    return panel_id


def make_row(pane_count=1):
    """Create one logical row with independent geometry."""
    return {
        "height": 190,
        "pane_count": pane_count,
        "sash_proportions": [(index + 1) / pane_count for index in range(pane_count - 1)],
    }


def make_tab(title):
    """Create a logical tab with a stable identity separate from its title."""
    return {
        "tab_id": f"tab-{uuid.uuid4().hex[:10]}",
        "title": title,
        "rows": [make_row(2), make_row(1)],
    }


def make_day_model(day):
    """Create a complete independent layout for a date."""
    tab_a = make_tab("Tab A")
    tab_b = make_tab("Tab B")
    tab_b["rows"] = [make_row(1), make_row(2)]
    model = {
        "date": day,
        "tabs": [tab_a, tab_b],
        "selected_tab_id": tab_a["tab_id"],
        "panel_at": {},
    }
    ensure_model_positions(model)
    return model


def ensure_day_model(day):
    """Return the one complete logical workspace owned by a date."""
    if day not in day_models:
        day_models[day] = make_day_model(day)
    return day_models[day]


def current_model():
    """Return the logical model for the currently selected date."""
    return ensure_day_model(g["selected_day"])


def iter_tab_positions(model, tab_id):
    """Yield all logical position addresses in one tab."""
    tab = next(tab for tab in model["tabs"] if tab["tab_id"] == tab_id)
    for row_number, row in enumerate(tab["rows"], start=1):
        for column_number in range(1, row["pane_count"] + 1):
            yield (tab_id, row_number, column_number)


def iter_positions(model):
    """Yield all logical position addresses in tab order."""
    for tab in model["tabs"]:
        yield from iter_tab_positions(model, tab["tab_id"])


def ensure_model_positions(model):
    """Ensure every logical position maps to one semantic panel identity."""
    existing = set(model["panel_at"])
    for position in iter_positions(model):
        if position in model["panel_at"]:
            continue
        panel_kind = TODO if not existing else JOURNAL if len(existing) == 1 else EMPTY
        model["panel_at"][position] = make_panel(model["date"], panel_kind)
        existing.add(position)
    for position in list(model["panel_at"]):
        if position not in set(iter_positions(model)):
            del model["panel_at"][position]


def find_tab(model, tab_id):
    """Find a logical tab by identity, never by title."""
    return next((tab for tab in model["tabs"] if tab["tab_id"] == tab_id), None)


def next_tab_title(model):
    """Return the next unused human-facing tab title."""
    used_titles = {tab["title"] for tab in model["tabs"]}
    index = 1
    while f"Tab {index}" in used_titles:
        index += 1
    return f"Tab {index}"


def reduce_model(model, event):
    """Return a changed logical model and a list of realization effects.

    This function is intentionally Tk-free.  Its input and output can be
    tested without creating a root window or any widgets.
    """
    next_model = deepcopy(model)
    event_type = event["type"]
    effects = []
    if event_type == SELECT_TAB:
        if find_tab(next_model, event["tab_id"]) and next_model["selected_tab_id"] != event["tab_id"]:
            next_model["selected_tab_id"] = event["tab_id"]
            effects.append("RECONCILE_WORKSPACE")
    elif event_type == SET_PANE_COUNT:
        tab = find_tab(next_model, event["tab_id"])
        row_number = event["row_number"]
        if tab and 1 <= row_number <= len(tab["rows"]):
            row = tab["rows"][row_number - 1]
            pane_count = max(1, min(3, int(event["pane_count"])))
            row["pane_count"] = pane_count
            row["sash_proportions"] = [(index + 1) / pane_count for index in range(pane_count - 1)]
            ensure_model_positions(next_model)
            effects.append("RECONCILE_WORKSPACE")
    elif event_type == ADD_ROW:
        tab = find_tab(next_model, event["tab_id"])
        if tab:
            tab["rows"].append(make_row(1))
            ensure_model_positions(next_model)
            effects.append("RECONCILE_WORKSPACE")
    elif event_type == ADD_TAB:
        tab = make_tab(next_tab_title(next_model))
        next_model["tabs"].append(tab)
        next_model["selected_tab_id"] = tab["tab_id"]
        ensure_model_positions(next_model)
        effects.append("RECONCILE_WORKSPACE")
    elif event_type == RENAME_TAB:
        tab = find_tab(next_model, event["tab_id"])
        title = event["title"].strip()
        if tab and title:
            tab["title"] = title
            effects.append("RECONCILE_WORKSPACE")
    elif event_type == DELETE_TAB:
        if len(next_model["tabs"]) > 1:
            deleted_tab_id = event["tab_id"]
            deleted_index = next((index for index, tab in enumerate(next_model["tabs"]) if tab["tab_id"] == deleted_tab_id), None)
            if deleted_index is not None:
                next_model["tabs"].pop(deleted_index)
                if next_model["selected_tab_id"] == deleted_tab_id:
                    replacement_index = min(deleted_index, len(next_model["tabs"]) - 1)
                    next_model["selected_tab_id"] = next_model["tabs"][replacement_index]["tab_id"]
                ensure_model_positions(next_model)
                effects.append("RECONCILE_WORKSPACE")
    elif event_type == SET_SASH_PROPORTIONS:
        tab = find_tab(next_model, event["tab_id"])
        row_number = event["row_number"]
        if tab and 1 <= row_number <= len(tab["rows"]):
            row = tab["rows"][row_number - 1]
            if len(event["proportions"]) == row["pane_count"] - 1:
                row["sash_proportions"] = list(event["proportions"])
    elif event_type == SET_ROW_HEIGHT:
        tab = find_tab(next_model, event["tab_id"])
        row_number = event["row_number"]
        if tab and 1 <= row_number <= len(tab["rows"]):
            tab["rows"][row_number - 1]["height"] = max(80, int(event["height"]))
    elif event_type == DELETE_ROW:
        tab = find_tab(next_model, event["tab_id"])
        row_number = event["row_number"]
        if tab and len(tab["rows"]) > 1 and 1 <= row_number <= len(tab["rows"]):
            tab["rows"].pop(row_number - 1)
            reindex_panel_positions_after_row_deletion(next_model, event["tab_id"], row_number)
            ensure_model_positions(next_model)
            effects.append("RECONCILE_WORKSPACE")
    elif event_type == REPLACE_PANEL:
        position = tuple(event["position"])
        if position in next_model["panel_at"]:
            next_model["panel_at"][position] = make_panel(next_model["date"], event["panel_type"])
            effects.append("RECONCILE_WORKSPACE")
    return next_model, effects


def reindex_panel_positions_after_row_deletion(model, tab_id, deleted_row_number):
    """Shift later logical rows upward while preserving their panel identities."""
    remapped = {}
    for position, panel_id in model["panel_at"].items():
        position_tab_id, row_number, column_number = position
        if position_tab_id != tab_id:
            remapped[position] = panel_id
        elif row_number < deleted_row_number:
            remapped[position] = panel_id
        elif row_number > deleted_row_number:
            remapped[(tab_id, row_number - 1, column_number)] = panel_id
    model["panel_at"] = remapped


def reduce_panel_event(panel_id, event):
    """Apply a semantic event to one panel record without touching Tk."""
    panel = panels[panel_id]
    if event["type"] == TOGGLE_TODO and panel["panel_type"] == TODO:
        panel["state"]["items"][0]["done"] = not panel["state"]["items"][0]["done"]
    elif event["type"] == EDIT_JOURNAL and panel["panel_type"] == JOURNAL:
        panel["state"]["text"] = event["text"]


def post_event(event):
    """Queue an application event for the controlled processing stage."""
    event_queue.append(event)
    request_processing()


def request_processing():
    """Schedule one event-processing pass."""
    if g["root"] is not None and not g["processing_scheduled"]:
        g["processing_scheduled"] = True
        g["root"].after_idle(process_events)


def process_events():
    """Reduce queued events, then reconcile the active logical model."""
    g["processing_scheduled"] = False
    reconcile = False
    while event_queue:
        event = event_queue.popleft()
        event_type = event["type"]
        if event_type in (SELECT_PREVIOUS_DAY, SELECT_NEXT_DAY, SELECT_TODAY):
            if event_type == SELECT_PREVIOUS_DAY:
                g["selected_day"] -= timedelta(days=1)
            elif event_type == SELECT_NEXT_DAY:
                g["selected_day"] += timedelta(days=1)
            else:
                g["selected_day"] = date.today()
            ensure_day_model(g["selected_day"])
            reconcile = True
        elif event_type == SECOND_ELAPSED:
            g["heartbeat_count"] += 1
        elif event_type == EDIT_ORIENTATION:
            g["orientation_text"] = event["text"]
        elif event_type in (TOGGLE_TODO, EDIT_JOURNAL):
            reduce_panel_event(event["panel_id"], event)
            reconcile = True
        else:
            old_model = current_model()
            new_model, effects = reduce_model(old_model, event)
            day_models[g["selected_day"]] = new_model
            reconcile = reconcile or "RECONCILE_WORKSPACE" in effects
    project_top_area()
    if reconcile:
        reconcile_workspace(current_model())
    if event_queue:
        request_processing()


# ---------------------------------------------------------------------------
# Tk realization and reconciliation


def position_label(position):
    """Return a human-readable logical position label."""
    _tab_id, row_number, column_number = position
    return f"row {row_number}, col {column_number}"


def reconcile_workspace(model):
    """Realize the logical model in Tk widgets.

    This first combined experiment intentionally rebuilds the visible
    workspace from the model at reconciliation boundaries.  The important
    seam is explicit: this function consumes model data and writes widgets;
    it does not decide application meaning or mutate the model.
    """
    notebook = widgets["notebook"]
    if notebook is None:
        return
    for child in notebook.winfo_children():
        child.destroy()
    widgets["tabs"].clear()
    widgets["positions"].clear()
    for tab in model["tabs"]:
        tab_frame = tk.Frame(notebook, background=COLORS["middle"])
        notebook.add(tab_frame, text=tab["title"])
        rows_frame = tk.Frame(tab_frame, background=COLORS["middle"])
        rows_frame.pack(fill="both", expand=True, padx=8, pady=8)
        widgets["tabs"][tab["tab_id"]] = {"frame": tab_frame, "rows_frame": rows_frame}
        for row_number, row in enumerate(tab["rows"], start=1):
            build_row(rows_frame, model, tab, row_number, row)
        ttk.Button(
            rows_frame,
            text="Add Row",
            command=lambda tab_id=tab["tab_id"]: post_event({"type": ADD_ROW, "tab_id": tab_id}),
        ).pack(pady=(6, 12))
    plus_frame = ttk.Frame(notebook)
    notebook.add(plus_frame, text="+")
    widgets["plus_frame"] = plus_frame
    selected_tab = model["selected_tab_id"]
    if selected_tab in widgets["tabs"]:
        notebook.select(widgets["tabs"][selected_tab]["frame"])


def build_row(parent, model, tab, row_number, row):
    """Realize one logical row and its logical positions."""
    row_frame = tk.Frame(parent, height=row["height"], background=COLORS["middle"])
    row_frame.pack(fill="x", expand=False)
    row_frame.pack_propagate(False)
    controls = tk.Frame(row_frame, width=34, background=COLORS["middle"])
    controls.pack(side="left", fill="y")
    for count in (1, 2, 3):
        ttk.Button(
            controls,
            text=str(count),
            width=2,
            command=lambda selected=count: post_event({
                "type": SET_PANE_COUNT,
                "tab_id": tab["tab_id"],
                "row_number": row_number,
                "pane_count": selected,
            }),
        ).pack(pady=1)
    ttk.Button(
        controls,
        text="x",
        width=2,
        command=lambda: post_event({"type": DELETE_ROW, "tab_id": tab["tab_id"], "row_number": row_number}),
    ).pack(pady=(6, 1))
    paned = ttk.Panedwindow(row_frame, orient="horizontal")
    paned.pack(side="left", fill="both", expand=True)
    for column_number in range(1, row["pane_count"] + 1):
        position = (tab["tab_id"], row_number, column_number)
        pane = ttk.Frame(paned)
        build_panel_host(pane, model, position)
        paned.add(pane, weight=1)
    paned.bind(
        "<ButtonRelease-1>",
        lambda _event: post_event({
            "type": SET_SASH_PROPORTIONS,
            "tab_id": tab["tab_id"],
            "row_number": row_number,
            "proportions": read_sash_proportions(paned, row["pane_count"]),
        }),
        add="+",
    )
    restore_sash_proportions(paned, row["sash_proportions"])
    build_row_resize_handle(parent, row_frame, tab["tab_id"], row_number, row["height"])


def build_row_resize_handle(parent, row_frame, tab_id, row_number, initial_height):
    """Realize the draggable boundary below one row."""
    resize_handle = tk.Frame(parent, height=6, background=COLORS["separator"], cursor="sb_v_double_arrow")
    resize_handle.pack(fill="x", expand=False)
    drag = {"start_y": None, "start_height": initial_height}

    def handle_when_row_resize_starts(event):
        drag["start_y"] = event.y_root
        drag["start_height"] = row_frame.winfo_height()

    def handle_when_row_resize_moves(event):
        if drag["start_y"] is None:
            return
        new_height = max(80, drag["start_height"] + event.y_root - drag["start_y"])
        row_frame.configure(height=new_height)

    def handle_when_row_resize_ends(_event):
        if drag["start_y"] is not None:
            post_event({
                "type": SET_ROW_HEIGHT,
                "tab_id": tab_id,
                "row_number": row_number,
                "height": row_frame.winfo_height(),
            })
        drag["start_y"] = None

    resize_handle.bind("<ButtonPress-1>", handle_when_row_resize_starts)
    resize_handle.bind("<B1-Motion>", handle_when_row_resize_moves)
    resize_handle.bind("<ButtonRelease-1>", handle_when_row_resize_ends)


def read_sash_proportions(paned, pane_count):
    """Read current Tk sash geometry as logical proportions."""
    width = max(1, paned.winfo_width())
    try:
        return [paned.sashpos(index) / width for index in range(pane_count - 1)]
    except tk.TclError:
        return []


def restore_sash_proportions(paned, proportions):
    """Apply logical sash proportions after Tk has measured the paned window."""
    if not proportions:
        return
    def restore():
        if not paned.winfo_exists():
            return
        width = paned.winfo_width()
        if width <= 1:
            paned.after(50, restore)
            return
        try:
            for index, proportion in enumerate(proportions):
                paned.sashpos(index, round(proportion * width))
        except tk.TclError:
            return
    paned.after_idle(restore)


def build_panel_host(parent, model, position):
    """Realize one logical position and mount its semantic panel."""
    host = ttk.Frame(parent, padding=8, relief="solid", borderwidth=1, style="Panel.TFrame")
    host.pack(side="left", fill="both", expand=True, padx=6, pady=6)
    panel_id = model["panel_at"][position]
    panel = panels[panel_id]
    header = ttk.Frame(host, style="Panel.TFrame")
    header.pack(fill="x")
    ttk.Label(header, text=position_label(position), style="PanelTitle.TLabel").pack(side="left")
    menu_button = ttk.Button(header, text="⋮", width=3)
    menu_button.configure(command=lambda: open_panel_menu(position, menu_button))
    menu_button.pack(side="right")
    ttk.Label(host, text=PANEL_TITLES.get(panel["panel_type"], panel["panel_type"]), style="PanelTitle.TLabel").pack(anchor="w")
    content = ttk.Frame(host, padding=8)
    content.pack(fill="both", expand=True)
    widgets["positions"][position] = {"host": host, "panel_id": panel_id}
    widgets["panels"][panel_id] = {"content": content}
    if panel["panel_type"] == TODO:
        label = ttk.Label(content)
        label.pack(anchor="w", pady=(0, 8))
        widgets["panels"][panel_id]["status_label"] = label
        ttk.Button(content, text="Toggle first item", command=lambda: post_event({"type": TOGGLE_TODO, "panel_id": panel_id})).pack(anchor="w")
        project_panel(panel_id)
    elif panel["panel_type"] == JOURNAL:
        text_var = tk.StringVar(value=panel["state"]["text"])
        widgets["panels"][panel_id]["text_var"] = text_var
        entry = ttk.Entry(content, textvariable=text_var, width=36)
        entry.pack(fill="x")
        entry.bind("<Return>", lambda event: post_event({"type": EDIT_JOURNAL, "panel_id": panel_id, "text": event.widget.get()}))
    else:
        ttk.Label(content, text="Structural host ready for a future instrument.", anchor="center").pack(fill="both", expand=True)


def open_panel_menu(position, button):
    """Queue a semantic panel replacement for a logical position."""
    menu = tk.Menu(button, tearoff=False)
    for panel_type, title in ((EMPTY, "Empty Panel"), (TODO, "Todo"), (JOURNAL, "Journal")):
        menu.add_command(label=title, command=lambda selected=panel_type: post_event({"type": REPLACE_PANEL, "position": position, "panel_type": selected}))
    menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())


def project_panel(panel_id):
    """Project one semantic panel record into its realized widgets."""
    panel = panels[panel_id]
    panel_widgets = widgets["panels"].get(panel_id, {})
    if panel["panel_type"] == TODO and "status_label" in panel_widgets:
        item = panel["state"]["items"][0]
        panel_widgets["status_label"].configure(text=("done" if item["done"] else "open") + ": " + item["text"])
    elif panel["panel_type"] == JOURNAL and "text_var" in panel_widgets:
        panel_widgets["text_var"].set(panel["state"]["text"])


def project_top_area():
    """Project global top-area state when the top widgets exist."""
    if not widgets["top"]:
        return
    widgets["top"]["date_label"].configure(text=g["selected_day"].isoformat())
    widgets["top"]["heartbeat_label"].configure(text=f"heartbeat {g['heartbeat_count']}")
    widgets["top"]["orientation_var"].set(g["orientation_text"])


# ---------------------------------------------------------------------------
# Tk shell


def handle_when_previous_day_button_is_clicked():
    """Queue previous-day navigation."""
    post_event({"type": SELECT_PREVIOUS_DAY})


def handle_when_next_day_button_is_clicked():
    """Queue next-day navigation."""
    post_event({"type": SELECT_NEXT_DAY})


def handle_when_today_button_is_clicked():
    """Queue today navigation."""
    post_event({"type": SELECT_TODAY})


def handle_when_orientation_text_is_submitted(event):
    """Queue an orientation edit."""
    post_event({"type": EDIT_ORIENTATION, "text": event.widget.get()})


def handle_when_heartbeat_timer_fires():
    """Queue the heartbeat and schedule the next timer callback."""
    if g["running"]:
        post_event({"type": SECOND_ELAPSED})
        g["root"].after(1000, handle_when_heartbeat_timer_fires)


def handle_when_notebook_tab_is_changed(_event):
    """Queue tab selection by stable tab identity, not tab title."""
    notebook = widgets["notebook"]
    selected_widget = notebook.select()
    if widgets["plus_frame"] is not None and selected_widget == str(widgets["plus_frame"]):
        post_event({"type": ADD_TAB})
        return
    for tab_id, tab_widgets in widgets["tabs"].items():
        if selected_widget == str(tab_widgets["frame"]):
            post_event({"type": SELECT_TAB, "tab_id": tab_id})
            return


def handle_when_notebook_is_double_clicked(event):
    """Open the editor for a real tab, never for the trailing plus tab."""
    notebook = widgets["notebook"]
    if notebook.identify(event.x, event.y) != "label":
        return
    try:
        tab_index = notebook.index(f"@{event.x},{event.y}")
    except tk.TclError:
        return
    model = current_model()
    if tab_index < len(model["tabs"]):
        open_tab_editor(model["tabs"][tab_index]["tab_id"])
        return "break"


def open_tab_editor(tab_id):
    """Show rename and delete commands for one logical tab."""
    tab = find_tab(current_model(), tab_id)
    if tab is None:
        return
    dialog = tk.Toplevel(widgets["notebook"])
    dialog.title("Edit Tab")
    dialog.transient(g["window"])
    dialog.resizable(False, False)
    ttk.Label(dialog, text="Tab Name:").grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 3))
    title = tk.StringVar(value=tab["title"])
    entry = ttk.Entry(dialog, textvariable=title, width=30)
    entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
    entry.focus_set()
    entry.selection_range(0, "end")

    def handle_when_tab_rename_is_confirmed():
        if title.get().strip():
            post_event({"type": RENAME_TAB, "tab_id": tab_id, "title": title.get()})
            dialog.destroy()

    def handle_when_tab_delete_is_confirmed():
        post_event({"type": DELETE_TAB, "tab_id": tab_id})
        dialog.destroy()

    ttk.Button(dialog, text="Rename", command=handle_when_tab_rename_is_confirmed).grid(row=2, column=0, padx=(10, 3), pady=(0, 10))
    delete_button = ttk.Button(dialog, text="Delete", command=handle_when_tab_delete_is_confirmed)
    delete_button.grid(row=2, column=1, padx=3, pady=(0, 10))
    if len(current_model()["tabs"]) <= 1:
        delete_button.state(["disabled"])
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=2, column=2, padx=(3, 10), pady=(0, 10))
    dialog.bind("<Return>", lambda _event: handle_when_tab_rename_is_confirmed())
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    dialog.grab_set()
    dialog.wait_window()


def build_top_area(parent):
    """Build the global top area."""
    area = tk.Frame(parent, background=COLORS["top"], padx=12, pady=10)
    area.pack(fill="x")
    ttk.Button(area, text="<", command=handle_when_previous_day_button_is_clicked).pack(side="left")
    date_label = ttk.Label(area, width=12, anchor="center")
    date_label.pack(side="left", padx=6)
    ttk.Button(area, text="今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(area, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left")
    orientation_var = tk.StringVar(value=g["orientation_text"])
    orientation = ttk.Entry(area, textvariable=orientation_var, width=28)
    orientation.pack(side="left", padx=12)
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    heartbeat_label = ttk.Label(area, text="heartbeat 0")
    heartbeat_label.pack(side="right")
    widgets["top"].update({"date_label": date_label, "orientation_var": orientation_var, "heartbeat_label": heartbeat_label})


def build_window():
    """Create the withdrawn root and visible application Toplevel."""
    root = tk.Tk()
    root.withdraw()
    g["root"] = root
    window = tk.Toplevel(root)
    g["window"] = window
    window.title("Today — Combined Model")
    window.geometry("1100x760")
    window.minsize(720, 480)
    window.protocol("WM_DELETE_WINDOW", handle_when_application_close_is_requested)
    style = ttk.Style(root)
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["panel_text"], font=("TkDefaultFont", 10, "bold"))
    build_top_area(window)
    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True)
    widgets["notebook"] = notebook
    notebook.bind("<<NotebookTabChanged>>", handle_when_notebook_tab_is_changed)
    notebook.bind("<Double-1>", handle_when_notebook_is_double_clicked, add="+")
    reconcile_workspace(current_model())
    status = tk.Label(window, text="Ready.", anchor="w", background=COLORS["status"], foreground=COLORS["status_text"], padx=7, pady=3)
    status.pack(fill="x", side="bottom")
    widgets["status"] = status
    root.after(1000, handle_when_heartbeat_timer_fires)
    return root


def handle_when_application_close_is_requested():
    """Stop the machine and destroy the runtime."""
    g["running"] = False
    g["root"].destroy()


def main():
    """Initialize the logical world and run the Tk shell."""
    ensure_day_model(g["selected_day"])
    root = build_window()
    root.mainloop()


if __name__ == "__main__":
    main()
