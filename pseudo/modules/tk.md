# `tk.py`

OWNS: widgets, bindings, Tk-side semantic events, Core-command realization.

READS: plain Core commands.

DOES NOT OWN: Today state or decisions.

`panel_widget_reg` establishes the active panel host and identities while a
panel builder runs. `create_widget("unhost-button")` owns the shared unhost
and Control-click delete bindings; panel builders only place the result.

The hosted-panel combobox sends `HOST_PANEL`; it does not swap panels itself.

The top-left `<`, date, `今`, and `>` controls send day-selection events.
Tk presents only the date Core has rendered.

The top-right Orientation editor is the day-level special position. It sends
the ordinary text events and has no history controls.

Text input resets one 1-second debounce. Its expiry sends generic
`TEXT_DEBOUNCE`; Tk does not decide whether to save.

A To-Do panel has Tk-local `List` / `Text` presentation selection. List
controls send semantic item events; Text sends `TODO_TEXT_CHANGED` and uses the
same debounce. Returning to List flushes a pending text debounce first, then
asks Core for its current canonical List rendering.

A TkMarkup panel has Tk-local `View` / `Edit` selection. View parses raw
normalized source locally; Edit sends `TKMARKUP_TEXT_CHANGED` through the same
debounce. Returning to View flushes then waits for Core's raw-text rendering.
Tk owns external link/path opening and clipboard copying from its local view.
Double-clicking noninteractive TkMarkup View content enters Edit; Ctrl+Enter
in its editor follows the ordinary Edit-to-View boundary.

Tk renders the history slider and Snapshot button. The visible version's status
uses the global status bar; Tk does not interpret history.

Rename stays disabled until Core renders the panel. Its callback uses the
rendered panel identity. A late render does not re-enable it during closing.

Stage 7B builds Core's fixed rows and positions. A hosted position builds its
panel controls; an unhosted position visibly says it is empty.

Stage 7C gives an empty position a chooser of eligible existing panels. A
hosted position offers `Unhost panel`; neither control mutates Tk's model.

An empty position also offers `+ Whiteboard`, `+ To-Do`, `+ TkMarkup`, `+ Journal`, and `+ Image`.
Each sends `CREATE_AND_HOST_PANEL`; Tk does not mint or host a panel itself.

An Image panel offers Paste from Clipboard, Browse for Image, and native file
drop into its canvas. The TkDND-enabled root owns drop reception; Tcl list
parsing preserves spaces in dropped paths. Browse obtains a path through the
native dialog. Paste only requests clipboard acquisition. Each emits
`IMPORT_IMAGE`; acquisition, decoding, resizing, and asset writes happen off
the Tk thread. Multiple dropped files produce a local explanatory message.

`RENDER_IMAGE_PANEL` supplies the asset reference, busy state, and input error.
Empty controls disable while busy. Clear image emits `CLEAR_IMAGE`, including
during an import; it is distinct from the shared panel-unhost `x` control.
Each hosted position retains its own PhotoImage and preview geometry.

Mapped, nonzero canvas bounds debounce `REQUEST_IMAGE_PREVIEW` by 100 ms.
`SET_IMAGE_PREVIEW` carries prepared RGBA bytes and actual dimensions plus
the original requested bounds. Tk constructs the Tk image without decoding
or resizing. Results whose asset or requested bounds are obsolete are ignored.
Unhosting and full rebuild cancel pending callbacks and invalidate old widget
records; hidden hosts request their preview when mapped.

Red pen draws a separate Canvas ink layer. Tk captures one unfinished stroke;
release sends normalized points, red color, and relative width to Core. A dot
is a one-point stroke. The pen begins only within the fitted image, clamps
dragged points to its bounds, and resets a panel-owned 60-second save callback.
Active drawing cancels that callback. Leave/tab/day/normal close and widget
teardown finish strokes and flush drawing timers; clear discards pending ink.
Preview replacement/resize reprojects marks without changing the image bytes.

The 50 ms main-thread fatal-failure poll also reaps exited worker runtimes.
Reaping joins and removes completed machines; it does not request retirement.

Normal `x` unhosts. Control-clicking `x` opens a Tk-local delete confirmation;
its optional 30-second no-prompt window is also Tk-local. Confirmation sends
only `DELETE_PANEL` to Core.

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
events. A trailing Tk-only `+` Notebook page sends `CREATE_TAB`. Double-click
on a real tab opens a Tk edit dialog; its controls send rename or delete events.

Each tab is a scrollable surface. Settled scrolling emits
`SET_TAB_SCROLL_POSITION`; Core's accepted position is reapplied to Tk.
Before date navigation, Tk flushes a pending scroll save. On rebuild, Tk waits
for a stable workspace geometry generation before restoring that fraction.

The Tk shell follows the 03 cockpit palette. The row rail carries inert
`1`/`2`/`3`/`x` controls beside the working row arrows.
