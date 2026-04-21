# TODO

Small known issues and follow-ups that aren't urgent.

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

## Two output types: Print vs Digital

The Image Processing tab now exposes an "Output type" select that saves to
`project.output_type` (`"digital"` / `"print"` / `"both"`), default `digital`.
It is **not yet wired to the stitcher** — the selection is stored but all
runs still produce the current (digital-style) composite.

**Intended semantics:**
- **Digital** — current behavior. All available photos (including
  intermediate views `_ob`, `_ol`, `_or`, `_rl`, `_rr`, `_ot2`, etc.) with
  gradient blending at the overlaps. Rich, web-friendly composite.
- **Print** — only the six primary views `_01`–`_06` (obverse, reverse, top,
  bottom, left, right). No intermediates, no gradient blends. Clean, minimal
  plate for book/catalogue reproduction.
- **Both** — produce both variants side by side in separate subfolders.

**Output folder layout (option B — chosen):**

Separate subfolders per variant, so single-output projects stay byte-identical
to today and the print set can be published as a whole without filtering.

```
<root>/
  _Final_JPG/            ← digital (unchanged when output_type=digital)
    Si.32.jpg
  _Final_JPG_Print/      ← print variant, only appears when print is produced
    Si.32.jpg
  _Final_TIFF/
    Si.32.tif
  _Final_TIFF_Print/
    Si.32.tif
```

- `output_type = "digital"` → only `_Final_JPG/` and `_Final_TIFF/` are written.
- `output_type = "print"` → only `_Final_JPG_Print/` and `_Final_TIFF_Print/`
  are written (digital folders untouched / not produced).
- `output_type = "both"` → both pairs written. Stitcher runs the canvas twice
  with different view sets (full vs `_01`–`_06` only) and different final
  target folders; most of the pre-processing (object extraction, ruler
  generation, measurements) is shared.

**To implement:**
- Forward `project.output_type` via a new `--output-type` CLI flag in
  [src/main/main.js](src/main/main.js) + [src/main/stitcher-bridge.js](src/main/stitcher-bridge.js).
- Add the flag to argparse in
  [stitcher/process_tablets.py](stitcher/process_tablets.py).
- In [stitch_images.py](stitcher/lib/stitch_images.py) / the view-gathering
  step, filter intermediates out for the print pass. For `"both"`, run the
  stitch twice with different view sets.
- Update [stitcher/lib/stitch_output.py](stitcher/lib/stitch_output.py) to
  choose the output folder (`_Final_JPG` vs `_Final_JPG_Print`, same for
  TIFF) based on which pass is running.
- Update [src/main/results-ops.js](src/main/results-ops.js) `scanResults` to
  also scan `_Final_JPG_Print/` and tag those results with a `variant: "print"`
  badge so the Results panel distinguishes them.
- Update the Results-tab renderer ([src/renderer/js/app.js](src/renderer/js/app.js))
  to show a small "Print" badge on print-variant cards and group the digital
  + print pair for the same tablet visually.

## Built-in project renames (requires rebuild)

Two stitcher projects were renamed/retired:

- **`Non-eBL Ruler (VAM)` → `General (white background)`**
  — Same ruler (`General_External_photo_ruler.svg`, single-mode, 3.248 cm).
  Institution field cleared (was VAM-specific).
- **`Black background (Jena)` → `General (black background)`**
  — Same adaptive-set scale bars (`Black_*_scale.tif`).

Files affected:
- [stitcher/assets/projects/general_white_background.json](stitcher/assets/projects/general_white_background.json) (new)
- [stitcher/assets/projects/general_black_background.json](stitcher/assets/projects/general_black_background.json) (new)
- [stitcher/process_tablets.py](stitcher/process_tablets.py) — default `--museum` updated; calls `project_manager.set_active_project()` after loading so `_select_ruler_from_project` is used for all new projects (no hardcoded name branches needed).
- [stitcher/lib/stitch_config.py](stitcher/lib/stitch_config.py) — keys renamed in the museum settings map.
- [stitcher/lib/remove_background.py](stitcher/lib/remove_background.py),
  [stitcher/lib/resize_ruler.py](stitcher/lib/resize_ruler.py),
  [stitcher/lib/workflow_ruler_generation.py](stitcher/lib/workflow_ruler_generation.py)
  — legacy hardcoded name strings updated to the new names (used only as fallback when `set_active_project` is not called).

Old bundled `.exe` will refuse the new project names. Rebuild required before next release.

## Stitcher metadata (requires rebuild of `resources/stitcher/eBL.Photo.Stitcher.exe`)

- Per-project metadata overrides now flow end-to-end:
  - UI fields: `photographer`, `institution`, `credit_line`, `usage_terms`.
  - Electron packs them into `extraArgs` ([src/main/main.js](src/main/main.js)).
  - Forwarded as `--institution`, `--credit-line`, `--usage-terms` by
    [src/main/stitcher-bridge.js](src/main/stitcher-bridge.js).
  - [stitcher/process_tablets.py](stitcher/process_tablets.py) overrides the
    corresponding `stitch_config` module constants before any downstream
    code reads them, so `stitch_output.py` / `pure_metadata.py` don't need
    per-call changes.
- Python fixes / additions already applied in
  [stitcher/lib/pure_metadata.py](stitcher/lib/pure_metadata.py):
  - **Fix:** `Xmp.dc.subject` now carries the tablet ID as a keyword
    instead of the copyright text.
  - **Metric:** `XResolution` / `YResolution` are written in px/cm with
    `ResolutionUnit=3` when `pixels_per_cm` is known; falls back to DPI
    otherwise.
  - **EXIF additions:** `DateTime`, `Photo.DateTimeOriginal`,
    `Photo.DateTimeDigitized`.
  - **XMP additions (dc):** `identifier`, `publisher`, `date`, `type`.
  - **XMP additions (xmp core):** `CreatorTool`, `CreateDate`, `ModifyDate`.
  - **XMP additions (photoshop):** `Headline`.
  - **IPTC-IIM block:** full legacy-reader block — `ObjectName`, `Headline`,
    `Caption`, `Byline`, `Credit`, `Source`, `Copyright`, `Keywords`,
    `DateCreated`, `TimeCreated`. Wrapped in try/except because pyexiv2's
    IPTC support varies by version; EXIF+XMP is still written if IPTC-IIM
    fails.
- Build setup ready:
  - Both `.spec` files point at the vendored `process_tablets.py` entry.
  - `npm run build-stitcher` rebuilds + copies the binary into
    `resources/stitcher/` (requires Python + `pyinstaller` +
    `stitcher/requirements.txt` installed).
- **Not yet run** — bundle more pending changes first, then rebuild +
  release in one pass. Existing `_Final_JPG/` outputs keep their old
  metadata until the tablet is reprocessed with the new binary.
- **Data-cleanup candidate:** `dc.description` and `ImageDescription` both
  currently carry the tablet ID (same as `dc.title`). By Dublin Core they
  should hold a longer account (e.g. `"Cuneiform tablet Si.22 — stitched
  composite, six views."`). Decide on a template and swap in.

## CI

- Future: add a GitHub Action that runs `npm run build-stitcher` on push to
  `main` so the bundled `.exe` is always in sync with `stitcher/lib/`.
  Skipped for now — not releasing yet.
