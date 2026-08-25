```
date: 2026-08-25
```

# Addendum — Per-Date Panel Configuration

Extend the experiment so that panel configuration is **per selected date**.

The current experiment effectively uses one global panel configuration regardless of which date is selected. That is not representative of the intended Today model.

Each date should have its own panel-position assignments.

Conceptually:

```text
selected date
    ↓
that date's layout/configuration
    ↓
panel positions
    ↓
semantic panel IDs occupying those positions
```

For example:

```python
day_state = {
    date_1: {
        "position_panel": {
            "position-1": "panel-a1",
            "position-2": "panel-a2",
        },
    },

    date_2: {
        "position_panel": {
            "position-1": "panel-b1",
            "position-2": "panel-b2",
        },
    },
}
```

The exact representation may differ.

## New-Date Initialization

When the user navigates to a date for which no Today configuration yet exists, allocate a default configuration immediately.

That should include:

```text
default panel positions
+
fresh unique semantic panel IDs
+
default panel types
+
default semantic state for each panel
```

For example, a newly encountered date might receive:

```text
position-1 → newly created TODO panel
position-2 → newly created JOURNAL panel
```

Those panel IDs must be unique to that date's semantic panel instances.

Do not reuse the previous date's panel IDs merely because the layout looks the same.

Therefore:

```text
2026-08-25 / position-1 / TODO
```

and:

```text
2026-08-26 / position-1 / TODO
```

should normally refer to two different panel IDs.

The positions may have the same names because they describe corresponding GUI locations.

The semantic panel instances must remain distinct.

## Date Navigation

When selected date changes:

```text
1. finish ordinary event processing
2. determine whether destination date already has configuration
3. if not, allocate default panel configuration and fresh panel IDs
4. load that date's position → panel assignments
5. reconfigure the persistent GUI hosts to display the panels assigned to the new date
6. restore each panel from that panel's own semantic state
```

Date navigation should therefore visibly demonstrate that the same panel host positions can display entirely different semantic panels depending on the selected date.

## Demonstration Behavior

The demo should make this easy to observe.

For example:

```text
Aug 25
    position-1 → Todo panel A
    position-2 → Journal panel B

navigate to Aug 26

Aug 26 is new:
    allocate Todo panel C
    allocate Journal panel D

edit/toggle them independently

navigate back to Aug 25

Todo panel A and Journal panel B return with their prior state

navigate again to Aug 26

Todo panel C and Journal panel D return with their prior state
```

This should prove:

```text
panel position identity
≠
panel semantic identity
≠
date identity
```

and that panel state follows the semantic panel ID rather than the visible position alone.

## Interaction with Panel Replacement

Panel replacement remains per-date.

If, on Aug 25, `position-1` is changed from its Todo panel to a Journal panel, that changes only Aug 25's configuration.

Aug 26's `position-1` assignment should remain whatever Aug 26 currently specifies.

Thus panel configuration belongs to the selected day's application state, not globally to the program.
