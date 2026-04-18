# Dead Code Tracker

Audit from 2026-04-18. Items below are confirmed unused (zero importers, zero callers, verified by repo-wide grep). Each is kept on this list instead of being deleted immediately so the reasoning stays visible and removal order is deliberate.

Already removed:
- [x] `stitcher/lib/version_checker.py` — old standalone-stitcher auto-update checker. Wrong repo URL, stale `CURRENT_VERSION = "v1.0"`, dead tkinter imports, no callers. Superseded by `electron-updater` wired into the Electron main process (`src/main/main.js::initAutoUpdater`). Deleted 2026-04-18.
- [x] `seg-start-server` / `segStartServer` / `startSegServerIfNeeded()` — explicit "start segmentation server" step. Removed after SAM moved in-process via onnxruntime-node; sessions now preload during the splash so segmentation is ready before the user can click. Removed 2026-04-18.
- [x] `seg-stop-server` / `segStopServer` — orphan IPC API (the bridge's `stopServer()` is still called internally on `before-quit`). Removed 2026-04-18.
- [x] `seg-server-status` / `segServerStatus` — orphan status ping, no caller. Removed 2026-04-18.
- [x] `seg-progress` / `onSegProgress` / `offSegProgress` — no subprocess to stream progress from; obsolete. Removed 2026-04-18.

## Candidates — Python (stitcher/)

- [ ] **`stitcher/lib/image_merger.py`** (74 lines) — no importers. Name suggests a core role but nothing calls it; the actual stitching is in `stitch_images.py` et al. Safe delete.
- [ ] **`stitcher/lib/stitch_processing_utils.py`** (220 lines) — no importers. Easily confused with `stitch_file_utils.py` / `stitch_utils.py` / `stitch_image_processing.py` which ARE used. Safe delete.
- [ ] **`stitcher/lib/stitch_utils.py`** (201 lines) — no importers. Same family-of-stitch_* ambiguity as above. Safe delete.
- [ ] **`stitcher/lib/object_extractor_sam.py`** (371 lines) — the SAM-for-auto extractor from Phase B.5. Reverted to use rembg after it produced worse results on thin-edge views. Currently marked "parking lot for future SAM-assisted auto work." Delete for cleanliness (git history preserves it), or keep if you'd rather iterate on a SAM+U2NET hybrid later.
- [ ] **`stitcher/lib/manual_ruler_gui.py`** (221 lines) — Tkinter fallback for when auto ruler detection fails. Currently imported only under `if force_manual_ruler: from manual_ruler_gui import ...` in `workflow_scale_detection.py:233`. That flag is hardcoded `False` in headless runs, so the code never executes. **Defer deletion** until the Electron manual-ruler overlay (plan §B.1.5) replaces this path.

## Candidates — Electron IPC plumbing

These IPC APIs are defined in `src/main/main.js` and exposed on `window.api` via `src/main/preload.js`, but **never called from the renderer** (`src/renderer/js/app.js`). Each one has:
- an `ipcMain.handle('<channel>', ...)` in `main.js`
- a `<methodName>: () => ipcRenderer.invoke('<channel>', ...)` line in `preload.js`

Removing them means deleting both the handler and the preload line.

- [ ] **`autoDetectStitcher`** — leftover from the Phase A.4 "browse for stitcher exe" cleanup.
- [ ] **`selectStitcherExe`** — same leftover.
- [ ] **`deleteProject`** — defined but no Settings UI exposes it.
- [ ] **`newProject`** — defined but no Settings UI exposes it.
- [ ] **`onStitcherProgress` / `offStitcherProgress`** — off/on pair, neither is called.

Total: ~30 lines across main.js + preload.js (the seg-* APIs on this list were removed 2026-04-18 alongside the SAM-preload-at-splash refactor).

## Candidates — HTML DOM

3 ids in `src/renderer/index.html` that don't appear in `app.js` or `style.css`:

- [ ] `#project-config-fields` — wrapper div, never styled or scripted. Keeping it doesn't hurt; remove for cleanliness if we're editing that section anyway.
- [ ] `#seg-history-section` — placeholder section, never populated.
- [ ] `#tab-results` — a tab that was never wired up.

## Candidates — Python dependencies (stitcher/requirements.txt)

Direct imports nowhere in the `stitcher/` tree (grep-verified):

- [ ] **`scikit-image`** — zero `from skimage` / `import skimage` anywhere.
- [ ] **`scipy`** — zero `from scipy` / `import scipy` anywhere.
- [ ] **`cairocffi`** — transitive of `cairosvg`. Explicit pin adds nothing.
- [ ] **`tinycss2`**, **`cssselect2`**, **`defusedxml`**, **`webencodings`** — all transitive of `cairosvg`. Explicit pins are noise.

**Expected installer size savings once these are dropped from the PyInstaller bundle: roughly 20–40 MB.**

Keep (transitively used — grep flagged them initially but they're likely pulled in by rembg / pandas / pyexiv2):
- `tqdm`, `pandas`, `openpyxl`, `pyexiv2`, `cairosvg`, `onnxruntime`

## Candidates — JavaScript dependencies (package.json)

None confirmed dead. `electron-builder` was flagged by the audit but it's a build tool invoked via npm scripts, not a runtime import — false positive.

## Large-but-alive (refactor targets, not dead code)

Called out separately because these are live code, just big:

- `src/renderer/js/app.js` — 3,493 lines. Likely has some orphan branches from the Phase A.4 settings rework and the A.7 AppData migration. Needs per-function review.
- `src/main/main.js::rotateAndSave` — 351-line function, candidate for splitting.
- `src/main/main.js::prepareHistoryForApply` — 228 lines.
- `stitcher/lib/gui_workflow_runner.py` — 762 lines, largest file in the stitcher. Per plan step 6: rename to `workflow_runner.py` and strip any residual tkinter imports.

---

## Total impact if all candidates are removed

- **~1,087 lines of Python** (ignoring `manual_ruler_gui.py` which waits on the Electron overlay)
- **~100 lines of IPC boilerplate** in main.js + preload.js
- **~20-40 MB installer shrinkage** from dropping unused pip packages
- **Zero behavior change** — all items are provably unreferenced.
