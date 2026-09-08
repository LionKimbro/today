# `mem.py`

OWNS: canonical in-memory `days` and `panels`.

`GET_PANEL` deep-copies the requested panel into the current stack registers.
The canonical record stays owned by Mem, including nested mutable data.
