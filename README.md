# Today / Temple of Focus

A daily cockpit built as cooperating machines. The runnable `src/today/`
package is the Stage 3 skeleton; `src/parts/` contains earlier experiments.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m today
python -m unittest discover -s tests -v
python tests/gui_failure_smoke.py normal
python tests/gui_image_smoke.py
```

Today requires Python 3.11+ and the `machine-root` package. Its data directory
is MachineRoot's `db-root-2026` entry followed by the `today` subdirectory.
Missing registry configuration fails before the window or workers start.

Image panels accept clipboard images, a file chooser, or a dropped JPEG, PNG,
or GIF. Images fit the panel; GIFs display their first frame. Clear image returns
to the import controls. Files are copied into the owning day's `assets/` folder;
clearing or deleting a panel keeps those files. Pillow and tkinterdnd2 provide
image preparation and native file drops.

Image work runs in router-created machines with unique addresses. Machines
can visit other machines and resume before explicitly retiring. The main
thread joins and reaps them; uncaught worker failures remain process-fatal.

Tests can run the application with an exact temporary root:

```python
from tempfile import TemporaryDirectory
from today.main import main

with TemporaryDirectory() as directory:
    main(data_root=directory)
```

This override bypasses the registry lookup and uses the directory directly.

The GUI checks require a desktop. Failure-check modes are `CORE`, `MEM`, and
`DISK`; run each in a fresh process. Image controls and rendering are checked
by `gui_image_smoke.py`.

See [the architecture reconstruction](docs/architecture-review.md) for the
machine model, observations, remaining questions, and candidate lessons for
review. The bounded implementation sketches live in `pseudo/`.
