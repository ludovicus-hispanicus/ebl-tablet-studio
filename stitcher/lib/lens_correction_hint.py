"""
Heuristic predictor for when lensfunpy-style lens correction would have helped.

We can't know for sure without running lensfunpy (which we intentionally don't
bundle — see stitcher/README.md and raw_processor.py). But we can flag the
conditions where correction MATTERS: RAW-sourced photos where the subject
(tablet) sits close to the frame edge, i.e. where lens distortion and corner
vignetting are most visible.

The module exposes a small stateful API:
  - record_raw_conversion(tiff_path): call from convert_raw_image_to_tiff.
    Remembers that this intermediate TIFF came from a RAW source.
  - check_extraction(input_path, bbox, frame_w, frame_h, file_id): call from
    the rembg object extractor once the bbox is finalized. If the input was
    a RAW-derived TIFF AND the bbox hugs a frame edge, emit a one-line hint
    and increment the counter.
  - report_summary(): returns lines to append to print_final_statistics.
  - reset(): clear state between runs (called at workflow start).

Threshold: 10% of the shorter frame side. Tablets with min-edge-gap below
that are considered edge-hugging. Chosen because most non-macro lenses show
noticeable distortion/vignetting within the outer 10% of the frame.
"""

EDGE_MARGIN_THRESHOLD = 0.10

_raw_derived_paths = set()
_flagged_files = set()
_raw_files_seen = set()


def reset():
    _raw_derived_paths.clear()
    _flagged_files.clear()
    _raw_files_seen.clear()


def record_raw_conversion(tiff_path):
    if tiff_path:
        _raw_derived_paths.add(tiff_path)


def check_extraction(input_path, bbox, frame_w, frame_h, file_id=None):
    if input_path not in _raw_derived_paths:
        return
    _raw_files_seen.add(file_id or input_path)
    if not bbox or frame_w <= 0 or frame_h <= 0:
        return
    x_min, y_min, x_max, y_max = bbox
    gap = min(x_min, y_min, frame_w - x_max, frame_h - y_max)
    margin_fraction = gap / min(frame_w, frame_h)
    if margin_fraction >= EDGE_MARGIN_THRESHOLD:
        return
    key = file_id or input_path
    if key in _flagged_files:
        return
    _flagged_files.add(key)
    label = file_id or input_path
    print(
        f"    Lens-correction hint: {label} — tablet within "
        f"{margin_fraction * 100:.1f}% of frame edge on a RAW source. "
        f"lensfunpy could reduce edge distortion / vignetting here."
    )


def report_summary():
    total_raw = len(_raw_files_seen)
    total_flagged = len(_flagged_files)
    if total_raw == 0:
        return []
    return [f"Lens correction would have helped: {total_flagged} / {total_raw} RAW tablet(s)"]
