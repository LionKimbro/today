# `mobile_stacks.py`

OWNS: stack records: `frames` for control, `registers` for traveling context.

PRIMITIVES: push/drop frame; set/get register.

Within a machine, primitives operate on that thread's current stack.
