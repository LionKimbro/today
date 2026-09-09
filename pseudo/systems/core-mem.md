# Core / Mem seam

Core creates Mobile Stacks for `GET_DAY_LAYOUT`, `GET_PANEL`, panel updates,
canonical hosting changes, and selected-tab changes.
Row geometry also crosses this seam as canonical `SET_ROW_HEIGHT` and
`SET_SASH_PROPORTIONS` operations.
`MOVE_ROW` returns the changed canonical tab record for structural rendering.

Mem places an independent copy of `panel` in its registers and returns the
same stack to Core. Core copies retained result data into its reducer event
before the runtime drops the frame and possibly forwards the stack again.

Frames are stored bottom first: push `CORE / PANEL_RETURNED`, then
`MEM / GET_PANEL`. The last frame executes first.

For `HOST_PANEL`, Core first gets the panel, then asks Mem to change hosting.
Mem returns the accepted target position and any position it unhosted.

For `UPDATE_PANEL`, the stack carries `base-revision` and `proposed-panel`.
