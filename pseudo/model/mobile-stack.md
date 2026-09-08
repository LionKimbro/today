# Mobile Stack

| Part | Carries |
| --- | --- |
| `frames` | Continuation control |
| `registers` | Traveling context |

The top frame is `{machine, entry}`. A machine handles it, drops it, then the
new top frame names the next destination.
