#!/usr/bin/env python
"""
Headless CLI entry point for the ebl-photo-stitcher pipeline.

Used by the Electron renamer to reprocess tablets after review.
Accepts a root folder and an optional list of tablet names to process.
If no tablets are specified, processes all.

Usage:
    python process_tablets.py --root "C:/path/project"
    python process_tablets.py --root "C:/path/project" --tablets "Si.10" "Si.11"
    python process_tablets.py --root "C:/path/project" --museum "Non-eBL Ruler (VAM)" --measurements "path/to/measurements.xlsx"

Exit codes:
    0 - success
    1 - error
    2 - invalid arguments
"""

import os
import sys
import argparse
import json

script_directory = os.path.dirname(os.path.abspath(__file__))
lib_directory = os.path.join(script_directory, "lib")
if lib_directory not in sys.path:
    sys.path.insert(0, lib_directory)


def main():
    parser = argparse.ArgumentParser(
        description="Process cuneiform tablet images (headless).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--root', required=True,
                        help='Root folder containing tablet subfolders')
    parser.add_argument('--tablets', nargs='*', default=None,
                        help='Specific tablet names to process (default: all)')
    parser.add_argument('--museum', default='Non-eBL Ruler (VAM)',
                        help='Museum ruler configuration to use')
    parser.add_argument('--measurements', default=None,
                        help='Path to Excel measurements file')
    parser.add_argument('--photographer', default='Unknown',
                        help='Photographer name for metadata')
    parser.add_argument('--ruler-position', default='bottom',
                        choices=['top', 'bottom', 'left', 'right'],
                        help='Ruler position in final stitched image')
    parser.add_argument('--add-logo', action='store_true',
                        help='Add institution logo to output')
    parser.add_argument('--logo-path', default=None,
                        help='Path to logo image file')
    parser.add_argument('--json-progress', action='store_true',
                        help='Emit progress as JSON lines for programmatic parsing')

    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"ERROR: Root folder does not exist: {args.root}", file=sys.stderr)
        return 2

    # Load measurements if provided
    measurements_dict = {}
    if args.measurements:
        if not os.path.isfile(args.measurements):
            print(f"WARNING: Measurements file not found: {args.measurements}", file=sys.stderr)
        else:
            try:
                from measurements_utils import load_measurements_from_excel, load_measurements_from_json
                ext = os.path.splitext(args.measurements)[1].lower()
                if ext in ('.xlsx', '.xls'):
                    measurements_dict = load_measurements_from_excel(args.measurements)
                else:
                    measurements_dict = load_measurements_from_json(args.measurements)
                print(f"Loaded {len(measurements_dict)} measurements from {os.path.basename(args.measurements)}.")
            except Exception as e:
                print(f"WARNING: Could not load measurements: {e}", file=sys.stderr)

    # Load the project's measurements file if --measurements not provided explicitly
    if not args.measurements:
        try:
            sys.path.insert(0, lib_directory)
            import project_manager
            from measurements_utils import load_measurements_from_json, load_measurements_from_excel, merge_measurements_dicts
            proj = project_manager.get_project_by_name(args.museum)
            proj_meas = (proj or {}).get("measurements_file", "")
            if proj_meas:
                meas_path = project_manager.resolve_asset_path(proj_meas)
                if os.path.isfile(meas_path):
                    ext = os.path.splitext(meas_path)[1].lower()
                    if ext in ('.xlsx', '.xls'):
                        proj_data = load_measurements_from_excel(meas_path)
                    else:
                        proj_data = load_measurements_from_json(meas_path)
                    measurements_dict = merge_measurements_dicts(proj_data, measurements_dict)
                    print(f"Loaded {len(proj_data)} reference measurements from project '{args.museum}'.")
        except Exception as e:
            print(f"Warning: Could not load project measurements: {e}", file=sys.stderr)

    # Import the workflow
    try:
        from gui_workflow_runner import run_complete_image_processing_workflow
        from stitch_config import STITCH_VIEW_PATTERNS_WITH_EXT
        from object_extractor import DEFAULT_EXTRACTED_OBJECT_FILENAME_SUFFIX as OBJECT_ARTIFACT_SUFFIX
    except ImportError as e:
        print(f"ERROR: Could not import stitcher modules: {e}", file=sys.stderr)
        print("Ensure the script is run from the ebl-photo-stitcher directory.", file=sys.stderr)
        return 1

    # Asset paths
    assets_dir = os.path.join(script_directory, 'assets')
    ruler_1cm = os.path.join(assets_dir, 'BM_1cm_scale.tif')
    ruler_2cm = os.path.join(assets_dir, 'BM_2cm_scale.tif')
    ruler_5cm = os.path.join(assets_dir, 'BM_5cm_scale.tif')

    # Progress reporting
    def progress_callback(value):
        if args.json_progress:
            print(json.dumps({'type': 'progress', 'value': value}), flush=True)
        # Also print human-readable
        sys.stdout.flush()

    finished_flag = {'done': False}

    def finished_callback():
        finished_flag['done'] = True
        if args.json_progress:
            print(json.dumps({'type': 'finished'}), flush=True)

    # Announce start
    if args.json_progress:
        print(json.dumps({
            'type': 'start',
            'root': args.root,
            'tablets': args.tablets,
            'museum': args.museum,
        }), flush=True)

    print(f"=== Starting stitcher ===")
    print(f"  Root: {args.root}")
    if args.tablets:
        print(f"  Tablets: {', '.join(args.tablets)}")
    else:
        print(f"  Tablets: ALL")
    print(f"  Museum: {args.museum}")

    # Run the workflow directly (blocking, no thread)
    try:
        run_complete_image_processing_workflow(
            args.root,                                  # source_folder_path
            args.ruler_position,                        # ruler_position
            args.photographer,                          # photographer_name
            'rembg',                                    # object_extraction_bg_mode
            args.add_logo,                              # add_logo
            args.logo_path,                             # logo_path
            '.cr2',                                     # raw_ext_config
            ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'),  # image_extensions
            ruler_1cm, ruler_2cm, ruler_5cm,            # ruler templates
            STITCH_VIEW_PATTERNS_WITH_EXT,              # view_file_patterns_config
            "temp_isolated_ruler.tif",                  # temp_ruler_filename
            OBJECT_ARTIFACT_SUFFIX,                     # object_artifact_suffix
            progress_callback,
            finished_callback,
            museum_selection=args.museum,
            app_root_window=None,
            use_measurements_from_database=bool(measurements_dict),
            measurements_dict=measurements_dict,
            selected_tablets=args.tablets,
        )
    except Exception as e:
        print(f"ERROR during processing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        if args.json_progress:
            print(json.dumps({'type': 'error', 'message': str(e)}), flush=True)
        return 1

    print("=== Done ===")
    return 0


if __name__ == '__main__':
    sys.exit(main())
