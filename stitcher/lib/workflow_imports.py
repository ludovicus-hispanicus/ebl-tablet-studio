import os
import sys


def _placeholder_func(*args, **kwargs):
    print(f"Error: Missing module for {args[0] if args else 'operation'}")


try:
    import resize_ruler
    import ruler_detector
    from blending_mask_applier import process_intermediate_image_with_mask
    from stitch_images import process_tablet_subfolder
    from stitch_config import (
        MUSEUM_CONFIGS,
        MAX_ADDITIONAL_INTERMEDIATES,
        get_extended_intermediate_suffixes
    )
    # Automatic tablet extraction uses rembg + U2NET (via onnxruntime).
    # SAM was evaluated here in Phase B.5 but reverted: SAM is a promptable
    # model and produces unpredictable mask choices on edge-view frames
    # where the tablet isn't the dominant object. U2NET is a salient-object-
    # detection model — right tool for this job. SAM stays in the Electron
    # UI for interactive click-to-segment; see lib/object_extractor_sam.py
    # which is kept on disk as a starting point if we revisit auto-SAM later.
    from object_extractor_rembg import extract_and_save_center_object
    from object_extractor import extract_specific_contour_to_image_array, DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE
    from remove_background import (
        create_foreground_mask_from_background as create_foreground_mask,
        select_contour_closest_to_image_center,
        select_ruler_like_contour_from_list as select_ruler_like_contour,
        get_museum_background_color,
        detect_dominant_corner_background_color
    )
    from raw_processor import convert_raw_image_to_tiff
    from put_images_in_subfolders import group_and_move_files_to_subfolders as organize_files_func
    import ruler_detector_iraq_museum
    from workflow_processing_steps import organize_project_subfolders, determine_ruler_image_for_scaling
    from measurements_utils import load_measurements_from_json, get_tablet_width_from_measurements
    from workflow_processing_steps import determine_pixels_per_cm_from_measurement

    IMPORTS_AVAILABLE = True

except ImportError as e:
    print(f"ERROR in workflow_imports.py: Failed to import a processing module: {e}")

    resize_ruler = type(
        'module', (), {'resize_and_save_ruler_template': _placeholder_func})
    ruler_detector = type(
        'module', (), {'estimate_pixels_per_centimeter_from_ruler': _placeholder_func})
    process_tablet_subfolder = _placeholder_func
    extract_and_save_center_object = lambda *a, **kw: (None, None)
    extract_specific_contour_to_image_array = _placeholder_func
    create_foreground_mask = _placeholder_func
    select_contour_closest_to_image_center = _placeholder_func
    select_ruler_like_contour = _placeholder_func
    convert_raw_image_to_tiff = _placeholder_func
    organize_files_func = lambda *a: []
    organize_project_subfolders = lambda *a, **kw: []
    determine_ruler_image_for_scaling = lambda *a, **kw: None
    detect_dominant_corner_background_color = lambda *a, **kw: (0, 0, 0)
    process_intermediate_image_with_mask = _placeholder_func
    get_museum_background_color = lambda *a, **kw: (0, 0, 0)
    def get_extended_intermediate_suffixes(): return {}
    ruler_detector_iraq_museum = type(
        'module', (), {'detect_1cm_distance_iraq': _placeholder_func})
    get_tablet_width_from_measurements = lambda *a, **kw: None
    determine_pixels_per_cm_from_measurement = lambda *a, **kw: None
    MUSEUM_CONFIGS = {}
    DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE = 20

    IMPORTS_AVAILABLE = False

__all__ = [
    'resize_ruler', 'ruler_detector', 'process_tablet_subfolder',
    'extract_and_save_center_object', 'extract_specific_contour_to_image_array',
    'create_foreground_mask', 'select_contour_closest_to_image_center',
    'select_ruler_like_contour', 'convert_raw_image_to_tiff', 'organize_files_func',
    'organize_project_subfolders', 'determine_ruler_image_for_scaling',
    'detect_dominant_corner_background_color', 'process_intermediate_image_with_mask',
    'get_museum_background_color', 'get_extended_intermediate_suffixes',
    'ruler_detector_iraq_museum', 'get_tablet_width_from_measurements',
    'determine_pixels_per_cm_from_measurement', 'MUSEUM_CONFIGS',
    'DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE', 'IMPORTS_AVAILABLE'
]
