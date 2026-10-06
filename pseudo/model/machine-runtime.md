# Machine runtime

| Field | Meaning |
| --- | --- |
| `name` | Unique machine address, permanent or dynamically assigned |
| `inbox` | One blocking queue |
| `current-stack` | Stack being handled, else `None` |
| `handlers` | Entry → machine handler |
| `running` | Worker loop compatibility flag |
| `lifecycle` | starting → running → stopping → exited → reaped |
| `thread` | Worker handle; main joins before registry removal |
| `dynamic` | Instance created by routing a new-machine destination |
| `continuation-frames` | Bottom-first frames appended after current frame removal |

`machine.machines[name]` maps each identity to its runtime dictionary. A machine
claims its runtime on its own thread; it does not use `g["runtime"]`.

One machine thread has at most one active `current-stack`.

A waiting instance remains running while its stack visits another machine.
Its handler explicitly requests retirement; completion of one delivery never
retires it automatically. Registry membership and lifecycle transitions use
`machines_lock`. Only main reaps an exited runtime, after joining its thread.
