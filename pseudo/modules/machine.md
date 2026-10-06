# `machine.py`

OWNS: blocking inbox runtime, current stack, frame dispatch, stack routing.

`None` stops a machine. A handled frame is dropped, then its stack routes by
the newly exposed top frame, including when that is the same machine.

Reject receiving a second stack while one is active. Routing clears the local
current-stack slot before publishing the stack to the destination queue.
Stage 3 handlers leave frame removal and routing to this runtime.

Required workers enter through `run_worker`. An uncaught BaseException prints
its traceback and calls `when_thread_dies_unexpectedly`. That function latches
`a_thread_died_unexpectedly` and wakes all worker inboxes with `None`, once
under a lock. Fatal shutdown abandons ordinary work at dispatch boundaries;
an already executing operation returns to its next boundary. The wrapper
clears runtime lifecycle and active-stack state on exit.
