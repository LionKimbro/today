# `today.app`

OWNS: Stage 1's in-memory day, tab, position, panel records; their Tk view.

ENSURES:

```text
today -> Tab A -> position-1 hosts panel-1
```

DOES NOT OWN: persistence, threads, reducer, panel creation, layouts beyond
the one position.

```text
initialize world
create window
show date, tab, hosted panel
run Tk loop
```
