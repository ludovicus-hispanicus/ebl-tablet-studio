# eBL Tablet Studio 1.0.0-rc.2

Second release candidate. Everything from rc.1 remains; this one adds a
RAW-to-TIFF converter, loose-photo handling in the Picker, a live Results
dashboard during batch runs, plus macOS and Linux installers (rc.1 shipped
Windows only).

## What's new since rc.1

### New
- **RAW → TIFF converter** in the Picker's new **Conversion** tab —
  three scopes (selected / all-in-folder / entire project). 16-bit TIFFs
  land next to the source files; originals kept. Live per-file progress
  bar, streams the log into the Results Dashboard.
- **Picker tabs**: Selected / Conversion / Settings. Export target moved
  into Settings alongside per-folder stats.
- **Loose-file handling**: `(Loose files)` pseudo-entry at the top of the
  tree in both Picker and Renamer. Click to browse + select loose images
  at the root of your source / export folder.
- **Two grouping actions** in Picker Settings:
  - *Organize by filename (auto)* — groups `Si.32_01.jpg, Si.32_02.jpg, …`
    into `Si.32/`. Camera-default stems (`IMG_`, `DSC_`, etc.) skipped so
    you don't end up with a folder literally named `IMG`.
  - *Group selected into folder…* — pick thumbnails, type a name, files
    move into the new folder.
- **Live refresh during batch runs** — Results thumbnails and per-file
  "sent" badges appear as each tablet finishes, not only at the end.
  Conversion runs do the same: new TIFFs pop into the Picker grid live.
- **Tree refresh button** (`↻`) for picking up external changes.
- **Tree status placeholder** — faint empty `○` on every Renamer row now
  signals "click to set a status" even before any status exists.

### Changed
- RAW → TIFF output lands **beside the source file** (no `_converted/`
  subfolder). Plays nicer with the Renamer.

### Fixed
- macOS `.dmg` builds now succeed in CI — icon path + `.app` bundle copy
  fixes. Cross-platform installers ship on every tagged release.
- Text-prompt modal keyboard focus + button styling (couldn't type,
  unstyled OK/Cancel).
- Loose-files export: no longer crashes on missing subfolder; prompts
  for the tablet name instead.

See [`CHANGELOG.md`](CHANGELOG.md) for the complete list.

## Install

Pick the installer for your OS from the Assets below:

- **Windows 10/11 x64**: `…-win-x64-setup.exe` (NSIS, recommended) or
  `…-win-x64-portable.exe`.
- **macOS 12+ (Apple Silicon)**: `…-mac-arm64.dmg`. Right-click → Open on
  first launch (not code-signed yet).
- **Linux (glibc 2.31+)**: `…-linux-x86_64.AppImage`. `chmod +x` then
  double-click.

Auto-update picks up the next release automatically.

## Known issues

- Not code-signed on any platform. Gatekeeper / SmartScreen warns on
  first run — override manually.
- Deviation-Excel length column stays `N/A` until your measurements file
  carries both width and length per tablet.
- macOS Intel (x64) builds are not published — rebuild from source.

## Report issues

https://github.com/ludovicus-hispanicus/ebl-tablet-studio/issues

Include the Dashboard log pane contents for any processing-related bug.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
