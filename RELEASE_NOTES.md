# eBL Tablet Studio 1.0.0-rc.1

**First release candidate.** Merges
[`tablet-image-renamer`](https://github.com/ludovicus-hispanicus/tablet-image-renamer)
and
[`ebl-photo-stitcher`](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher)
into one desktop app with a bundled Python stitcher. Zero-config install — no
Python or extra dependencies required.

## What's new since the 0.x betas

### New
- **Per-project settings** with a proper New / Delete flow in Settings.
- **Excel-driven measurements** with deviation-comparison Excel output.
- **Print vs Digital** output variants (primary views only vs. full composite
  with intermediate-view blends), or both in parallel.
- **Results dashboard** with live progress, highlighted log banners per
  tablet, and a project-scoped General Notes textarea.
- **Incremental result thumbnails** — each tablet pops into the grid as it
  finishes, not at the end of the batch.
- **Exported-tablet indicator** in the Picker tree with `(picked/total) ✓`.
- **Lens-correction hint** for RAW-sourced edge-hugging tablets (rare in your
  typical JPG workflow — stays silent then).

### Changed
- Stitcher is now built from vendored source at `stitcher/` with
  `npm run build-stitcher`. Default projects renamed to `General (white
  background)` / `General (black background)`.
- Measurements and review statuses land consistently in one place per
  batch instead of scattering per-subfolder.

### Fixed
- Folder switching from the single-image viewer no longer strands the
  viewer on a stale image.
- Stale per-subfolder measurement JSONs no longer block the measurement
  write / Excel finalizer.
- Source/export name normalization (`Si 41` vs `Si.41`) for the Picker ✓.

### Removed
- Tkinter GUI remnants, PyTorch, SAM auto-extractor (reverted), dead IPC
  plumbing, and bundled reference measurements.

See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

## Install

Pick the installer for your OS from the Assets below:

- **Windows 10/11 x64** — `eBL_Tablet_Studio-1.0.0-rc.1-win-x64-setup.exe`
  (NSIS installer with Start Menu entry + uninstaller) **or**
  `eBL_Tablet_Studio-1.0.0-rc.1-win-x64-portable.exe` (single-file portable —
  no install, run anywhere).
- **macOS 12+ (Apple Silicon)** — `eBL_Tablet_Studio-1.0.0-rc.1-mac-arm64.dmg`.
  First launch: right-click → Open to bypass Gatekeeper (not code-signed yet).
- **Linux (glibc 2.31+)** — `eBL_Tablet_Studio-1.0.0-rc.1-linux-x86_64.AppImage`.
  `chmod +x` then double-click.

Auto-update will pick up the next tagged release automatically.

## Known issues / limitations

- **Not code-signed on any platform yet.** Expect Gatekeeper / SmartScreen
  warnings on first run; override manually.
- Length column in the deviation Excel is `N/A` unless your Excel measurements
  file has both width AND length per tablet (current reader only captures
  width from column 2).
- macOS Intel (x64) builds are not published; rebuild from source if needed.
- `lensfunpy` is intentionally NOT bundled — you may see a one-line hint on
  RAW workflows where edge correction would have helped. No effect on output
  otherwise.

## Report issues

Open an issue at
https://github.com/ludovicus-hispanicus/ebl-tablet-studio/issues. Include the
content of the Dashboard log pane from the affected run if the problem
happened during processing.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
