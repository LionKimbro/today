# `disk.py`

OWNS: JSON day-bundle files beneath the initialized Today data root.
Also owns stored image assets inside each day's `assets/` directory.

`initialize_data_root` resolves MachineRoot's `db-root-2026` plus `today`,
or installs an explicit test root, in `g["data-root"]`. Main calls it before
opening Tk or starting workers. Missing MachineRoot configuration fails startup.

READS: `LOAD_DAY` Mobile Stacks.

WRITES: `WRITE_DAY` Mobile Stacks.

WRITE_IMAGE_ASSET accepts validated image bytes and a JPEG/PNG/GIF extension,
creates `assets/image-<uuid>.<extension>` through a temporary file and rename,
and returns the day-relative `image-asset` reference. READ_IMAGE_ASSET accepts
only that generated reference shape and returns bytes for Image to decode.
Expected file errors are returned in `image-error`, not raised as worker deaths.
Image bytes never become part of a day bundle. Clearing or deleting an Image
panel removes its reference but retains asset files; cleanup is not automatic.

DOES NOT OWN: live application meaning, canonical Mem records, or Tk state.
