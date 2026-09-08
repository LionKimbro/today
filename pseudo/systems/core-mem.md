# Core / Mem seam

Core creates a Mobile Stack: `MEM / GET_PANEL`, then `CORE / PANEL_RETURNED`.

Mem places an independent copy of `panel` in its registers and returns the
same stack to Core. Core copies retained result data into its reducer event
before the runtime drops the frame and possibly forwards the stack again.

Frames are stored bottom first: push `CORE / PANEL_RETURNED`, then
`MEM / GET_PANEL`. The last frame executes first.
