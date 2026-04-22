# TODO

Small known issues and follow-ups that aren't urgent.

## Auto-classify loose photos into tablet subfolders

When the user opens a folder in the Picker that contains photos at the root
(e.g. `Si.32_01.jpg`, `Si.32_02.jpg`, `Si.33_01.jpg`, ...) **without** per-tablet
subfolders, the app currently shows an empty tree — the user sees a "circulo
vacío" state instead of the photos they just opened. The old
`tablet-image-renamer` auto-grouped those files into `<TabletID>/` subfolders
using the filename pattern.

The stitcher side already has this logic at
[`stitcher/lib/put_images_in_subfolders.py`](stitcher/lib/put_images_in_subfolders.py)
— it groups files matching `<id>_<view>.<ext>` (e.g. `Si.32_01.jpg`,
`Si.32_ob.jpg`) into a `Si.32/` folder. It just isn't reachable from the
Electron UI.

### Desired behavior

Two acceptable flavors:

- **Auto-detect + confirm (preferred)**: on folder open in Picker, if the
  scan finds loose photos but zero subfolders, show a one-time prompt:
  *"This folder contains N photos not grouped into tablet subfolders.
  Organize them automatically? (groups by filename stem — `Si.32_01.jpg`
  → `Si.32/`)"*. Yes runs the grouper; No leaves the folder as-is.
- **Manual action button**: a toolbar button in the Picker labeled
  "Organize loose photos" that's enabled whenever the scan detects files
  at root that match the pattern. No auto-prompt.

Start with the auto-detect+confirm flow; it's the pattern the old renamer
used and matches "I just dumped my photos here, do something with them."

### Implementation sketch

1. **Scan side** — extend [`src/main/file-ops.js`](src/main/file-ops.js)'s
   `scanFolder` (or add a companion IPC) to also return loose image files at
   the root, not just subfolders. Today it ignores root-level files.
2. **Grouper IPC** — new `organize-loose-photos` handler in
   [`src/main/main.js`](src/main/main.js). Port the regex + move logic from
   `put_images_in_subfolders.py` into Node (or shell out to it — simpler but
   a heavier hop). Node port is ~30 lines and avoids a Python round-trip for a
   pure filesystem operation.
3. **Renderer** — in [`src/renderer/js/app.js`](src/renderer/js/app.js) after
   `scanFolder`, if result has loose photos AND zero subfolders, show the
   confirm dialog and call the new IPC. After it returns, rescan + rebuild
   the tree.
4. **Regex** — match the stitcher's pattern so the two paths behave
   identically:
   ```
   (.+)_(\d+|ob|ol|or|rl|rr|rt|rb|ot|ob2|...)\.(jpg|jpeg|tif|tiff|png|cr2|cr3|nef|arw)
   ```
   (see `generate_subfoldering_pattern()` in `put_images_in_subfolders.py`).
5. **Edge cases** — files that don't match the pattern stay at root (and are
   reported count-only in the confirm dialog). Collisions (existing subfolder
   same name) merge; don't overwrite existing files on name conflict.

### Why move to JS (not call Python)

A Python round-trip for a pure file-rename operation means users need the
stitcher binary present even just to open an unorganized folder. Keeping the
organizer in Node means the Picker can auto-organize before the stitcher
binary is ever invoked. Around 30 lines of Node maps cleanly onto the Python
original.

## Ruler output placement

The UI Ruler-position field currently says "Ruler is placed at the bottom" because
[stitcher/lib/stitch_layout_calculation.py:453-471](stitcher/lib/stitch_layout_calculation.py#L453-L471)
hardcodes ruler placement at the end of the vertical stack. The old
`--ruler-position` flag still exists on the CLI, but it only controls the
*detection ROI* (where the stitcher looks for the ruler inside the raw photo),
not where the digital ruler is rendered in the composite.

**To enable configurable output placement:**
- Thread `ruler_position` through `calculate_stitching_layout` in
  [stitch_layout_calculation.py](stitcher/lib/stitch_layout_calculation.py)
  (via `stitch_images.py` → `process_tablet_subfolder`).
- Add branches: `"top"` inserts the ruler row before obverse; `"left"` /
  `"right"` rotate the ruler 90° and place it as a vertical strip. `"bottom"`
  is current behavior.
- Re-enable the `<select>` in the Settings UI
  ([src/renderer/index.html](src/renderer/index.html)) — the saved field
  `project.fixed_ruler_position` is still present so no migration needed.

Pick this up only if a user requests non-bottom placement.

## Dublin-Core description polish

`dc.description` and EXIF `ImageDescription` both currently carry the tablet ID
(same value as `dc.title`). By Dublin Core they should hold a longer account
(e.g. `"Cuneiform tablet Si.22 — stitched composite, six views."`). Decide on
a template and swap in — minor metadata-cleanliness item, not user-visible.

---

## Already done (kept here briefly for the changelog trail)

- ✅ Two output types (Digital / Print / Both) — wired end-to-end in v1.0.0-rc.1.
- ✅ Built-in project renames (`General (white/black background)`) — shipped.
- ✅ Stitcher metadata (EXIF/XMP/IPTC) — shipped with the rebuilt binary.
- ✅ CI build for `npm run build-stitcher` across Windows / macOS / Linux —
  [`.github/workflows/release.yml`](.github/workflows/release.yml) builds
  all three platforms on every tag push.
