# `disk.py`

OWNS: JSON day-bundle files beneath the initialized Today data root.

`initialize_data_root` resolves MachineRoot's `db-root-2026` plus `today`,
or installs an explicit test root, in `g["data-root"]`. Main calls it before
opening Tk or starting workers. Missing MachineRoot configuration fails startup.

READS: `LOAD_DAY` Mobile Stacks.

WRITES: `WRITE_DAY` Mobile Stacks.

DOES NOT OWN: live application meaning, canonical Mem records, or Tk state.
