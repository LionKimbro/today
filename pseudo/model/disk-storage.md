# Disk storage

Root: `Path(machineroot.get("db-root-2026")) / "today"`, resolved at startup.
Tests can pass an exact root to `main(data_root=...)`; no `today` suffix is
appended to that override. Importing Today does not read the registry.

```text
YYYY/
  YYYY-MM/
    YYYY-MM-DD/
      YYYY-MM-DD.json
      assets/
      files/
```

The JSON file is one complete `today-day-v1` bundle: day, tabs, rows,
positions, and that day's panels. Disk writes a temporary JSON file, then
replaces the day file.

Image files live in `assets/image-<uuid>.jpg|png|gif`. Panel JSON stores only
the relative `assets/...` reference after Disk has written the asset. Files
are preserved when panels are cleared or deleted; cleanup is deferred.

Mem loads an unseen day through Disk. Mem remains canonical while running and
coalesces its changed day writes after one quiet second; shutdown flushes them.
