# `machine.py`

OWNS: blocking inbox runtime, current stack, frame dispatch, stack routing.

`None` stops a machine. A handled frame is dropped, then its stack routes by
the newly exposed top frame.
