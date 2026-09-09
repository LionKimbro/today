# Six steps of incorporating 07

## 7A — Archaeology

Read and map the old `03` layout: its visual regions, interaction vocabulary,
and which parts are geometry versus application meaning. No implementation
change.

## 7B — Static multi-position geometry

Bring in a small fixed arrangement of positions, with no dragging or resizing
yet. Prove Core-defined positions can host panels in the new shape.

## 7C — Multiple hosted panels

Move day/tab/row/position records into Mem, then let several visible positions
independently host and retain panels.

## 7D — Tabs, rows, and panes

Introduce the real layout grouping and canonical tab-selection semantics.

## 7E — Resize

Add splitter behavior while keeping Core authoritative over the resulting layout
meaning.

## 7F — Rearrangement

Add dragging or moving positions or panels only after the stable geometry and
hosting model are solid.
