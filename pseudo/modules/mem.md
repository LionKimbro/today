# `mem.py`

OWNS: canonical in-memory `days` and `panels`.

`GET_PANEL` deep-copies the requested panel into the current stack registers.
The canonical record stays owned by Mem, including nested mutable data.

Stage 4 seeds `panel-1` and `panel-2`.

`UPDATE_PANEL` accepts only a matching base revision, then returns the accepted
canonical panel with its incremented revision.
