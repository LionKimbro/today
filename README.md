# Today / Temple of Focus

A daily cockpit built as cooperating machines. The runnable `src/today/`
package is the Stage 3 skeleton; `src/parts/` contains earlier experiments.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m today
python -m unittest discover -s tests -v
python tests/gui_smoke.py normal
```

The GUI smoke check requires a desktop. Other modes are `delayed`,
`early-close`, and `sentinel`; run each in a fresh process.

See [the architecture reconstruction](docs/architecture-review.md) for the
machine model, observations, remaining questions, and candidate lessons for
review. The bounded implementation sketches live in `pseudo/`.
