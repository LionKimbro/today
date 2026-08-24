"""Interactive cockpit chassis spike for the Today application.

This file deliberately contains layout machinery only.  Panels are hosts for
future Today instruments; they do not know anything about todos, dates, or M1.
"""

import json
import tkinter as tk
from tkinter import ttk


# Shared program facts.  These are mutated in place so the running prototype's
# state remains easy to inspect while experimenting with the layout.
g = {
    "running": True,
    "debug_enabled": False,
}

# Open collections of live widgets, keyed by their stable layout ids.
widgets = {
    "rows": {},
}

# Small, JSON-friendly representation of the future serializable layout.
layout = {
    "outer_sash_position": None,
    "rows": [
        {
            "pane_count": 2,
            "sash_positions": [],
            "panels": [{"panel_type": "empty"}, {"panel_type": "empty"}],
        },
        {
            "pane_count": 1,
            "sash_positions": [],
            "panels": [{"panel_type": "empty"}],
        },
    ],
}


def make_empty_panel_state():
    """Return the minimal state for a future panel host."""
    return {"panel_type": "empty"}


class StatusBar(ttk.Frame):
    """Fixed bottom status area with a small debug-copy convenience."""

    def __init__(self, parent):
        super().__init__(parent, padding=(8, 3))
        self.message = tk.StringVar(value="Ready.")
        self.label = ttk.Label(self, textvariable=self.message, anchor="w")
        self.label.grid(row=0, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
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
        super().__init__(parent, padding=8, relief="solid", borderwidth=1)
        self.row_widget = row_widget
        self.panel_index = panel_index

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Empty Panel", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            header,
            text="⋮",
            width=3,
            command=self.handle_when_panel_menu_button_is_clicked,
        ).grid(row=0, column=1, sticky="e")
        ttk.Label(
            self,
            text="Panel host\nReady for a future Today instrument",
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        header.columnconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def handle_when_panel_menu_button_is_clicked(self):
        """Open temporary row manipulation commands for this panel."""
        menu = tk.Menu(self, tearoff=False)
        for pane_count in (1, 2, 3):
            menu.add_command(
                label=f"Set row to {pane_count} pane{'s' if pane_count != 1 else ''}",
                command=lambda count=pane_count: self.row_widget.set_pane_count(count),
            )
        menu.add_separator()
        menu.add_command(label="Remove row", command=self.row_widget.remove_row)
        menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())


class RowWidget(ttk.Frame):
    """One vertically stacked row, containing one to three panel hosts."""

    def __init__(self, parent, middle_area, row_index, row_state):
        super().__init__(parent, height=190, padding=(0, 0, 0, 10))
        self.middle_area = middle_area
        self.row_index = row_index
        self.row_state = row_state
        self.panedwindow = ttk.Panedwindow(self, orient="horizontal")
        self.panedwindow.pack(fill="both", expand=True)
        self.pack_propagate(False)
        self.set_pane_count(row_state["pane_count"], announce=False)

    def set_pane_count(self, pane_count, announce=True):
        """Replace this row's panel hosts with the requested pane count."""
        pane_count = max(1, min(3, int(pane_count)))
        self.row_state["pane_count"] = pane_count
        self.row_state["panels"] = [make_empty_panel_state() for _ in range(pane_count)]
        self.row_state["sash_positions"] = []
        for child in self.panedwindow.panes():
            self.panedwindow.forget(child)
            self.nametowidget(child).destroy()
        for panel_index in range(pane_count):
            panel = PanelWidget(self.panedwindow, self, panel_index)
            self.panedwindow.add(panel, weight=1)
        self.after_idle(self.capture_sash_positions)
        if announce:
            self.middle_area.set_status(f"Row {self.row_index + 1} set to {pane_count} pane{'s' if pane_count != 1 else ''}.")

    def capture_sash_positions(self):
        """Keep current inner sash locations in the explicit layout model."""
        try:
            self.row_state["sash_positions"] = [
                self.panedwindow.sashpos(index)
                for index in range(max(0, self.row_state["pane_count"] - 1))
            ]
        except tk.TclError:
            pass

    def remove_row(self):
        """Ask the owning middle area to remove this row."""
        self.middle_area.remove_row(self.row_index)


class MiddleArea(ttk.Frame):
    """Scrollable canvas and stacked row workspace."""

    def __init__(self, parent, status_bar):
        super().__init__(parent, padding=8)
        self.status_bar = status_bar
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#f4f4f4")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rows_frame.columnconfigure(0, weight=1)
        self.rows_frame.bind("<Configure>", self.handle_when_rows_frame_is_configured)
        self.canvas.bind("<Configure>", self.handle_when_canvas_is_configured)
        self.canvas.bind("<Enter>", self.handle_when_pointer_enters_canvas)
        self.canvas.bind("<Leave>", self.handle_when_pointer_leaves_canvas)
        self.render_rows()

    def render_rows(self):
        """Render all rows and keep the Add a Row control last."""
        for child in self.rows_frame.winfo_children():
            child.destroy()
        widgets["rows"].clear()
        for row_index, row_state in enumerate(layout["rows"]):
            row = RowWidget(self.rows_frame, self, row_index, row_state)
            row.grid(row=row_index, column=0, sticky="ew")
            widgets["rows"][row_index] = row
        add_button = ttk.Button(self.rows_frame, text="Add a Row", command=self.add_row)
        add_button.grid(row=len(layout["rows"]), column=0, pady=(4, 12))
        self.rows_frame.rowconfigure(len(layout["rows"]), weight=0)

    def add_row(self):
        """Append a one-pane row immediately before the add button."""
        layout["rows"].append({
            "pane_count": 1,
            "sash_positions": [],
            "panels": [make_empty_panel_state()],
        })
        self.render_rows()
        self.set_status(f"Added Row {len(layout['rows'])}.")

    def remove_row(self, row_index):
        """Remove one row from the explicit layout and redraw the workspace."""
        if not 0 <= row_index < len(layout["rows"]):
            return
        del layout["rows"][row_index]
        self.render_rows()
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


class TodayApp:
    """Own the root window and the cockpit's three structural regions."""

    def __init__(self, root):
        self.root = root
        self.root.title("Today — Spike Solution")
        self.root.geometry("1100x760")
        self.root.minsize(720, 480)
        self.root.protocol("WM_DELETE_WINDOW", self.handle_when_application_close_is_requested)

        self.outer_panedwindow = ttk.Panedwindow(root, orient="vertical")
        self.outer_panedwindow.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        self.top_area = ttk.Frame(self.outer_panedwindow, padding=12)
        ttk.Label(self.top_area, text="Top Area", font=("TkDefaultFont", 16, "bold")).pack(anchor="nw")
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
