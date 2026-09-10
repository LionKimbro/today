# Disk storage

Root, for now: `C:\lion\installed\lions-today-db`

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

Mem loads an unseen day through Disk. Mem remains canonical while running and
coalesces its changed day writes after one quiet second; shutdown flushes them.
