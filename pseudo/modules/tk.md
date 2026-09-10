# `tk.py`

OWNS: widgets, bindings, Tk-side semantic events, Core-command realization.

READS: plain Core commands.

DOES NOT OWN: Today state or decisions.

The hosted-panel combobox sends `HOST_PANEL`; it does not swap panels itself.

Text input resets one 1-second debounce. Its expiry sends generic
`TEXT_DEBOUNCE`; Tk does not decide whether to save.

Tk renders the history slider and Snapshot button. The visible version's status
uses the global status bar; Tk does not interpret history.

Rename stays disabled until Core renders the panel. Its callback uses the
rendered panel identity. A late render does not re-enable it during closing.

Stage 7B builds Core's fixed rows and positions. A hosted position builds its
panel controls; an unhosted position visibly says it is empty.

Stage 7C gives an empty position a chooser of eligible existing panels. A
hosted position offers `Unhost panel`; neither control mutates Tk's model.

Stage 7D renders each day tab as a Notebook page. User selection emits
`SELECT_TAB`; Core's accepted `SET_SELECTED_TAB` selects the page.

Stage 7E uses horizontal Tk paned windows. Each document row has a resize
handle beneath it, including the final row. A released handle or pane sash
reports measured geometry; accepted row height or sash proportions are
reapplied by targeted commands.

Stage 7F row controls emit `MOVE_ROW`. Tk rebuilds from Core only after Mem
accepts the structural order change. The final row alone also offers `+` for
`ADD_ROW`.

The row rail's `1` / `2` / `3` / `x` controls send pane-count and row-deletion
events. The header offers create, rename, and delete for the selected tab.

Each tab is a scrollable surface. Settled scrolling emits
`SET_TAB_SCROLL_POSITION`; Core's accepted position is reapplied to Tk.

The Tk shell follows the 03 cockpit palette. The row rail carries inert
`1`/`2`/`3`/`x` controls beside the working row arrows.
