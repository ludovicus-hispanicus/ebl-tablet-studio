# eBL Tablet Studio

Unified desktop application for cuneiform tablet image processing. Successor to [tablet-image-renamer](https://github.com/ludovicus-hispanicus/tablet-image-renamer) and [ebl-photo-stitcher](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher) — combines their workflows into a single Electron app with a bundled Python backend.

## What it does

- **Image renaming** — rename raw photos by tablet view code (obverse, reverse, top, bottom, left, right, etc.) with project-aware metadata.
- **Interactive segmentation** — click-to-refine tablet extraction in the Electron UI, powered by a SAM ONNX model running in `onnxruntime-node`.
- **Automated stitching** — multi-view compositing, ruler detection, scale-based digital ruler overlay, EXIF/XMP metadata embedding, optional print/digital variants.
- **Zero-config install** — single installer per OS; the Python stitcher is bundled as a PyInstaller `.exe` next to the Electron app.

## Install

Download the installer for your platform from
[Releases](https://github.com/ludovicus-hispanicus/ebl-tablet-studio/releases):

- **Windows 10/11 (x64)** — `eBL_Tablet_Studio-<version>-win-x64-setup.exe`
  (NSIS installer with Start Menu entry and uninstaller) or
  `-portable.exe` (single-file, no install).
- **macOS 12+ (Apple Silicon)** — `eBL_Tablet_Studio-<version>-mac-arm64.dmg`.
  First launch: right-click → Open (not code-signed yet).
- **Linux (glibc 2.31+)** — `eBL_Tablet_Studio-<version>-linux-x86_64.AppImage`.
  `chmod +x` and double-click.

Subsequent releases auto-update via `electron-updater`.

## Quick start

1. **Open a source folder** in the Picker. Tablet subfolders inside it appear
   in the tree with `(picked/total) ✓` for any that have already been exported.
2. **Select and export** the photos that belong to each tablet view
   (obverse, reverse, top, bottom, left, right, and optional intermediates).
3. **Switch to the Renamer** (tabs at the top) and review the exported tablets.
   Click thumbnails to refine segmentation manually if needed.
4. **Open Settings** and pick the active project — defaults `General (white
   background)` and `General (black background)` are included, or create a
   new one with **New**.
5. **Attach a measurements file** (Excel or JSON) in Settings if you want the
   stitcher to use known widths for scale calibration and produce a
   deviation-comparison Excel.
6. **Process** the ready tablets. Dashboard shows live progress, logs, and
   a tally of results. Each tablet appears in the grid as it finishes.

## Output

The stitcher writes composites to the batch root:

```
<root>/
├── _Final_JPG/            ← digital-variant JPG per tablet
├── _Final_TIFF/           ← digital-variant TIFF per tablet
├── _Final_JPG_Print/      ← print-only primary views (if output_type = print|both)
├── _Final_TIFF_Print/
├── calculated_measurements.json
├── measurement_comparison_<name>_<date>.xlsx  ← if a measurements file is attached
└── review_status.json     ← per-tablet review state, shared for collaboration
```

## Segmentation model split (why two)

Two different problems, two different tools. We tested swapping both to SAM and [reverted](stitcher/README.md#step-5-post-mortem--why-rembg-stayed) — each model is kept on the job it was trained for.

- **Automatic tablet extraction** (stitcher, per-view background removal) uses **rembg + U2NET** via `onnxruntime`. U2NET is a *salient-object* detector — it emits every foreground pixel in one shot, which is exactly what we need for a clean center-tablet mask across six views.
- **Interactive segmentation** (renamer, single-image click-to-refine) uses **SAM ONNX** via `onnxruntime-node`. SAM is a *promptable* segmenter — it excels at "segment the thing at this click", which matches the manual-correction flow.

Trying to make SAM do U2NET's job (grid-of-prompts, center-point, box prompts) failed on thin-edge tablet views where it confidently picked the foam support instead of the tablet. Trying to make U2NET do SAM's job loses the interactive refinement. Using each for its trained purpose was the sweet spot.

## Development

Active. See [stitcher/README.md](stitcher/README.md) for the Python backend, [docs/merge-plan.md](docs/merge-plan.md) for the original migration plan, and [TODO.md](TODO.md) for known follow-ups.

Local stitcher rebuild: `npm run build-stitcher` (requires Python + `pip install -r stitcher/requirements.txt pyinstaller`).

## License

MIT. See [LICENSE](LICENSE).
