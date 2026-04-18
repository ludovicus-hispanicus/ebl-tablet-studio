# Stitcher (vendored)

Python backend for tablet image stitching, vendored from [`ebl-photo-stitcher`](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher) commit `v2.0-rc.16` as part of Phase B of the [merge plan](../docs/merge-plan.md).

## Status

**Step 1 of 7 complete — source vendored, not yet built or wired in.** The app still ships the downloaded standalone stitcher binary. The code here is purely source-of-record until we build + swap.

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
