# Core / Mem seam

Core creates Mobile Stacks for `GET_DAY_LAYOUT`, `GET_PANEL`, panel updates,
and canonical hosting changes.

Mem places an independent copy of `panel` in its registers and returns the
same stack to Core. Core copies retained result data into its reducer event
before the runtime drops the frame and possibly forwards the stack again.

Frames are stored bottom first: push `CORE / PANEL_RETURNED`, then
`MEM / GET_PANEL`. The last frame executes first.

For `HOST_PANEL`, Core first gets the panel, then asks Mem to change hosting.
Mem returns the accepted target position and any position it unhosted.

For `UPDATE_PANEL`, the stack carries `base-revision` and `proposed-panel`.
