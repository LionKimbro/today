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

`install_machine_kind(kind, handlers)` defines behavior for dynamic instances.
A top frame with `machine: {new: KIND}` creates a uniquely addressed runtime
and worker under the registry lock, replaces the frame destination with that
address, and publishes the stack. Later frames address the same instance.

`continue_with_frames` records bottom-first continuation frames. Runtime pops
the handled frame before appending these, allowing an instance to visit Mem
or Disk and receive its stack back. `request_machine_retirement` marks stopping
without interrupting the current handler's final stack handoff. The wrapper
marks exited; main's `reap_exited_machines` joins and removes the address.

`begin_shutdown` prevents creation and wakes dynamic instances. Late dynamic
work is abandoned during application shutdown. Normal Mem-to-Disk final writes
still route; fatal shutdown abandons all ordinary routing. Outside shutdown,
routing to a stopping/exited/missing address raises an error.
