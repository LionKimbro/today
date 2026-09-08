# `mobile_stacks.py`

OWNS: stack records: `frames` for control, `registers` for traveling context.

PRIMITIVES: create stack; `stack()`; `top()`; push/drop frame; set/get register.

Within a machine, primitives operate on that thread's current stack.
Creating a stack while another is active is an error.
