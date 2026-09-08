# Hosting

`positions[position-id]["panel-id"]` is the hosted panel identity.

| Position | Hosts |
| --- | --- |
| `position-1` | `panel-1` or `panel-2` |

Changing that id changes the host relationship. Neither panel is destroyed.

Panels carry `revision`. Mem accepts an update only when its base revision
matches the canonical revision.
