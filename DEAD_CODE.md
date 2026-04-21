# Dead Code Tracker

Notes worth keeping across audits. Last pass: 2026-04-21.

## Deferred

- **`stitcher/lib/manual_ruler_gui.py`** (~221 lines) — Tkinter fallback for when auto ruler detection fails. Imported only under `if force_manual_ruler: ...` in `workflow_scale_detection.py:233`. That flag is hardcoded `False` in headless runs, so the code never executes. **Don't delete** until the Electron manual-ruler overlay replaces this path, at which point both can go together.

## Don't re-flag: transitive Python deps

A previous audit flagged seven packages in `stitcher/requirements.txt` as "no direct imports, safe to drop." Re-verified 2026-04-21 with `pip show <pkg>`: all seven are transitive deps of packages we DO use directly. Removing them from the pins is cosmetic — pip reinstalls them, and the PyInstaller bundle size doesn't change.

| package        | pulled in by                               |
|----------------|--------------------------------------------|
| `scikit-image` | `rembg`                                    |
| `scipy`        | `rembg` → `pymatting`, `scikit-image`      |
| `cairocffi`    | `cairosvg`                                 |
| `tinycss2`     | `cairosvg`, `cssselect2`                   |
| `cssselect2`   | `cairosvg`                                 |
| `defusedxml`   | `cairosvg`                                 |
| `webencodings` | `cairosvg`, `tinycss2`                     |

Only prune an entry if we stop using its parent (e.g. if `cairosvg` were replaced, the five Cairo-related entries could follow it out).

## Refactor targets (alive, just large)

Not dead — called out so future drive-bys don't mistake them for dead code:

- `src/renderer/js/app.js` — ~3,600 lines. Candidate for splitting by concern.
- `src/main/main.js::rotateAndSave` — 351-line function.
- `src/main/main.js::prepareHistoryForApply` — 228 lines.
- `stitcher/lib/gui_workflow_runner.py` — ~770 lines. Rename to `workflow_runner.py` and strip residual tkinter imports when it's next edited.
