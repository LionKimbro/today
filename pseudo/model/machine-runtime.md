# Machine runtime

| Field | Meaning |
| --- | --- |
| `name` | Machine identity: `CORE` or `MEM` |
| `inbox` | One blocking queue |
| `current-stack` | Stack being handled, else `None` |
| `handlers` | Entry → machine handler |
| `running` | Lifecycle state |

`machine.machines[name]` maps each identity to its runtime dictionary. A machine
claims its runtime on its own thread; it does not use `g["runtime"]`.

One machine thread has at most one active `current-stack`.
