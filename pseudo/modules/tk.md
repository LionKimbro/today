# `tk.py`

OWNS: widgets, bindings, Tk-side semantic events, Core-command realization.

READS: plain Core commands.

DOES NOT OWN: Today state or decisions.

The hosted-panel combobox sends `HOST_PANEL`; it does not swap panels itself.

Text input resets one 1-second debounce. Its expiry sends generic
`TEXT_DEBOUNCE`; Tk does not decide whether to save.

Tk renders the history slider, Snapshot button, and status. Their events ask
Core to select or snapshot a version; Tk does not interpret history.

Rename stays disabled until Core renders the panel. Its callback uses the
rendered panel identity. A late render does not re-enable it during closing.
