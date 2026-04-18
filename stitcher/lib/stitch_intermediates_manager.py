"""
Functions for handling intermediate image positions and grouping.
"""
import re
try:
    from stitch_config import get_extended_intermediate_suffixes
    from blending_mask_applier import generate_position_patterns
except ImportError as e:
    print(f"FATAL ERROR: stitch_intermediates_manager.py cannot import: {e}")
    def get_extended_intermediate_suffixes(): return {}
    def generate_position_patterns(): return [
        r'_([a-z]{2}\d*)_', r'intermediate_[^_]+_([^_\.]+)(?:_\d+)?']


def group_intermediate_images(intermediate_dims):
    """
    Group intermediate images by their base position and sort by suffix number.

    Args:
        intermediate_dims: Dictionary of intermediate image dimensions

    Returns:
        Dictionary of grouped intermediate images
    """

    extended_intermediate_positions = get_extended_intermediate_suffixes()

    grouped_intermediates = {
        "obverse_top": [],
        "obverse_bottom": [],
        "obverse_left": [],
        "obverse_right": [],
        "reverse_top": [],
        "reverse_bottom": [],
        "reverse_left": [],
        "reverse_right": [],
    }

    for key in intermediate_dims:
        position_found = False
        suffix_number = 1

        matched_position = None

        position_patterns = generate_position_patterns()
        for pattern in position_patterns:
            match = re.search(pattern, key.lower())
            if match:
                matched_position = match.group(1)

                if len(matched_position) > 2 and matched_position[-1].isdigit():

                    suffix_match = re.search(r'([a-z]{2})(\d+)', matched_position)
                    if suffix_match:
                        base_code = suffix_match.group(1)
                        suffix_number = int(suffix_match.group(2))
                        matched_position = base_code

                for position_name in grouped_intermediates.keys():
                    if position_name.endswith(matched_position.replace("l", "_left").replace("r", "_right").replace("t", "_top").replace("b", "_bottom")):
                        grouped_intermediates[position_name].append({
                            "key": key,
                            "number": suffix_number,
                            "dims": intermediate_dims[key]
                        })
                        position_found = True
                        break

                    if position_name == matched_position:
                        grouped_intermediates[position_name].append({
                            "key": key,
                            "number": suffix_number,
                            "dims": intermediate_dims[key]
                        })
                        position_found = True
                        break

                if position_found:
                    break

        if not position_found:

            for position_name in grouped_intermediates.keys():
                full_position_name = f"intermediate_{position_name}"
                if key == full_position_name:

                    grouped_intermediates[position_name].append({
                        "key": key,
                        "number": suffix_number,
                        "dims": intermediate_dims[key]
                    })
                    position_found = True
                    break

            if not position_found:

                match = re.match(r'intermediate_([a-z]+_[a-z]+)_(\d+)', key)
                if match:
                    position_part = match.group(1)
                    suffix_number = int(match.group(2))

                    if position_part in grouped_intermediates:
                        grouped_intermediates[position_part].append({
                            "key": key,
                            "number": suffix_number,
                            "dims": intermediate_dims[key]
                        })
                        position_found = True

        if not position_found:
            print(f"      Layout: Trying fallback detection for: {key}")

            for position_name in grouped_intermediates.keys():
                if position_name in key:
                    print(
                        f"      Layout: Found intermediate with non-standard naming: {key}")
                    grouped_intermediates[position_name].append({
                        "key": key,
                        "number": 99,
                        "dims": intermediate_dims[key]
                    })
                    position_found = True
                    break

    for group_key in grouped_intermediates:
        grouped_intermediates[group_key].sort(key=lambda x: x["number"])

    return grouped_intermediates


def calculate_row_widths(grouped_intermediates, has_left, has_obverse, has_right, has_reverse,
                         l_w, obv_w, r_w, rev_w, view_gap_px):
    """
    Calculate widths for the obverse and reverse rows including all intermediate images.

    Args:
        grouped_intermediates: Dictionary of grouped intermediate images
        has_left, has_obverse, has_right, has_reverse: Boolean flags for presence of main views
        l_w, obv_w, r_w, rev_w: Widths of main views
        view_gap_px: Gap between views in pixels

    Returns:
        Tuple of (obv_row_full_width, rev_row_full_width, potential_canvas_widths)
    """
    potential_canvas_widths = []

    obv_row_full_width = 0
    if has_left:
        obv_row_full_width += l_w + view_gap_px

    for left_int in grouped_intermediates["obverse_left"]:
        int_w = left_int["dims"]["w"]
        obv_row_full_width += int_w + view_gap_px

    if has_obverse:
        obv_row_full_width += obv_w + view_gap_px

    for right_int in grouped_intermediates["obverse_right"]:
        int_w = right_int["dims"]["w"]
        obv_row_full_width += int_w + view_gap_px

    if has_right:
        obv_row_full_width += r_w

    if obv_row_full_width > 0 and (has_left or has_obverse or has_right or grouped_intermediates["obverse_left"] or grouped_intermediates["obverse_right"]):
        obv_row_full_width -= view_gap_px

    potential_canvas_widths.append(obv_row_full_width)

    rev_row_full_width = 0
    if has_left:
        rev_row_full_width += l_w + view_gap_px

    for left_int in grouped_intermediates["reverse_left"]:
        int_w = left_int["dims"]["w"]
        rev_row_full_width += int_w + view_gap_px

    if has_reverse:
        rev_row_full_width += rev_w + view_gap_px

    for right_int in grouped_intermediates["reverse_right"]:
        int_w = right_int["dims"]["w"]
        rev_row_full_width += int_w + view_gap_px

    if has_right:
        rev_row_full_width += r_w

    if rev_row_full_width > 0 and (has_left or has_reverse or has_right or grouped_intermediates["reverse_left"] or grouped_intermediates["reverse_right"]):
        rev_row_full_width -= view_gap_px

    potential_canvas_widths.append(rev_row_full_width)

    return obv_row_full_width, rev_row_full_width, potential_canvas_widths
