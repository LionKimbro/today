# `mem.py`

OWNS: canonical in-memory `days` and `panels`.

`GET_PANEL` deep-copies the requested panel into the current stack registers.
The canonical record stays owned by Mem, including nested mutable data.

Stage 5 seeds `whiteboard-a` and `whiteboard-b` with canonical text and revision.

Whiteboard records also canonically carry newest-first snapshot history.

`UPDATE_PANEL` accepts only a matching base revision, then returns the accepted
canonical panel with its incremented revision.
