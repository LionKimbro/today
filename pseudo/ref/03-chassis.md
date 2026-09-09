# 03 chassis archaeology

Source: `src/parts/03_combined-model.py`. It is working evidence, not source to
port.

## Grammar

```text
top area
    -> page tab
        -> vertical rows
            -> 1–3 horizontal panes
                -> panel host
status bar
```

Each date owns a workspace. A page tab owns its rows. A pane hosts a distinct
panel identity.

## Working 03 interactions

- select, add, rename, and delete page tabs
- add/delete rows; choose one, two, or three panes; resize rows and pane sashes
- choose a panel kind for a pane
- move between date workspaces; show that date's orientation panel

## Carry forward as meaning

- layout belongs to the selected tab and day
- positions host panels; panels have separate identity and state
- pane count, row height, and sash proportions are layout state

## Do not carry forward as mechanism

- tuple position addresses such as `(tab-id, row, column)`; new positions need
  durable identities before layout editing
- broad Tk workspace rebuilds for ordinary semantic changes

## Source/document gaps

- 03 implements whole-page tabs. The per-pane `TabbedHost` described elsewhere
  is a later proposal, not 03 behavior.
- 03's source does not make the documented scrolling-row workspace real.
