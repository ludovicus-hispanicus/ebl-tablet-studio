# Changelog

All notable changes to eBL Tablet Studio are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc.1] — 2026-04-21

First release candidate — the merge of
[tablet-image-renamer](https://github.com/ludovicus-hispanicus/tablet-image-renamer)
and
[ebl-photo-stitcher](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher)
into a single desktop application with a bundled Python backend.

### Added

- **Unified Electron app** with two modes: *Picker* (select + export source photos)
  and *Renamer* (rename + segment + stitch exported batches).
- **Automatic tablet extraction** via rembg + U2NET (onnxruntime), bundled at
  `resources/stitcher/eBL.Photo.Stitcher.exe`. No Python install needed.
- **Interactive SAM segmentation** via onnxruntime-node for click-to-refine
  manual tablet extraction in the Picker.
- **Multi-view stitching** into a single composite with digital ruler overlay,
  EXIF/XMP/IPTC metadata embedding, and optional institution logo.
- **Print vs Digital output variants** — `Digital` includes intermediate views
  with gradient blends; `Print` stitches only the six primary views (_01–_06)
  for book/catalogue reproduction. `Both` produces both in parallel with
  shared upstream work. Output routes to `_Final_JPG/` / `_Final_JPG_Print/`.
- **Excel-driven measurements** — feed in a measurements file per project;
  stitcher derives scale from the reference width and produces
  `calculated_measurements.json` plus a deviation-comparison Excel using the
  user-supplied measurements as the reference.
- **Per-project settings** — photographer, institution, credit line, usage
  terms, logo, measurements file, ruler template. New/Delete project buttons
  in Settings.
- **Results dashboard** — live progress bar, log pane (with highlighted
  tablet-start banners and measurement-related lines), per-batch "General
  notes" textarea. Separate Detail view for per-tablet notes and metadata.
  Detail notes disabled until a thumbnail is selected.
- **Incremental results refresh** — new thumbnails pop into the grid as each
  tablet finishes, rather than appearing all at once at the end of the run.
- **Per-variant review status** — yellow "sent" badge is scoped per
  variant (digital / print) so stale variants from earlier runs don't get
  marked as "just reprocessed".
- **Per-tablet review status** (yellow / green / red / grey) persisted in
  `review_status.json`, with tree icons, status cycling via keyboard or
  context menu, and live-collaboration refresh (re-reads the shared status
  file every 10s).
- **Exported-tablet indicator in the Picker** — tree rows show `(picked/total)`
  and a green ✓ when the source has a matching export folder.
- **Auto-update** via `electron-updater` (GitHub releases provider).
- **Lens-correction hint** — flags RAW-sourced tablets with edge-hugging bbox
  where `lensfunpy` would have measurably improved output. Silent on JPG
  workflows. Summary tally in the processing summary.
- **Zero-config install** — single installer per OS, no system Python needed.

### Changed

- **Bundled stitcher**: built from vendored source at `stitcher/` via
  `npm run build-stitcher` (PyInstaller). No longer downloaded from the
  standalone `ebl-photo-stitcher` release.
- **Project renames** — the old museum-specific presets were retired in favor
  of generic backgrounds:
  - `Non-eBL Ruler (VAM)` → `General (white background)`
  - `Black background (Jena)` → `General (black background)`
- **Measurement records consolidate at the main folder**. Previously each
  tablet subfolder held its own `calculated_measurements.json`, which
  short-circuited downstream consumers. Now both the ruler-detection and
  Excel-driven paths write to `<source>/_Selected/calculated_measurements.json`
  so the Excel finalizer and the `DeviationReport.xlsx` see the results.
- **Stitcher metadata** rewritten — `Xmp.dc.subject` carries tablet ID,
  XResolution/YResolution emitted in px/cm when scale is known, full IPTC-IIM
  block, DateTime fields, `dc.identifier/publisher/date/type`,
  `photoshop:Headline`.

### Removed

- **PyTorch, torchvision, torchaudio** from the stitcher bundle — never called
  at runtime after the SAM experiment was reverted.
- **SAM auto-extractor** (`lib/object_extractor_sam.py`) — tested, reverted to
  rembg+U2NET on thin-edge views where SAM misidentified tablet vs foam
  support (see `stitcher/README.md` for the post-mortem).
- **Tkinter GUI remnants** from the upstream stitcher — `gui_app.py`,
  `lib/gui_*.py`, `gui_config.json`, `manual_ruler_gui.py`'s invocation path
  (the file itself is kept for a future Electron manual-ruler overlay).
- **Dead IPC plumbing** — `autoDetectStitcher`, `selectStitcherExe`,
  `offStitcherProgress`, and the segmentation-server start/stop/status APIs
  that predated the in-process SAM preload.
- **Dead Python modules** — `image_merger.py`, `stitch_processing_utils.py`,
  `stitch_utils.py`, `version_checker.py`, legacy `bm_measurements.json` bundled
  reference data.

### Fixed

- Stale per-subfolder `calculated_measurements.json` files from older runs no
  longer short-circuit the measurement-write pipeline for either the
  ruler-detection or Excel-driven path.
- Picker folder switching from within the single-image viewer now returns to
  the new folder's grid instead of keeping the old image open.
- Post-export tree refresh respects current mode — picker stays on its source
  tree instead of swapping to the renamer's Selected tree.
- Exported-match detection normalizes `Si 41` (space) vs `Si.41` (dot) so the
  Picker ✓ fires correctly for already-exported tablets.
- `lensfunpy` absence is now reported once per run (at first actual need)
  instead of on every Python import.
- Results log pane: banners for each tablet, distinct styling for
  measurement lines (green left-border), no more buffer growing by
  `textContent +=` on each line.

### Notes for packagers

- Installer sizes: Windows NSIS ≈ 230 MB, portable exe ≈ 200 MB, Linux
  AppImage ≈ 250 MB, macOS DMG ≈ 220 MB (arm64). Bundle dominated by the
  vendored Python runtime + ONNX Runtime + onnx models.
- Auto-update metadata is published per release via electron-builder's
  `publish: github` config.
- Minimum Windows: Windows 10 x64. Minimum macOS: 12 (Monterey) on Apple
  Silicon. Linux: glibc 2.31+.

---

All earlier versions were development betas (`v0.1.x-beta.1`, `v0.2.0-beta.1`)
and have been removed from GitHub releases. Their git history is preserved.
