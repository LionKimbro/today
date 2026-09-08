# `tk.py`

OWNS: widgets, bindings, Tk-side semantic events, Core-command realization.

READS: plain Core commands.

DOES NOT OWN: Today state or decisions.

The hosted-panel combobox sends `HOST_PANEL`; it does not swap panels itself.

Rename stays disabled until Core renders the panel. Its callback uses the
rendered panel identity. A late render does not re-enable it during closing.
