# Runtime / stack passage

Normal machine code uses its thread's current runtime and stack.

- Runtime record: passed only to `install_machine()` during startup.
- Stack record: passed from an inbox into `handle_received_mobile_stack()`.
  That handoff alone calls `install_current_stack()`.
- Routing carries the active stack directly to the destination inbox.
