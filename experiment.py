"""Interactive cockpit chassis spike for the Today application.

This file deliberately contains layout machinery only.  Panels are hosts for
future Today instruments; they do not know anything about todos, dates, or M1.
"""

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


# Shared program facts.  These are mutated in place so the running prototype's
# state remains easy to inspect while experimenting with the layout.
g = {
    "running": True,
    "debug_enabled": False,
}

COLORS = {
    "top": "#081525",
    "middle": "#10243A",
    "panel": "#F3F6F8",
    "panel_text": "#162332",
    "separator": "#35516B",
    "status": "#0B1828",
    "status_text": "#D7E2EC",
}

LAYOUT_SCHEMA_VERSION = 1
ROW_DEFAULT_HEIGHT = 190
ROW_HEIGHT_STEP = 16
ROW_MIN_HEIGHT = ROW_DEFAULT_HEIGHT
ROW_MAX_HEIGHT = 600
PANEL_TITLES = {
    "empty": "Empty Panel",
    "orientation": "Orientation",
    "todo": "Todo",
    "whiteboard": "Whiteboard",
    "journal": "Journal",
    "objectives": "Objectives",
    "metrics": "Metrics",
    "upcoming": "Upcoming",
}

# Open collections of live widgets, keyed by their stable layout ids.
widgets = {
    "rows": {},
}

# Small, JSON-friendly representation of the future serializable layout.
layout = {
    "schema_version": LAYOUT_SCHEMA_VERSION,
    "outer_sash_position": None,
    "row_sash_proportions": [],
    "rows": [
        {
            "pane_count": 2,
            "height": ROW_DEFAULT_HEIGHT,
            "sash_proportions": [],
            "panels": [{"panel_type": "empty"}, {"panel_type": "empty"}],
        },
        {
            "pane_count": 1,
            "height": ROW_DEFAULT_HEIGHT,
            "sash_proportions": [],
            "panels": [{"panel_type": "empty"}],
        },
    ],
}


def make_layout_document():
    """Return the versioned, JSON-ready document for the current layout."""
    return {
        "format": "today-cockpit-layout",
        "schema_version": LAYOUT_SCHEMA_VERSION,
        "layout": json.loads(json.dumps(layout)),
    }


def validate_layout_document(document):
    """Validate and return a layout payload from a saved document."""
    if not isinstance(document, dict):
        raise ValueError("Layout document must be a JSON object.")
    saved_layout = document.get("layout", document)
    if not isinstance(saved_layout, dict):
        raise ValueError("Layout payload must be a JSON object.")
    rows = saved_layout.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Layout payload must contain a rows list.")
    saved_layout.setdefault("row_sash_proportions", [])
    if not isinstance(saved_layout["row_sash_proportions"], list):
        raise ValueError("Layout payload must contain a row_sash_proportions list.")
    for row_index, row_state in enumerate(rows, start=1):
        if not isinstance(row_state, dict):
            raise ValueError(f"Row {row_index} is not an object.")
        pane_count = row_state.get("pane_count")
        if pane_count not in (1, 2, 3):
            raise ValueError(f"Row {row_index} has an invalid pane count.")
        row_height = row_state.setdefault("height", ROW_DEFAULT_HEIGHT)
        if isinstance(row_height, bool) or not isinstance(row_height, int):
            raise ValueError(f"Row {row_index} has an invalid height.")
        if row_height < ROW_MIN_HEIGHT:
            row_state["height"] = ROW_DEFAULT_HEIGHT
        elif row_height > ROW_MAX_HEIGHT:
            raise ValueError(f"Row {row_index} height is outside the supported range.")
        row_state.setdefault("sash_proportions", [])
        if not isinstance(row_state["sash_proportions"], list):
            raise ValueError(f"Row {row_index} must contain a sash_proportions list.")
        panels = row_state.get("panels")
        if not isinstance(panels, list) or len(panels) < pane_count:
            raise ValueError(f"Row {row_index} must contain a panels list.")
    return json.loads(json.dumps(saved_layout))


def write_layout_file(filename):
    """Serialize the current layout document to a UTF-8 JSON file."""
    with open(filename, "w", encoding="utf-8") as stream:
        json.dump(make_layout_document(), stream, indent=2)
        stream.write("\n")


def read_layout_file(filename):
    """Read and validate a saved layout document from a UTF-8 JSON file."""
    with open(filename, "r", encoding="utf-8") as stream:
        return validate_layout_document(json.load(stream))


def make_empty_panel_state():
    """Return the minimal state for a future panel host."""
    return {"panel_type": "empty"}


def get_panel_title(panel_type):
    """Return the display title for a serialized panel type."""
    return PANEL_TITLES.get(panel_type, PANEL_TITLES["empty"])


class StatusBar(ttk.Frame):
    """Fixed bottom status area with a small debug-copy convenience."""

    def __init__(self, parent):
        super().__init__(parent, padding=(1, 1), style="StatusOuter.TFrame")
        self.status_surface = tk.Frame(self, background=COLORS["status"])
        self.status_surface.grid(row=0, column=0, sticky="nsew")
        self.message = tk.StringVar(value="Ready.")
        self.label = tk.Label(
            self.status_surface,
            textvariable=self.message,
            anchor="w",
            background=COLORS["status"],
            foreground=COLORS["status_text"],
            padx=7,
            pady=3,
        )
        self.label.grid(row=0, column=0, sticky="ew")
        self.status_surface.columnconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._click_times = []
        self.bind("<Button-1>", self.handle_when_status_bar_is_clicked)
        self.label.bind("<Button-1>", self.handle_when_status_bar_is_clicked)

    def set_message(self, message):
        """Show a short status message."""
        self.message.set(message)

    def handle_when_status_bar_is_clicked(self, _event):
        """Copy a compact layout snapshot after five quick status clicks."""
        now = int(self.winfo_toplevel().tk.call("clock", "milliseconds"))
        self._click_times = [stamp for stamp in self._click_times if now - stamp <= 2000]
        self._click_times.append(now)
        if len(self._click_times) >= 5:
            snapshot = json.dumps(layout, indent=2)
            self.clipboard_clear()
            self.clipboard_append(snapshot)
            self.set_message("Layout debug snapshot copied to clipboard.")
            self._click_times.clear()


class PanelWidget(ttk.Frame):
    """A visible host for one future Today panel."""

    def __init__(self, parent, row_widget, panel_index):
        self.panel_state = row_widget.row_state["panels"][panel_index]
        super().__init__(parent, padding=8, relief="solid", borderwidth=1, style="Panel.TFrame")
        self.row_widget = row_widget
        self.panel_index = panel_index

        header = ttk.Frame(self, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        self.title = tk.StringVar(value=get_panel_title(self.panel_state.get("panel_type", "empty")))
        ttk.Label(header, textvariable=self.title, style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.menu_button = ttk.Button(
            header,
            text="⋮",
            width=3,
            command=self.handle_when_panel_menu_button_is_clicked,
        )
        self.menu_button.grid(row=0, column=1, sticky="e")
        ttk.Label(
            self,
            text="Panel host\nReady for a future Today instrument",
            style="PanelBody.TLabel",
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        header.columnconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def handle_when_panel_menu_button_is_clicked(self):
        """Open content-selection commands attached to this panel."""
        menu = tk.Menu(self, tearoff=False)
        panel_types = (
            ("Empty", "Empty Panel"),
            ("Orientation", "Orientation"),
            ("Todo", "Todo"),
            ("Whiteboard", "Whiteboard"),
            ("Journal", "Journal"),
            ("Objectives", "Objectives"),
            ("Metrics", "Metrics"),
            ("Upcoming", "Upcoming"),
        )
        menu.add_command(label="Panel Type", state="disabled")
        menu.add_separator()
        for panel_type, title in panel_types:
            menu.add_command(
                label=panel_type,
                command=lambda selected_type=panel_type, selected_title=title: self.set_panel_type(
                    selected_type, selected_title
                ),
            )
        menu.tk_popup(
            self.menu_button.winfo_rootx(),
            self.menu_button.winfo_rooty() + self.menu_button.winfo_height(),
        )

    def set_panel_type(self, panel_type, title):
        """Change the placeholder identity without changing row geometry."""
        self.panel_state["panel_type"] = panel_type.lower()
        self.title.set(title)
        self.row_widget.middle_area.set_status(f"Panel set to {title}.")


class RowWidget(tk.Frame):
    """One vertically stacked row, containing one to three panel hosts."""

    def __init__(self, parent, middle_area, row_index, row_state):
        row_state.setdefault("height", ROW_DEFAULT_HEIGHT)
        super().__init__(parent, height=row_state["height"], background=COLORS["middle"])
        self.middle_area = middle_area
        self.row_index = row_index
        self.row_state = row_state
        self.control_strip = tk.Frame(self, width=34, background=COLORS["middle"])
        self.control_strip.grid(row=0, column=0, sticky="ns", padx=(0, 5), pady=(0, 10))
        self.control_strip.grid_propagate(False)
        self.control_buttons = {}
        for button_row, pane_count in enumerate((1, 2, 3)):
            button = tk.Button(
                self.control_strip,
                text=str(pane_count),
                width=2,
                padx=0,
                pady=1,
                command=lambda count=pane_count: self.set_pane_count(count),
            )
            button.grid(row=button_row, column=0, padx=2, pady=(3 if button_row == 0 else 1, 1))
            self.control_buttons[pane_count] = button
        delete_button = tk.Button(
            self.control_strip,
            text="x",
            width=2,
            padx=0,
            pady=1,
            command=self.remove_row,
        )
        delete_button.grid(row=3, column=0, padx=2, pady=(5, 1))
        self.panedwindow = ttk.Panedwindow(self, orient="horizontal")
        self.panedwindow.grid(row=0, column=1, sticky="nsew", pady=(0, 10))
        self.panedwindow.bind(
            "<ButtonRelease-1>",
            self.handle_when_horizontal_sash_is_released,
            add="+",
        )
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.grid_propagate(False)
        initial_sash_proportions = list(row_state.get("sash_proportions", []))
        self.set_pane_count(row_state["pane_count"], announce=False)
        self.row_state["sash_proportions"] = initial_sash_proportions

    def set_pane_count(self, pane_count, announce=True):
        """Replace this row's panel hosts with the requested pane count."""
        pane_count = max(1, min(3, int(pane_count)))
        existing_panels = self.row_state.get("panels", [])
        self.row_state["pane_count"] = pane_count
        self.row_state["panels"] = (
            existing_panels[:pane_count]
            + [make_empty_panel_state() for _ in range(max(0, pane_count - len(existing_panels)))]
        )
        self.row_state["sash_proportions"] = []
        for count, button in self.control_buttons.items():
            button.configure(relief="sunken" if count == pane_count else "raised")
        for child in self.panedwindow.panes():
            self.panedwindow.forget(child)
            self.nametowidget(child).destroy()
        for panel_index in range(pane_count):
            panel = PanelWidget(self.panedwindow, self, panel_index)
            self.panedwindow.add(panel, weight=1)
        self.after_idle(self.restore_sash_positions)
        if announce:
            self.middle_area.set_status(f"Row {self.row_index + 1} set to {pane_count} pane{'s' if pane_count != 1 else ''}.")

    def capture_sash_positions(self):
        """Keep current inner sash proportions in the explicit layout model."""
        try:
            available_width = max(1, self.panedwindow.winfo_width())
            sash_proportions = []
            for index in range(max(0, self.row_state["pane_count"] - 1)):
                sash_proportions.append(
                    int(self.panedwindow.sashpos(index)) / available_width
                )
            self.row_state["sash_proportions"] = sash_proportions
        except tk.TclError:
            pass

    def restore_sash_positions(self):
        """Apply serialized sash positions after Tk has measured the row."""
        if self.panedwindow.winfo_width() <= 1 and self.row_state.get("sash_proportions"):
            self.after(50, self.restore_sash_positions)
            return
        try:
            available_width = max(1, self.panedwindow.winfo_width())
            for index, proportion in enumerate(self.row_state.get("sash_proportions", [])):
                self.panedwindow.sashpos(index, round(proportion * available_width))
            self.capture_sash_positions()
        except tk.TclError:
            pass

    def handle_when_horizontal_sash_is_released(self, _event):
        """Capture a row's divider positions immediately after a drag."""
        self.after_idle(self.capture_sash_positions)

    def remove_row(self):
        """Ask the owning middle area to remove this row."""
        self.middle_area.remove_row(self.row_index)

class MiddleArea(tk.Frame):
    """Scrollable canvas and stacked row workspace."""

    def __init__(self, parent, status_bar):
        super().__init__(parent, background=COLORS["middle"], padx=8, pady=8)
        self.status_bar = status_bar
        self.canvas = tk.Canvas(self, highlightthickness=0, background=COLORS["middle"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.rows_frame = tk.Frame(self.canvas, background=COLORS["middle"])
        self.rows_panedwindow = ttk.Panedwindow(self.rows_frame, orient="vertical")
        self.rows_panedwindow.grid(row=0, column=0, sticky="ew")
        self.rows_frame.columnconfigure(0, weight=1)
        self.add_button = None
        self.rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rows_frame.bind("<Configure>", self.handle_when_rows_frame_is_configured)
        self.canvas.bind("<Configure>", self.handle_when_canvas_is_configured)
        self.canvas.bind("<Enter>", self.handle_when_pointer_enters_canvas)
        self.canvas.bind("<Leave>", self.handle_when_pointer_leaves_canvas)
        self.rows_panedwindow.bind(
            "<ButtonRelease-1>",
            self.handle_when_vertical_sash_is_released,
            add="+",
        )
        self.render_rows()

    def render_rows(self):
        """Render rows in a vertical paned layout and keep Add a Row last."""
        for pane in self.rows_panedwindow.panes():
            self.rows_panedwindow.forget(pane)
            self.nametowidget(pane).destroy()
        if self.add_button is not None:
            self.add_button.destroy()
        widgets["rows"].clear()
        for row_index, row_state in enumerate(layout["rows"]):
            row = RowWidget(self.rows_frame, self, row_index, row_state)
            self.rows_panedwindow.add(row, weight=1)
            widgets["rows"][row_index] = row
        add_button = ttk.Button(self.rows_frame, text="Add a Row", command=self.add_row)
        add_button.grid(row=1, column=0, pady=(4, 12))
        self.add_button = add_button

    def capture_live_layout_state(self):
        """Copy measured horizontal and vertical sash proportions into the model."""
        for row in widgets["rows"].values():
            row.capture_sash_positions()
        self.capture_vertical_sash_proportions()

    def capture_vertical_sash_proportions(self):
        """Store row divider locations relative to the current rows viewport."""
        try:
            available_height = max(1, self.rows_panedwindow.winfo_height())
            layout["row_sash_proportions"] = [
                int(self.rows_panedwindow.sashpos(index)) / available_height
                for index in range(max(0, len(layout["rows"]) - 1))
            ]
        except tk.TclError:
            pass

    def restore_vertical_sash_proportions(self):
        """Apply saved row divider proportions after the viewport is measured."""
        if self.rows_panedwindow.winfo_height() <= 1 and layout.get("row_sash_proportions"):
            self.after(50, self.restore_vertical_sash_proportions)
            return
        try:
            available_height = max(1, self.rows_panedwindow.winfo_height())
            for index, proportion in enumerate(layout.get("row_sash_proportions", [])):
                self.rows_panedwindow.sashpos(index, round(proportion * available_height))
            self.constrain_vertical_sashes()
            self.capture_vertical_sash_proportions()
        except tk.TclError:
            pass

    def constrain_vertical_sashes(self):
        """Keep every row at least the minimum usable height."""
        row_count = len(layout["rows"])
        if row_count < 2:
            return
        try:
            available_height = self.rows_panedwindow.winfo_height()
            if available_height < row_count * ROW_MIN_HEIGHT:
                return
            for index in range(row_count - 1):
                lower_bound = (index + 1) * ROW_MIN_HEIGHT
                upper_bound = available_height - (row_count - index - 1) * ROW_MIN_HEIGHT
                position = int(self.rows_panedwindow.sashpos(index))
                self.rows_panedwindow.sashpos(
                    index,
                    max(lower_bound, min(upper_bound, position)),
                )
        except tk.TclError:
            pass

    def add_row(self):
        """Append a row without rebuilding existing rows or moving their sashes."""
        self.capture_live_layout_state()
        row_state = {
            "pane_count": 1,
            "height": ROW_DEFAULT_HEIGHT,
            "sash_proportions": [],
            "panels": [make_empty_panel_state()],
        }
        layout["rows"].append(row_state)
        row_index = len(layout["rows"]) - 1
        row = RowWidget(self.rows_frame, self, row_index, row_state)
        self.rows_panedwindow.add(row, weight=1)
        widgets["rows"][row_index] = row
        self.add_button.grid(row=1, column=0, pady=(4, 12))
        self.after_idle(self.restore_vertical_sash_proportions)
        self.set_status(f"Added Row {len(layout['rows'])}.")

    def remove_row(self, row_index):
        """Remove one row from the explicit layout and redraw the workspace."""
        if not 0 <= row_index < len(layout["rows"]):
            return
        self.capture_live_layout_state()
        del layout["rows"][row_index]
        layout["row_sash_proportions"] = layout["row_sash_proportions"][: max(0, len(layout["rows"]) - 1)]
        self.render_rows()
        self.after_idle(self.restore_vertical_sash_proportions)
        self.set_status("Row removed.")

    def set_status(self, message):
        """Report workspace changes in the fixed status bar."""
        self.status_bar.set_message(message)

    def handle_when_rows_frame_is_configured(self, _event):
        """Keep the canvas scroll region aligned with the rows."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def handle_when_canvas_is_configured(self, event):
        """Make the embedded rows frame track the available canvas width."""
        self.canvas.itemconfigure(self.rows_window, width=event.width)

    def handle_when_pointer_enters_canvas(self, _event):
        """Enable mouse-wheel scrolling while the pointer is over the workspace."""
        self.canvas.bind_all("<MouseWheel>", self.handle_when_mouse_wheel_moves)

    def handle_when_pointer_leaves_canvas(self, _event):
        """Stop consuming the application mouse wheel outside the workspace."""
        self.canvas.unbind_all("<MouseWheel>")

    def handle_when_mouse_wheel_moves(self, event):
        """Scroll rows in platform-neutral wheel units."""
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def handle_when_vertical_sash_is_released(self, _event):
        """Capture row heights immediately after a vertical sash drag."""
        self.after_idle(self.constrain_vertical_sashes)
        self.after_idle(self.capture_vertical_sash_proportions)


class TodayApp:
    """Own the root window and the cockpit's three structural regions."""

    def __init__(self, root):
        self.root = root
        self.root.title("Today — Spike Solution")
        self.root.geometry("1100x760")
        self.root.minsize(720, 480)
        self.root.protocol("WM_DELETE_WINDOW", self.handle_when_application_close_is_requested)
        style = ttk.Style(self.root)
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["panel_text"], font=("TkDefaultFont", 10, "bold"))
        style.configure("PanelBody.TLabel", background=COLORS["panel"], foreground=COLORS["panel_text"])
        style.configure("StatusOuter.TFrame", background=COLORS["separator"])

        self.menu_bar = tk.Menu(root)
        layout_menu = tk.Menu(self.menu_bar, tearoff=False)
        layout_menu.add_command(label="Save Layout…", command=self.save_layout_to_file)
        layout_menu.add_command(label="Load Layout…", command=self.load_layout_from_file)
        self.menu_bar.add_cascade(label="Layout", menu=layout_menu)
        root.configure(menu=self.menu_bar)

        self.outer_panedwindow = ttk.Panedwindow(root, orient="vertical")
        self.outer_panedwindow.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        self.top_area = tk.Frame(self.outer_panedwindow, background=COLORS["top"], padx=12, pady=12)
        tk.Label(
            self.top_area,
            text="Top Area",
            background=COLORS["top"],
            foreground="#E8EEF5",
            font=("TkDefaultFont", 16, "bold"),
            anchor="nw",
        ).grid(row=0, column=0, sticky="nw")
        tk.Frame(self.top_area, height=1, background=COLORS["separator"]).grid(
            row=1, column=0, sticky="ew", pady=(12, 0)
        )
        self.top_area.columnconfigure(0, weight=1)
        self.middle_area = MiddleArea(self.outer_panedwindow, None)
        self.status_bar = StatusBar(root)
        self.status_bar.grid(row=1, column=0, sticky="ew")
        self.middle_area.status_bar = self.status_bar
        self.outer_panedwindow.add(self.top_area, weight=1)
        self.outer_panedwindow.add(self.middle_area, weight=3)
        self.root.after_idle(self.restore_outer_sash_position)

    def restore_outer_sash_position(self):
        """Restore a saved outer sash when this prototype gains persistence."""
        if layout["outer_sash_position"] is not None:
            try:
                self.outer_panedwindow.sashpos(0, layout["outer_sash_position"])
            except tk.TclError:
                pass

    def capture_live_layout_state(self):
        """Copy current widget geometry into the serializable layout model."""
        try:
            layout["outer_sash_position"] = self.outer_panedwindow.sashpos(0)
        except tk.TclError:
            pass
        self.middle_area.capture_live_layout_state()

    def save_layout_to_file(self):
        """Prompt for a JSON path and save the current cockpit configuration."""
        self.capture_live_layout_state()
        filename = filedialog.asksaveasfilename(
            title="Save Today Cockpit Layout",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not filename:
            return
        try:
            write_layout_file(filename)
            self.status_bar.set_message(f"Layout saved: {filename}")
        except (OSError, ValueError) as error:
            messagebox.showerror("Save Layout", str(error), parent=self.root)

    def load_layout_from_file(self):
        """Prompt for a JSON path and apply its cockpit configuration."""
        filename = filedialog.askopenfilename(
            title="Load Today Cockpit Layout",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not filename:
            return
        try:
            loaded_layout = read_layout_file(filename)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Load Layout", str(error), parent=self.root)
            return
        layout.clear()
        layout.update(loaded_layout)
        layout.setdefault("schema_version", LAYOUT_SCHEMA_VERSION)
        self.middle_area.render_rows()
        self.root.after_idle(self.restore_outer_sash_position)
        self.root.after_idle(self.middle_area.restore_vertical_sash_proportions)
        self.status_bar.set_message(f"Layout loaded: {filename}")

    def handle_when_application_close_is_requested(self):
        """Capture the outer sash before closing the experiment."""
        try:
            layout["outer_sash_position"] = self.outer_panedwindow.sashpos(0)
        except tk.TclError:
            pass
        g["running"] = False
        self.root.destroy()


def run_experiment():
    """Create and run the interactive cockpit prototype."""
    root = tk.Tk()
    TodayApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_experiment()
