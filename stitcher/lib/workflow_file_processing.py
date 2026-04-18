import os
from workflow_imports import get_extended_intermediate_suffixes, determine_ruler_image_for_scaling


def find_ruler_and_views(subfolder_path_item, subfolder_name_item, all_files_in_subfolder,
                         image_extensions_tuple, view_file_patterns_config, object_artifact_suffix_config):
    """Find ruler image and identify other views."""

    image_files_for_layout = []
    for f_name in all_files_in_subfolder:
        if f_name.lower().endswith(image_extensions_tuple):
            image_files_for_layout.append(os.path.join(subfolder_path_item, f_name))

    intermediate_suffix_patterns = get_extended_intermediate_suffixes()
    if len(image_files_for_layout) > 6:
        print(
            f"   Subfolder {subfolder_name_item} has {len(image_files_for_layout)} images.")
        print(
            f"   Using automatic suffix detection for intermediate images (looking for: {list(intermediate_suffix_patterns.keys())})")
        print(f"   Images exceeding 6 without suffix patterns will be ignored.")

    view_original_suffix_patterns_config = view_file_patterns_config if view_file_patterns_config else {}

    rel_count = 0
    pr02_reverse, pr03_top, pr04_bottom = None, None, None
    orig_views_fps = {}

    for fn in all_files_in_subfolder:
        fn_low = fn.lower()
        full_fp = os.path.join(subfolder_path_item, fn)

        if fn_low.endswith(image_extensions_tuple):
            if (object_artifact_suffix_config not in fn
                and "_scaled_ruler." not in fn
                and "temp_isolated_ruler" not in fn
                    and not fn_low.endswith("_rawscale.tif")):
                rel_count += 1

            if "reverse" in view_original_suffix_patterns_config and view_original_suffix_patterns_config["reverse"] in fn_low:
                pr02_reverse = full_fp
            if "top" in view_original_suffix_patterns_config and view_original_suffix_patterns_config["top"] in fn_low:
                pr03_top = full_fp
            if "bottom" in view_original_suffix_patterns_config and view_original_suffix_patterns_config["bottom"] in fn_low:
                pr04_bottom = full_fp

            for vk, sp_pattern_suffix in view_original_suffix_patterns_config.items():
                if not sp_pattern_suffix:
                    continue
                core_pattern = os.path.splitext(sp_pattern_suffix)[0]
                expected_prefix_in_filename = subfolder_name_item + core_pattern

                if fn_low.startswith(expected_prefix_in_filename.lower()):
                    orig_views_fps[vk] = full_fp

    ruler_for_scale_fp = determine_ruler_image_for_scaling(
        None, orig_views_fps, image_files_for_layout,
        pr02_reverse, pr03_top, pr04_bottom, rel_count
    )

    return ruler_for_scale_fp, orig_views_fps
