# `machine.py`

OWNS: blocking inbox runtime, current stack, frame dispatch, stack routing.

`None` stops a machine. A handled frame is dropped, then its stack routes by
the newly exposed top frame, including when that is the same machine.

Reject receiving a second stack while one is active. Routing clears the local
current-stack slot before publishing the stack to the destination queue.
Stage 3 handlers leave frame removal and routing to this runtime.
