# eBL Tablet Studio — Merge Plan

**Status:** Draft · **Owner:** Luis Saenz · **Date:** 2026-04-17 · **Last updated:** 2026-04-17 (v3 — fresh-repo approach)

Building a single app, **eBL Tablet Studio**, in a **new GitHub repo** (`ebl-tablet-studio`). Both existing repos (`tablet-image-renamer` and `ebl-photo-stitcher`) are archived on cutover. The renamer's Electron shell is imported as the UI host; the stitcher is imported as a headless Python backend bundled inside Electron's `resources/`. The renamer's segmentation Python is absorbed into the stitcher's pinned 3.12 bundle so there is one Python runtime and one ML engine (SAM via ONNX).

**Segmentation architecture (key decision):** replace U2NET/rembg entirely with SAM. One ML model (SAM variant, exported to ONNX) powers both automatic and manual object extraction. Drops the rembg dependency, the U2NET weight download, and — crucially — torch from the bundled runtime. Inference runs on **onnxruntime only**; torch is a dev-time tool for the one-time ONNX export, never shipped.

---

## 1. Goals & non-goals

**Goals**
1. One installer per OS (Windows `.exe`, macOS `.dmg`, Linux `.AppImage`) that contains both tools.
2. One product identity: "eBL Tablet Studio" across window title, menus, installer, icons, artifact names.
3. Zero-config install for non-technical users — no system Python, no manual dep installs.
4. One release cycle, one changelog.
5. Preserve current renamer users: existing project JSON at `%APPDATA%/eBLImageProcessor/projects/` keeps working unchanged.
6. Unified segmentation: one model (SAM via ONNX), one code path for auto and manual.

**Non-goals**
- Rewriting stitching logic in Node.
- Changing the stitcher's image-processing pipeline semantics (other than swapping the extraction step).
- Changing ruler-recognition or scale-detection logic. Both detectors (`ruler_detector.py`, `ruler_detector_iraq_museum.py`) and the measurement-fallback cascade are preserved byte-for-byte. See §5.B.1 for the isolation argument.
- Supporting system-Python installs after the merge lands. Bundled Python becomes the only path.
- Changing CLI contracts for power users mid-merge — `process_tablets.py` stays callable with the same args.
- Preserving the U2NET / rembg pipeline. It is being retired in favor of SAM.
- Shipping torch in the production bundle. Torch is a dev-time dependency only (for model export).

---

## 2. Repo strategy

- **New repo:** `ebl-tablet-studio`, created on GitHub at the start of Phase A. Public. License matches the sources.
- **Initial commit:** imports the `tablet-image-renamer` Electron shell as the UI skeleton (rebranded to Studio identity in the same commit). Stitcher code does not yet move in — Phase A only bundles the pre-built stitcher binary as an Electron resource.
- **Branch model:** single `main` branch for a solo project. Short feature branches only for risky work (the B.0 SAM/ONNX spike is one such branch). No long-lived integration branches.
- **Versioning:** starts at `v0.1.0` in the new repo. First public installer when Phase A is complete. Pre-releases tagged `v0.N.0-beta.M` with electron-builder `prerelease: true`. `v1.0.0` reserved for Phase C cutover.
- **Old repos during development:** `tablet-image-renamer` and `ebl-photo-stitcher` stay public, read-write, releasable. Any renamer-only or stitcher-only bugfix users need can still ship from them until cutover.
- **Old repos after cutover (Phase C):** archived (read-only). Each gets a farewell `README.md` banner pointing to `ebl-tablet-studio`, plus a final `archive-final` tag on HEAD.
- **Issue/PR triage before archiving:** open issues on both old repos are reviewed; relevant ones migrated as fresh issues on the new repo, stale ones closed with a link to the new repo.
- **Git history:** not imported. `git blame` won't walk back across the merge boundary; old repos remain available for lookup. Justified because this is a solo project and archived repos are one click away.

---

## 3. Delivery shape (staged A → B → C)

**Phase A — Packaging merge + rename** (target: 1–1.5 weeks)
Ship a single installer that wraps the existing stitcher binary unchanged. Dual Python runtime still present. Users still need system Python for segmentation. Internal beta only. Segmentation architecture is untouched in this phase — still MobileSAM + torch on the renamer side, still U2NET/rembg on the stitcher side.

**Phase B — Python + segmentation consolidation** (target: 2–3 weeks after A)
Collapse both Python sides into one bundled 3.12 interpreter. Replace U2NET with SAM for object extraction. Go ONNX-only at runtime. Drop torch, rembg, u2net from the shipped bundle. Zero-config install. This is the user-facing win.

**Phase C — Release** (target: 1 week after B)
Final polish, full beta, cutover, rename.

Phase A is a shippable fallback. If Phase B's ONNX export or bundle-size targets slip, we can still release Phase A as a single-installer product and push the segmentation consolidation to a follow-up release.

---

## 4. Phase A — Packaging merge

### A.1 Initialize the new repo and import the Electron shell
- **Create the GitHub repo** `<org>/ebl-tablet-studio` (public). Match the license of the source repos (verify, likely MIT).
- **Fresh local clone.** `git init` locally, create the repo scaffolding: `.gitignore` (copy from renamer), `README.md` (stub), `LICENSE`.
- **Import the Electron shell from `tablet-image-renamer`:**
  - `src/main/`, `src/renderer/`, `src/preload.js`, and related files.
  - `package.json` — with **new identity** from the first commit:
    - `name`: `ebl-tablet-studio`
    - `productName`: `eBL Tablet Studio`
    - `version`: `0.1.0`
    - `build.appId`: `com.ebl.tablet-studio`
    - `build.artifactName`: `eBL_Tablet_Studio-${version}-${os}-${arch}.${ext}`
  - Do **not** copy `node_modules/`, `dist/`, `build/` — regenerate with `npm install`.
- **Import icons from `ebl-photo-stitcher`:**
  - `eBL_Logo.ico`, `eBL_Logo.icns`, any PNG set from the stitcher's `assets/`.
  - Wire `build.win.icon`, `build.mac.icon`, `build.linux.icon` in `package.json`.
- **Rebrand in-place:**
  - `src/main/main.js` — BrowserWindow title → `'eBL Tablet Studio'`.
  - Grep `src/renderer/` for "Tablet Image Renamer" strings; replace with "eBL Tablet Studio".
- **First commit message:** `Initial import: Electron shell from tablet-image-renamer, rebranded as eBL Tablet Studio`.
- **Acceptance:** `npm install && npm start` opens a window titled "eBL Tablet Studio" with the renamer's existing UI and no functional regression.

### A.2 Bundle the stitcher binary
- Build stitcher PyInstaller artifacts **in the stitcher repo** as usual (don't change the stitcher's build process yet).
- Copy artifacts into renamer's `resources/stitcher/`:
  - Windows: `eBL Photo Stitcher.exe` (onefile, ~240 MB)
  - macOS: `eBL Photo Stitcher.app/` (onedir bundle)
  - Linux: skip for now — stitcher has no Linux build today. Linux AppImage ships without stitcher in Phase A; renamer features work, stitcher-dependent UI is disabled with "not supported on Linux" notice.
- `package.json` `build.extraResources`:
  ```jsonc
  { "from": "resources/stitcher", "to": "stitcher", "filter": ["**/*"] }
  ```
- `resources/stitcher/` is gitignored; CI builds the stitcher artifact and drops it here before `electron-builder`.

### A.3 Update `stitcher-bridge.js`
- Stop asking the user for a stitcher exe path.
- Resolve bundled path:
  - Dev: `path.join(__dirname, '../../resources/stitcher/eBL Photo Stitcher.exe')` (or `.app/Contents/MacOS/...` on macOS)
  - Packaged: `path.join(process.resourcesPath, 'stitcher', ...)`
- Delete the "Browse for stitcher exe" UI flow.
- `stitcher-config.json`: keep the file for other settings but drop the `exe path` key. Migrate on first run: if old key exists, log and ignore it.

### A.4 Migrate stitcher settings into renamer UI
`gui_config.json` keys that now need a home in the renamer settings panel:
- `last_ruler_position` (top/bottom/left/right)
- `last_photographer`
- `last_add_logo` + `last_logo_path`
- `last_folder` already handled by renamer's project manager
Persist in the existing `stitcher-config.json` at `%APPDATA%/tablet-image-renamer/` (rename to `%APPDATA%/eBL Tablet Studio/` — see A.7).

### A.5 Progress streaming sanity check
`process_tablets.py --json-progress` already emits `{type: progress|start|finished|error}` on stdout. Confirm the renamer's `stitcher-bridge.js` consumes it correctly with the bundled exe path. One integration test: run a single tablet through the packaged app end-to-end.

### A.6 CI changes (renamer repo)
`.github/workflows/release.yml` gains a **stitcher artifact fetch** step before `electron-builder`:
- Option 1 (simpler, loose coupling): download latest `eBL Photo Stitcher` release artifact from the stitcher repo via `gh release download`. Pin to a specific stitcher version in a `STITCHER_VERSION` env var.
- Option 2 (tighter, more CI): trigger stitcher repo's `build-release.yml` via `workflow_dispatch`, wait for artifacts, download them. More moving parts; defer unless Option 1 becomes painful.

Go with Option 1 in Phase A.

### A.7 AppData path migration
- Current: `%APPDATA%/tablet-image-renamer/`
- New: `%APPDATA%/eBL Tablet Studio/`
- On first launch of v0.6.0-beta: if old dir exists and new dir doesn't, copy contents (user.json, saved-histories.json, stitcher-config.json, seg-weights/). Leave old dir in place — don't delete; users may roll back.
- `%APPDATA%/eBLImageProcessor/projects/` **stays untouched** — this is the shared project store; both old stitcher and new Studio continue to read/write it.

### A.8 Documentation
- `README.md` in renamer repo: rewrite intro to describe eBL Tablet Studio.
- Add `docs/migration-from-standalone.md` for users who had the old renamer + stitcher separately.
- Archive the stitcher repo's README with a link to the new repo.

### A.9 Phase A acceptance criteria
- Single installer builds on Windows and macOS CI.
- Fresh install on a test VM (no Python, no old renamer, no old stitcher): installer runs, app launches, can open a project, rename images, and kick off a stitch of at least one tablet end-to-end.
- Renamer's segmentation still works on a dev machine that has system Python installed (Phase A doesn't fix segmentation install — that's Phase B).
- Smoke test on macOS arm64 and Windows x64 minimum.

---

## 5. Phase B — Python + segmentation consolidation

### B.0 SAM model selection + ONNX export spike (~2 days)
Decides which model we ship and validates that the ONNX export pipeline is viable. Blocks the rest of Phase B.

**Model candidates** (smallest to largest, all Apache 2.0):

| Model | Weight | Notes |
|---|---|---|
| MobileSAM (current) | ~40 MB | Known-good, already wired in renamer. ONNX exports mature and widely used. Safe fallback. |
| SAM 2 tiny | ~38 MB | Newer architecture, better than MobileSAM at same size. |
| SAM 2 small | ~46 MB | Noticeably better edges. Recommended if tiny isn't enough. |
| **SAM 2 base+ (recommended)** | **~80 MB** | **Sweet spot — excellent quality, still small. Apache 2.0.** |
| SAM 2 large | ~224 MB | Max quality; only if A/B test shows visible gain. |

**Spike tasks:**
1. Pick 5 representative tablets covering clean shots, hand-in-frame, cluttered background, off-center tablets, textured backgrounds.
2. Run extraction with each model candidate (torch, for ground truth).
3. Export each candidate to ONNX (encoder + decoder split where applicable — SAM 2's decoder is the trickier half).
4. Verify ONNX output matches torch output numerically (cosine similarity > 0.99 on mask logits).
5. A/B the final **stitched** outputs, not just the masks — the feathering stage may smooth away differences that looked big at the mask level.
6. Pick the smallest model that's indistinguishable from the largest in the stitched A/B.

**Exit gate:** chosen model + verified ONNX export script in `tools/export_sam_onnx.py` + committed ONNX artifact or CI step that produces it.

**Fallback if SAM 2 export fails:** fall back to MobileSAM ONNX (already mature). Quality still better than U2NET for our use case.

### B.1 Replace U2NET with SAM in the stitcher extraction path
This is the architectural heart of Phase B.

**Isolation argument (why this is safe):**
The stitcher's pipeline runs ruler detection and scale calculation **on the original raw/converted image, BEFORE object extraction** ([gui_workflow_runner.py:364–396](../../../Documents/GitHub/ebl-photo-stitcher/lib/gui_workflow_runner.py#L364-L396)). Object extraction is a downstream step. Swapping U2NET → SAM therefore cannot affect:
- `lib/ruler_detector.py` (general mark/tick detection)
- `lib/ruler_detector_iraq_museum.py` (Hough-line Iraq detector)
- `lib/workflow_scale_detection.py` (measurement → detection fallback cascade)
- `lib/workflow_ruler_generation.py` / `lib/resize_ruler.py` (digital ruler overlay)
- `lib/measurements_utils.py` (Excel/JSON loaders)
- The legacy contour-based `lib/object_extractor.py` used for ruler *extraction* (not tablet extraction)

All of these are preserved byte-for-byte. Regression test required: run `process_tablets.py` on a fixture tablet with no `--measurements` flag, confirm ruler auto-detection produces the same px/cm before and after the SAM swap.

**Files to delete:**
- `lib/object_extractor_rembg.py` (~430 lines) — entire U2NET pipeline, including the download/validate/session-management logic.
- U2NET model file at `~/.u2net/u2net.onnx` stops being used. Don't actively delete the user's copy — let it age out.

**Files to add or rewrite:**
- `lib/object_extractor_sam.py` — new module. Loads the SAM ONNX model (via onnxruntime), exposes `extract_and_save_center_object(...)` with the same signature as the old rembg version so `gui_workflow_runner.py` / `workflow_runner.py` don't need to change.
- Internally uses a **center-point prompt** as the default auto strategy (one click at image center, one SAM inference, sub-second on CPU).
- Validates the resulting mask: area > N% of image, centroid within M% of center, aspect ratio within plausible tablet range. If invalid, raise a structured error the Electron layer catches and routes to the manual-SAM UI.
- Reuses the `SelectCenterObject`-style heuristic (closest to center among largest blobs) as a second pass when SAM returns multiple disjoint mask regions, which is rare but possible.

**Model loading strategy:**
- Single onnxruntime session, lazy-initialized, reused across calls (mirrors the old `_get_rembg_session()` pattern).
- CUDA provider preferred if available, CPU fallback. No torch at runtime.

### B.1.5 Ruler-optional mode + detection-failure UX
The current stitcher raises `ValueError` when ruler auto-detection fails and no measurements are provided ([workflow_scale_detection.py:167](../../../Documents/GitHub/ebl-photo-stitcher/lib/workflow_scale_detection.py#L167)). The only fallback today is a Tkinter manual-entry dialog, which we're deleting along with the rest of the GUI. The merged Studio needs a better story.

**Three outcomes to support:**

1. **Scale known** (measurements file found, or auto-detection succeeded, or user did manual entry) → produce stitched output **with digital ruler overlay** as today.
2. **Scale unknown + user wants to retry** → open Electron manual-ruler dialog (see below). User clicks two points on the ruler image, enters distance in cm, app returns px/cm to Python.
3. **Scale unknown + user skips / no ruler in photo** → produce stitched output **without digital ruler overlay**. Log the skip; don't fail the job.

**New settings:**
- Project-level toggle: **"Include digital ruler in output"** (default: on). When off, skip scale detection entirely and skip the `generate_digital_ruler()` step.
- Per-tablet override when auto-detection fails: a modal asks user to either (a) click on ruler to enter scale manually, or (b) proceed without ruler for this tablet.

**Changes to `workflow_scale_detection.py` / orchestration:**
- `determine_pixels_per_cm_with_fallback()` must be allowed to return `None` cleanly (today it raises). Downstream `generate_digital_ruler()` call becomes conditional on `px_cm_val is not None`.
- `process_tablets.py --json-progress` emits a new event type `{"type": "scale_unknown", "tablet": "...", "reason": "..."}` when detection fails; Electron layer catches this and surfaces the modal.
- New CLI flag `--no-ruler` (default off) lets scholars run the stitcher headlessly with ruler overlay skipped.
- New CLI flag `--on-ruler-failure {error,skip,prompt}` (default `error` for backward compatibility in scripts; Electron passes `prompt`). `skip` matches the new user-visible behavior: quietly proceed without ruler.

**New Electron overlay (renderer side) — blocking, full-app takeover:**
- Triggered by the `scale_unknown` JSON event. The overlay grabs input regardless of what view the user is on (picker, renamer, settings, etc.) — user can't use the rest of the app while it's up.
- **Closable via X button (top-right) or Esc key**, and closing has a well-defined meaning: **skip ruler for this tablet** (same outcome as the explicit "Skip ruler for this tablet" button). User is never trapped; dismissing the overlay is itself a valid resolution.
- Implementation: `position: fixed; inset: 0; z-index: 9999;` with a semi-opaque backdrop and a centered workspace. Captures all pointer and keyboard events on the body while visible. Other windows (devtools etc.) remain accessible; this is an intra-renderer overlay, not a separate BrowserWindow.
- Shows the ruler image at fit-to-screen scale with zoom/pan (reuse the existing zoom/pan plumbing already built for the picker view).

**Line-drawing primitive (new, not reused from SAM):**
The SAM UI is click-a-point; this is draw-a-line. New canvas component `src/renderer/js/line-tool.js`:
- **Default mode: free-hand two-point line.** Click-and-drag: mousedown sets start, mousemove previews, mouseup commits. Or click-click: first click sets start, second click sets end. Both interaction styles work.
- **Shift-held mode: constrained straight line.** While Shift is held during drag or second-click, the line snaps to the nearest of: horizontal, vertical, 45°. Visual feedback (the preview line jumps to the snapped angle so the user can see it will lock).
- **After commit:** both endpoints are draggable handles; user can fine-tune either end. Line stays until user clicks "Use this scale" or "Redraw" to start over.
- Pixel distance between endpoints is computed continuously and shown next to the line (e.g. "842 px").

**Overlay controls:**
- **Distance input (cm)** — real-world length the user measured with the line. Accepts decimals (e.g. `2.5`).
- **Use this scale** → computes `px/cm = pixel_distance / cm_distance`, sends via new IPC channel `scale-manual-entry`, overlay dismisses.
- **Redraw line** → clears the current line, stays in the overlay.
- **Skip ruler for this tablet** → sends `null`, overlay dismisses, stitching continues without ruler.
- **Skip ruler for all remaining tablets in this batch** → sends `null` + a batch-wide flag so the backend doesn't prompt again on subsequent tablets in the same run.
- **Keyboard shortcuts:** `Esc` = skip this tablet, `Enter` = confirm (if line drawn + cm entered), `R` = redraw, `Shift` = straight-line constraint (held during drag).

Lives in `src/renderer/js/ruler-modal.js` (overlay shell) + `src/renderer/js/line-tool.js` (drawing primitive).

**New IPC channels in `segmentation-bridge.js` / stitcher-bridge:**
- Outbound (Python → Electron): `scale-unknown` event on the stitcher bridge's progress stream.
- Inbound (Electron → Python): `scale-manual-entry` with `{tablet, px_per_cm|null}` payload. Stitcher backend waits synchronously (or polls) for this response before continuing that tablet.

**Stitching without ruler — image-processing implications:**
- `generate_digital_ruler()` simply not called. No blank space reserved for the ruler.
- `workflow_ruler_generation.select_ruler_template()` is skipped.
- `stitch_enhancement_utils` logo addition still works (independent of ruler).
- Final cropping / canvas-size calculation needs one branch: if `px_cm_val is None`, skip the "reserve X cm for ruler" padding. Verify `stitch_layout_calculation.py` doesn't hard-assume a non-None scale.

### B.2 Bundled Python dep set
The merged `requirements.txt` after Phase B:

| Dep | Stitcher today | Renamer today | **Merged (Phase B)** |
|---|---|---|---|
| torch | excluded from spec | required for MobileSAM | **dropped from runtime** (dev-only, for ONNX export) |
| torchvision | excluded from spec | required | **dropped from runtime** |
| mobile-sam (pip pkg) | not used | required (from GitHub) | **dropped** — we use ONNX directly |
| rembg | required | not used | **dropped** — SAM replaces it |
| u2net model | required | not used | **dropped** |
| **onnxruntime** | required | not used | **required, sole ML runtime** |
| **SAM ONNX model** | not used | not used | **new, shipped in bundle or downloaded on first run (~40–80 MB)** |
| opencv-python | required | not used directly | required |
| pyexiv2 | required (needs system exiv2 on mac) | not used | required — keep macOS binary bundling pattern from `eBL_Photo_Stitcher_MacOS.spec` |
| rawpy | required | not used | required |
| cairosvg + cairocffi | required | not used | required |
| Pillow, numpy, scikit-image, scipy | required | partial | required |

Pin every dep explicitly (`==`, not `>=`). The stitcher's current `>=` ranges are a long-term landmine once we bundle.

**Bundle size projection:**
- Stitcher today: ~240 MB (Windows onefile)
- After Phase B: ~240 MB – (rembg+u2net artifacts ≈ 60 MB) + (onnxruntime ≈ 50 MB, already present) + (SAM ONNX ≈ 80 MB) ≈ **~310 MB**. Net growth ~70 MB for full segmentation, no torch.
- Contrast: naively adding torch would have pushed us to ~700–900 MB. This is why the ONNX-only architecture is load-bearing.

### B.3 Move renamer's Python into the stitcher tree
- `python/segmentation_server.py` → `lib/segmentation_server.py`, rewritten to use **onnxruntime** instead of torch + MobileSAM pip package. Same stdin/stdout JSON protocol — the Electron layer sees no protocol change.
- `python/download_weights.py` → `lib/sam_weights.py`, downloads the chosen SAM ONNX model to the shared cache. Reuses the download pattern from the old `object_extractor_rembg.py:38-101` (retry, progress, validation).
- `python/requirements.txt` is deleted; all Python deps live in the merged stitcher `requirements.txt`.

### B.4 Unify Python entry points
Two entry points in the bundle:
1. `process_tablets.py` — unchanged CLI for stitch workflow. Under the hood, now calls `object_extractor_sam.py` instead of the old rembg module.
2. `segmentation_server.py` — the interactive SAM server for the manual UI.

Both get PyInstaller specs (or one spec with two `EXE` blocks producing two binaries in a shared `onedir` tree — preferred on macOS since it shares libs and the SAM ONNX model file).

**Alternative (deferred, post-launch):** single long-running Python subprocess that dispatches both stitch jobs and segmentation commands via one protocol. Shares the loaded SAM session across auto and manual → zero cold start for manual refinement after auto extraction. Bigger protocol refactor; not critical path.

### B.5 Update PyInstaller spec
- `eBL_Photo_Stitcher.spec` and `eBL_Photo_Stitcher_MacOS.spec`:
  - **Keep** torch, torchvision, torchaudio in `excludes` (they're only used by the dev-time export script, never at runtime).
  - **Remove** rembg-related `hiddenimports` (lines referencing `rembg`, `u2net`).
  - **Add** `onnxruntime` to `hiddenimports` if not already sufficient; verify all providers are picked up.
  - **Add** the SAM ONNX model to `datas` — or configure first-run download, same pattern as U2NET used to have.
  - Expected Windows bundle: ~310 MB. macOS onedir bundle similar.
- No MPS / CUDA debugging needed — onnxruntime's provider model is well-behaved in PyInstaller.

### B.6 Rewrite `segmentation-bridge.js`
- Delete the Python-path search logic entirely (`segmentation-bridge.js:42-64`, the `resolvePython()` function).
- Resolve path to bundled segmentation server binary:
  - Dev: `path.join(__dirname, '../../resources/stitcher/segmentation_server[.exe]')`
  - Packaged: `path.join(process.resourcesPath, 'stitcher', 'segmentation_server[.exe]')`
- Update `weights-dir` arg to point at the shared model cache (B.7).
- stdin/stdout JSON protocol is unchanged — no changes needed on the renderer side.

### B.7 Shared model cache
- Root: `%APPDATA%/eBL Tablet Studio/models/` (Windows), `~/Library/Application Support/eBL Tablet Studio/models/` (macOS).
- Subdir: `sam/` — contains the chosen ONNX model (one file typically, or encoder + decoder split).
- On first run, if the model file is absent, download it in the background with progress reported to the UI. Same UX pattern as the old U2NET download, minus the "176 MB" warning (our model is smaller).
- Override via env var `EBL_MODEL_CACHE` for CI and for scholars who want to point at a shared network drive.

### B.8 Drop the stitcher GUI and dead extraction code
Delete (staged to avoid breaking Phase A fallback — do these commits in order, gated by integration tests):

**GUI files:**
- `gui_app.py`
- `lib/gui_advanced.py`, `lib/gui_components.py`, `lib/gui_config_handlers.py`, `lib/gui_config_manager.py`, `lib/gui_config_tab.py`, `lib/gui_events.py`, `lib/gui_layout.py`, `lib/gui_museum_options.py`, `lib/gui_utils.py`

**Dead extraction code:**
- `lib/object_extractor_rembg.py`
- Any imports of `rembg` elsewhere in `lib/`

**Preserve and rename:** `lib/gui_workflow_runner.py` (35 KB) → `lib/workflow_runner.py`. Strip any tkinter imports (likely uses `root.update()`, `messagebox` calls — replace with structured logging and JSON progress events consistent with `process_tablets.py --json-progress`). This file orchestrates the entire stitch pipeline and can't simply be deleted.

### B.9 Phase B acceptance criteria
- Fresh VM (no Python, nothing): installer runs, app launches, **both auto and manual segmentation work without installing Python**.
- Bundle size ≤ 400 MB on Windows (target: ~310 MB). If it exceeds 500 MB, investigate.
- Auto-extraction quality on the 5-tablet A/B set is equal to or better than the current U2NET pipeline (visual comparison of stitched outputs, not just raw masks).
- **Ruler-logic regression test passes**: run `process_tablets.py` on a fixture tablet with no `--measurements` flag and confirm auto-detection produces the same px/cm value pre- and post-SAM-swap (exact match, to within floating-point tolerance).
- **No-ruler mode works end-to-end**: a tablet photographed without a physical ruler, with `--no-ruler` or with the project toggle off, produces a stitched output with no overlay, no errors, no reserved ruler space.
- **Ruler-failure UX works end-to-end**: on a tablet where auto-detection fails, the Electron modal appears; both "enter manually" and "skip this tablet" paths complete without crashing the batch.
- All of Phase A's acceptance criteria still pass.
- Cold-start latency for first segmentation ≤ 5 s on a mid-range machine; subsequent calls ≤ 500 ms (long-running server keeps model loaded).
- No torch, torchvision, rembg, or mobile-sam pip packages appear in the shipped bundle (verify with `PyInstaller --log-level=DEBUG` output or by grepping the frozen binary).

---

## 6. Phase C — Release

- Tag `v1.0.0` on the new repo.
- Final CI run produces Windows, macOS arm64, macOS Intel, Linux artifacts.
- GitHub release notes: migration guide for existing renamer/stitcher users, note the U2NET → SAM switch and the resulting quality improvement.
- **Archive both old repos** on GitHub:
  - `tablet-image-renamer`: mark read-only, add farewell README banner pointing to `ebl-tablet-studio`, tag `archive-final` at HEAD.
  - `ebl-photo-stitcher`: same treatment.
- **Issue/PR triage:** review open items on both old repos. Migrate anything still relevant as fresh issues on the new repo. Close the rest with a link to the new repo.
- Post-release: monitor GitHub Issues on the new repo for install failures for 1 week before considering the cutover done.

---

## 7. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SAM 2 ONNX export doesn't match torch output | Medium | High | Phase B.0 spike validates this before any integration work. Fallback: MobileSAM ONNX (mature exports exist). |
| Auto-extract quality regression vs U2NET on some shot types | Medium | Medium | A/B on 5 representative tablets in B.0; require visual parity on stitched outputs before committing to SAM. If regression found on specific shot classes, keep U2NET path as optional behind a setting until SAM closes the gap. |
| Bundle size balloons despite going ONNX-only | Low | Medium | Net growth budgeted at ~70 MB. If it exceeds 500 MB on Windows, audit PyInstaller output and cut unused libs. |
| Existing users lose projects during AppData rename | Low | High | Don't delete old dir; copy-migrate on first run with a visible one-time notice. |
| Stitcher regression from removing `gui_workflow_runner.py` tkinter deps | Medium | Medium | Write one integration test that runs `process_tablets.py` on a known-good tablet fixture before Phase B.8 and after; require both to match. |
| `stitch_layout_calculation.py` hard-assumes a non-None scale, breaks in no-ruler mode | Medium | Medium | Audit `stitch_layout_calculation.py`, `stitch_enhancement_utils.py`, and `stitch_images.py` for any `px_cm_val * X` math that would blow up on None. Gate ruler-reservation code behind `if px_cm_val is not None`. Add a no-ruler fixture to the integration tests. |
| onnxruntime on macOS arm64 has provider quirks | Low | Medium | Test on a real M-series Mac before Phase B exit. onnxruntime's CoreML provider is usable but not always best; default to CPU provider and measure. |
| macOS notarization breaks with new bundle layout | Medium | Medium | Stitcher already ships unsigned (`identity: null`); acceptable for now but plan to obtain an Apple Developer ID before v1.0 if we want Gatekeeper-clean installs. |
| Auto-update from old renamer → Studio surprises users | Medium | Medium | Keep `appId` change (`com.tablet-image-renamer` → `com.ebl.tablet-studio`) — electron-builder treats this as a new app, users install fresh. Announce in release notes. |

---

## 8. Rollback

- Phase A is reversible: the branch stays a branch until cutover. If issues surface, we cut a patch from `main` and keep shipping separate apps.
- Phase B is reversible: revert B.* commits, restore Phase A shape. The SAM-for-extraction switch is a self-contained change — the old U2NET module can be restored from git history.
- Phase C (the repo rename and archive) is the point of no return — only do it after 2+ weeks of stable beta usage.

---

## 9. Open questions

1. **Tester pool** — who runs the beta builds during Phase A/B? Need at least one Windows user and one macOS user outside the dev machine. Without this, we're flying blind on install quirks.
2. **Linux** — Phase A has no stitcher on Linux. Is there a real user need, or can we drop Linux from the supported list entirely? Dropping it simplifies CI.
3. **Stitcher repo history** — archive (read-only) or full delete after cutover? Recommend archive — the git history has value and the disk cost is zero.
4. **Apple Developer ID** — worth getting before v1.0 to avoid Gatekeeper "unidentified developer" warnings? (~$99/yr.)
5. **SAM tier** — once B.0 A/B test is done, commit to MobileSAM, SAM 2 tiny, SAM 2 small, or SAM 2 base+? Default recommendation: smallest model that's visually indistinguishable from SAM 2 base+ on the stitched output.
6. **Auto-extract failure UX** — when SAM auto-extract fails validation (hand in frame, weird composition), does the UI silently fall through to manual SAM, or explicitly prompt the user? Recommend explicit prompt with the failure reason — more predictable than silent behavior changes.

---

## 10. Concrete first steps

When you give the go-ahead:

1. **Create the new GitHub repo** `<org>/ebl-tablet-studio` (public, license matches sources).
2. **Initial commit — Electron shell import** (A.1). Copy renamer files, update `package.json` identity, set window title, import icons from the stitcher. Verify `npm install && npm start` opens a window titled "eBL Tablet Studio" with the renamer's existing UI intact.
3. **Bundle the stitcher binary** (A.2). Add `resources/stitcher/` to `.gitignore` and `extraResources`. Download the pinned stitcher release artifact locally (see stitcher-pin question in §9) and drop it in.
4. **Wire `stitcher-bridge.js`** to resolve the bundled path instead of prompting the user (A.3). Delete the "browse for exe" UI.
5. **Smoke test end-to-end.** On a fresh OS user account (ideally a VM), install, open a project, run a stitch on one tablet.
6. **Add CI** (A.6): download the pinned stitcher release artifact before `electron-builder`, on both Windows and macOS runners.

That's roughly 2–3 days to a working Phase A dev build on one OS. Second OS follows the same pattern. Once both OSes build green in CI, Phase A is shippable, and Phase B starts with the B.0 SAM/ONNX spike — a self-contained 2-day task that de-risks the rest of Phase B before any production code changes.
