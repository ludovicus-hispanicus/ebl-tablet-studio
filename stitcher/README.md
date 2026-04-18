# Stitcher (vendored)

Python backend for tablet image stitching, vendored from [`ebl-photo-stitcher`](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher) commit `v2.0-rc.16` as part of Phase B of the [merge plan](../docs/merge-plan.md).

## Status

**Step 2 of 7 complete — source vendored and validated to run.** The app still ships the downloaded standalone stitcher binary. The code here is source-of-record, proven to reproduce v2.0-rc.16 behavior, but not yet wired into the shipped installer.

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
