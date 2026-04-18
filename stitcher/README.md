# Stitcher (vendored)

Python backend for tablet image stitching, vendored from [`ebl-photo-stitcher`](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher) commit `v2.0-rc.16` as part of Phase B of the [merge plan](../docs/merge-plan.md).

## Status

**Hybrid architecture decided.** Automatic tablet extraction stays on **rembg + U2NET** (via onnxruntime). Interactive SAM segmentation continues to live in the Electron UI (`src/main/sam-onnx.js` in the renamer). Torch + torchvision + mobile-sam pip dropped from `requirements.txt` since nothing uses them at runtime anymore.

Phase B effective plan after the decision:
1. ✅ Source vendored (step 1)
2. ✅ Validated against v2.0-rc.16 (step 2, Si.49 TIFF byte-identical)
3. ⬜ Build with PyInstaller locally, drop into `resources/stitcher/` (step 3)
4. ⬜ CI builds from vendored source (step 4)
5. ❌ ~~Swap rembg → SAM~~ — **reverted**. SAM is a promptable model; U2NET is the right tool for salient-object auto-extraction. See Step 5 post-mortem below.
6. ⬜ Delete `lib/gui_workflow_runner.py`'s tkinter bits and rename → `workflow_runner.py` (step 6)
7. ⬜ Archive old `ebl-photo-stitcher` repo (step 7)

### Step 5 post-mortem — why rembg stayed

Swapped `object_extractor_rembg.py` for a SAM ONNX implementation, tested on Si.32 / Si.49 / Si.58 / Si.77, and backed out.

**What worked:** Si.32 and Si.49 canvases within ~2% of baseline. Single-center-point SAM produced deterministic output. EXIF orientation was tricky (fixed with `ImageOps.exif_transpose`).

**What failed:** thin-edge tablet views where the tablet is a narrow horizontal strip against a tall foam support. SAM variants tried:
- **Center-point prompt:** if center lands on foam, SAM returns foam. Si.77 catastrophically picked foam on several views even when dimensions coincidentally matched rembg-baseline sizes.
- **4×4 grid of points (16 masks OR-ed):** produced "whole image" masks because accumulated foreground exceeded max-coverage filters. Canvases blew out to 4000×6000 (full image).
- **80% box prompt:** Si.58_03 and Si.58_04 top/bottom edge views — SAM's 4 multimask outputs never included the thin-tablet-strip shape. SAM consistently preferred the vertical foam support (higher IoU confidence) regardless of which output was chosen.

**Why no amount of prompt tuning fixes this:** SAM is *promptable segmentation* (segment the object at this prompt). U2NET is *salient object detection* (emit all foreground). They solve different problems. Making SAM bigger (SAM 2 base+ / large / HQ-SAM) produces sharper boundaries but the same wrong object — a cleaner answer to the wrong question.

**Conclusion:** use each model for its trained purpose.

### Architecture

- `lib/object_extractor_rembg.py` — active. Automatic extraction. rembg calls u2net via onnxruntime, as v2.0-rc.16 did.
- `lib/object_extractor_sam.py` — kept on disk, not imported. Has the ONNX-only SAM extractor we wrote in step 5 with the EXIF fix. Starting point if we ever want to revisit SAM-for-auto (e.g. SAM refining an initial U2NET mask).
- `lib/object_extractor.py` — contour-based legacy path. Unchanged.
- Electron `src/main/sam-onnx.js` (in the renamer) — interactive manual SAM via onnxruntime-node. Unchanged, works.

### Dependencies

- Kept: `rembg`, `onnxruntime`, `opencv-python`, `pyexiv2`, `rawpy`, `Pillow`, `numpy`, `scikit-image`, `scipy`, `cairosvg`, `pandas`, `openpyxl`, etc.
- Dropped: `torch`, `torchvision` (PyInstaller already excluded them; now also gone from requirements.txt).
- Not added: `mobile-sam` pip package (we use the ONNX export, not the PyTorch model).

### Earlier status

- Step 2 (2026-04-18): vendored source validated against v2.0-rc.16. Si.49 TIFF byte-identical; Si.32 3-pixel rembg noise.
- Step 1 (2026-04-18): source imported from `ebl-photo-stitcher @ v2.0-rc.16`, Tkinter GUI files excluded, measurements decoupled.

### Validation results (2026-04-18)

Ran the vendored `process_tablets.py` against the bundled v2.0-rc.16 binary on two sandboxed copies of the same tablet folder (Si.32 + Si.49, full clean-room re-run):

- Si.49 `.tif` output: **byte-for-byte identical** (169,932,670 bytes)
- Si.49 `.jpg` dimensions: **exact match** (7274×7787)
- Si.32 `.tif` output: 0.04% smaller (345 MB) due to 3-pixel canvas-layout drift from rembg non-determinism
- Si.32 `.jpg` dimensions: 9267×12374 vs 9270×12375 (3 px / 1 px difference)
- Wall-clock: **28 s for both tablets, identical to baseline**

Conclusion: vendored code reproduces upstream to within rembg's intrinsic floating-point noise floor. Ready to build with PyInstaller and swap in.

### Fixes applied during Step 2

1. `lib/gui_utils.py` restored as a 40-line stub. The full Tkinter original was deleted during Step 1, but `project_manager.py` imports `resource_path` and `get_persistent_config_dir_path` from it. The stub contains just those helpers plus `APP_NAME_FOR_CONFIG = "eBLImageProcessor"`. Module filename preserved to avoid a cross-file rename during vendoring (proper rename deferred to Step 6).
2. When running the vendored script directly (not via PyInstaller), set `PYTHONIOENCODING=utf-8` on Windows. The script prints Unicode ✓/✗ marks and the default cp1252 console crashes. PyInstaller bundles wrap stdout so this doesn't surface in packaged builds.

## What's here

- `lib/` — stitcher's image-processing modules (ruler detection, RAW processing, stitching, metadata).
- `process_tablets.py` — headless CLI entry point (unchanged from upstream).
- `assets/` — ruler templates (TIF/SVG), institution logo, project JSONs. **No tablet measurements** — per the Phase B plan, measurements are always user-provided via Settings, never bundled.
- `tests/` — Iraq Museum ruler-detection test fixtures.
- `requirements.txt` — Python deps, untouched pending rembg→SAM swap in Step 5.
- `eBL_Photo_Stitcher.spec` / `eBL_Photo_Stitcher_MacOS.spec` — PyInstaller specs, to be renamed and adapted.

## What's intentionally NOT here

- `gui_app.py` and `lib/gui_{advanced,components,config_handlers,config_manager,config_tab,events,layout,museum_options,utils}.py` — Tkinter GUI, replaced by the Electron UI.
- `gui_config.json` — Tkinter config file, unused after the merge.
- `assets/bm_measurements.json` — bundled measurement data, dropped per Phase B non-goal.
- `Examples/`, `docs/`, `img/`, `build/`, `dist/`, `__pycache__/`, `.venv/` — dev scratch.
- `build_executable.bat` — old Windows-only build script, to be replaced by our CI.
- `.github/workflows/` from upstream — we'll write fresh CI that fits our repo.

## What still runs today

Nothing from this folder. The Electron app is unchanged; it still bundles the pre-built standalone stitcher exe downloaded from the `ebl-photo-stitcher` repo release.

## Next steps (Phase B)

2. Set up Python venv, verify `process_tablets.py` produces outputs identical to v2.0-rc.16.
3. Build a local PyInstaller binary from this source; swap it into `resources/stitcher/`.
4. Move the build into our CI, drop the cross-repo download step.
5. Replace `lib/object_extractor_rembg.py` with a SAM-ONNX implementation (using the same `resources/models/sam/` ONNX files the renamer's segmentation uses).
6. Delete `lib/object_extractor_rembg.py`, rename `lib/gui_workflow_runner.py` → `lib/workflow_runner.py`, strip any residual tkinter imports.
7. Archive the standalone `ebl-photo-stitcher` repo.
