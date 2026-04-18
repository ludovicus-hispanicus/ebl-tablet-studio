import cv2
import numpy as np
import os

try:
    from stitch_config import (
        STITCH_VIEW_GAP_PX,
        STITCH_RULER_PADDING_PX
    )
    from stitch_layout_utils import get_image_dimension
    from stitch_intermediates_manager import group_intermediate_images, calculate_row_widths
    from stitch_image_processing import resize_tablet_views_for_layout, create_rotated_images
except ImportError as e:
    print(f"FATAL ERROR: stitch_layout_calculation.py cannot import: {e}")
    STITCH_VIEW_GAP_PX = 10
    STITCH_RULER_PADDING_PX = 20

    def get_image_dimension(*args, **kwargs): return 0
    def group_intermediate_images(*args, **kwargs): return {}
    def calculate_row_widths(*args, **kwargs): return 0, 0, []
    def resize_tablet_views_for_layout(*args, **kwargs): return {}
    def create_rotated_images(*args, **kwargs): return {}


def calculate_stitching_layout(
    object_images_dict, ruler_image_path, logo_image_path, pixels_per_cm,
    view_file_patterns_config, gap_px=100, ruler_padding_px=100, 
    final_margin_px=100, museum_selection="British Museum", 
    custom_layout=None, logo_standard_width_px=1800
):
    print(f"DEBUG: calculate_stitching_layout called with:")
    print(f"  object_images_dict keys: {list(object_images_dict.keys()) if object_images_dict else 'None'}")
    print(f"  ruler_image_path: {ruler_image_path}")
    print(f"  logo_image_path: {logo_image_path}")
    print(f"  custom_layout: {custom_layout}")
    print(f"  museum_selection: {museum_selection}")

    if not object_images_dict:
        raise ValueError("No object images provided for layout calculation")

    for view_name, image_data in object_images_dict.items():
        print(f"  Checking view '{view_name}':")
        if isinstance(image_data, np.ndarray):
            if image_data.size > 0:
                height, width = image_data.shape[:2]

    standard_keys = ["obverse", "reverse", "top", "bottom"]

    if len(object_images_dict) == 4 and not any(key in standard_keys for key in object_images_dict.keys()):
        print("      Layout: Found exactly 4 images without standard naming. Assigning as obverse, reverse, top, bottom.")

        keys = list(object_images_dict.keys())
        standard_dict = {}

        for i, std_key in enumerate(standard_keys):
            if i < len(keys):
                standard_dict[std_key] = object_images_dict[keys[i]]
                print(f"      Renamed '{keys[i]}' to '{std_key}'")

        object_images_dict = standard_dict

    def get_sequence_primary_axis(view_key_for_seq):
        if "left" in view_key_for_seq.lower() or "right" in view_key_for_seq.lower():
            if "intermediate" in view_key_for_seq.lower() and ("top" in view_key_for_seq.lower() or "bottom" in view_key_for_seq.lower()):
                return 1
            return 0
        return 1

    obv_data = object_images_dict.get("obverse")
    obv_h = get_image_dimension(obv_data, 0, gap_px if isinstance(
        obv_data, list) and get_sequence_primary_axis("obverse") == 0 else 0)
    obv_w = get_image_dimension(obv_data, 1, gap_px if isinstance(
        obv_data, list) and get_sequence_primary_axis("obverse") == 1 else 0)

    if obv_h == 0 or obv_w == 0:
        if custom_layout:
            for key, data in object_images_dict.items():
                if data is not None and "ruler" not in key:
                    print(
                        f"      Layout: 'obverse' missing/invalid. Using '{key}' as primary for layout ref.")
                    obv_data = data
                    obv_h = get_image_dimension(obv_data, 0, gap_px if isinstance(
                        obv_data, list) and get_sequence_primary_axis(key) == 0 else 0)
                    obv_w = get_image_dimension(obv_data, 1, gap_px if isinstance(
                        obv_data, list) and get_sequence_primary_axis(key) == 1 else 0)
                    break
        if obv_h == 0 or obv_w == 0:
            raise ValueError(
                "A primary image (e.g., 'obverse' or other from custom_layout) with valid dimensions is required for layout.")

    l_w = get_image_dimension(object_images_dict.get("left"), 1, gap_px if isinstance(
        object_images_dict.get("left"), list) and get_sequence_primary_axis("left") == 1 else 0)
    r_w = get_image_dimension(object_images_dict.get("right"), 1, gap_px if isinstance(
        object_images_dict.get("right"), list) and get_sequence_primary_axis("right") == 1 else 0)
    l_h = get_image_dimension(object_images_dict.get("left"), 0, gap_px if isinstance(
        object_images_dict.get("left"), list) and get_sequence_primary_axis("left") == 0 else 0)
    r_h = get_image_dimension(object_images_dict.get("right"), 0, gap_px if isinstance(
        object_images_dict.get("right"), list) and get_sequence_primary_axis("right") == 0 else 0)

    b_h = get_image_dimension(object_images_dict.get("bottom"), 0, gap_px if isinstance(
        object_images_dict.get("bottom"), list) and get_sequence_primary_axis("bottom") == 0 else 0)
    b_w = get_image_dimension(object_images_dict.get("bottom"), 1, gap_px if isinstance(
        object_images_dict.get("bottom"), list) and get_sequence_primary_axis("bottom") == 1 else 0)

    rev_h = get_image_dimension(object_images_dict.get("reverse"), 0, gap_px if isinstance(
        object_images_dict.get("reverse"), list) and get_sequence_primary_axis("reverse") == 0 else 0)
    rev_w = get_image_dimension(object_images_dict.get("reverse"), 1, gap_px if isinstance(
        object_images_dict.get("reverse"), list) and get_sequence_primary_axis("reverse") == 1 else 0)

    t_h = get_image_dimension(object_images_dict.get("top"), 0, gap_px if isinstance(
        object_images_dict.get("top"), list) and get_sequence_primary_axis("top") == 0 else 0)
    t_w = get_image_dimension(object_images_dict.get("top"), 1, gap_px if isinstance(
        object_images_dict.get("top"), list) and get_sequence_primary_axis("top") == 1 else 0)

    rul_h = get_image_dimension(object_images_dict.get("ruler"), 0)
    rul_w = get_image_dimension(object_images_dict.get("ruler"), 1)

    intermediate_dims = {}
    for key, img_data in object_images_dict.items():
        if "intermediate" in key and img_data is not None:
            h = get_image_dimension(img_data, 0, gap_px if isinstance(
                img_data, list) and get_sequence_primary_axis(key) == 0 else 0)
            w = get_image_dimension(img_data, 1, gap_px if isinstance(
                img_data, list) and get_sequence_primary_axis(key) == 1 else 0)
            if h > 0 and w > 0:
                intermediate_dims[key] = {"h": h, "w": w, "data": img_data}

    grouped_intermediates = group_intermediate_images(intermediate_dims)

    left_data = object_images_dict.get("left")
    has_left = (left_data is not None and 
                (isinstance(left_data, np.ndarray) and left_data.size > 0) or 
                (isinstance(left_data, str) and os.path.exists(left_data))) and l_w > 0
    
    obv_data = object_images_dict.get("obverse")
    has_obverse = (obv_data is not None and 
                   (isinstance(obv_data, np.ndarray) and obv_data.size > 0) or 
                   (isinstance(obv_data, str) and os.path.exists(obv_data))) and obv_w > 0
    
    right_data = object_images_dict.get("right")
    has_right = (right_data is not None and 
                 (isinstance(right_data, np.ndarray) and right_data.size > 0) or 
                 (isinstance(right_data, str) and os.path.exists(right_data))) and r_w > 0
    
    reverse_data = object_images_dict.get("reverse")
    has_reverse = (reverse_data is not None and 
                   (isinstance(reverse_data, np.ndarray) and reverse_data.size > 0) or 
                   (isinstance(reverse_data, str) and os.path.exists(reverse_data))) and rev_w > 0

    obv_row_width, rev_row_width, potential_canvas_widths = calculate_row_widths(
        grouped_intermediates, has_left, has_obverse, has_right, has_reverse,
        l_w, obv_w, r_w, rev_w, gap_px
    )

    if rev_row_width > 0:
        potential_canvas_widths.append(rev_row_width + 200)
    if obv_row_width > 0:
        potential_canvas_widths.append(obv_row_width + 200)

    for top_int in grouped_intermediates["obverse_top"]:
        potential_canvas_widths.append(top_int["dims"]["w"])

    for bottom_int in grouped_intermediates["obverse_bottom"]:
        potential_canvas_widths.append(bottom_int["dims"]["w"])

    for top_int in grouped_intermediates["reverse_top"]:
        potential_canvas_widths.append(top_int["dims"]["w"])

    for bottom_int in grouped_intermediates["reverse_bottom"]:
        potential_canvas_widths.append(bottom_int["dims"]["w"])

    if b_w > 0:
        potential_canvas_widths.append(b_w)
    if t_w > 0:
        potential_canvas_widths.append(t_w)
    if rul_w > 0:
        potential_canvas_widths.append(rul_w)

    central_column_width = max(obv_w, rev_w) if has_obverse and has_reverse else (
        obv_w if has_obverse else rev_w)

    base_canvas_width = 0
    if has_left:
        base_canvas_width += l_w + gap_px
    base_canvas_width += central_column_width
    if has_right:
        base_canvas_width += gap_px + r_w

    ruler_extra_width = 0
    if rul_w > 0 and rul_w > central_column_width:
        ruler_extra_width = rul_w - central_column_width

    base_canvas_w = max(potential_canvas_widths) if potential_canvas_widths else 800

    min_canvas_for_ruler = 0
    if rul_w > 0:
        if has_left and has_right:
            min_canvas_for_ruler = l_w + gap_px + rul_w + gap_px + r_w + 200
        elif has_left:
            min_canvas_for_ruler = l_w + gap_px + rul_w + 200
        elif has_right:
            min_canvas_for_ruler = 200 + rul_w + gap_px + r_w
        else:
            min_canvas_for_ruler = rul_w + 200

    canvas_w = max(base_canvas_w + 200, min_canvas_for_ruler)

    if has_left:
        if ruler_extra_width > 0:
            extra_space_each_side = ruler_extra_width // 2
            central_column_x = l_w + gap_px + extra_space_each_side

            ruler_left = central_column_x + (central_column_width - rul_w) // 2
            ruler_right = ruler_left + rul_w

            if ruler_left < 100:
                adjustment = 100 - ruler_left
                central_column_x += adjustment
                canvas_w = max(canvas_w, ruler_right + adjustment + 100)
            elif ruler_right > canvas_w - 100:
                adjustment = ruler_right - (canvas_w - 100)
                canvas_w += adjustment
        else:
            central_column_x = l_w + gap_px
    else:
        if ruler_extra_width > 0:
            tentative_central_x = (canvas_w - central_column_width) // 2
            ruler_left = tentative_central_x + (central_column_width - rul_w) // 2
            ruler_right = ruler_left + rul_w

            if ruler_left < 100:
                central_column_x = 100 + (rul_w - central_column_width) // 2
                new_ruler_right = central_column_x + (central_column_width + rul_w) // 2
                canvas_w = max(canvas_w, new_ruler_right + 100)
            elif ruler_right > canvas_w - 100:
                needed_width = ruler_right + 100
                canvas_w = max(canvas_w, needed_width)
                central_column_x = tentative_central_x
            else:
                central_column_x = tentative_central_x
        else:
            central_column_x = (canvas_w - central_column_width) // 2

    coords = {}
    rotation_flags = {}
    y_curr = 100

    int_obv_l_key = "intermediate_obverse_left"
    int_obv_r_key = "intermediate_obverse_right"
    int_rev_l_key = "intermediate_reverse_left"
    int_rev_r_key = "intermediate_reverse_right"
    int_obv_t_key = "intermediate_obverse_top"
    int_obv_b_key = "intermediate_obverse_bottom"
    int_rev_t_key = "intermediate_reverse_top"
    int_rev_b_key = "intermediate_reverse_bottom"

    has_int_obv_l = int_obv_l_key in intermediate_dims
    has_int_obv_r = int_obv_r_key in intermediate_dims
    has_int_rev_l = int_rev_l_key in intermediate_dims
    has_int_rev_r = int_rev_r_key in intermediate_dims

    # === SPINE-FIRST LAYOUT ===
    # Step 1: Determine the spine (vertebral column) width and center it.
    # The spine consists of: obverse, bottom, reverse, top — centered on the canvas.
    # Side views are attached afterwards without moving the spine.

    spine_width = max(
        obv_w if has_obverse else 0,
        rev_w if has_reverse else 0,
        b_w if object_images_dict.get("bottom") is not None and b_h > 0 else 0,
        t_w if object_images_dict.get("top") is not None and t_h > 0 else 0
    )

    # Calculate total width needed for sides (to ensure canvas is wide enough)
    left_side_width = 0
    if has_left:
        left_side_width += l_w + gap_px
    for left_int in grouped_intermediates["obverse_left"]:
        left_side_width += left_int["dims"]["w"] + gap_px
    for left_int in grouped_intermediates["reverse_left"]:
        left_side_width = max(left_side_width, left_int["dims"]["w"] + gap_px)

    right_side_width = 0
    if has_right:
        right_side_width += r_w + gap_px
    for right_int in grouped_intermediates["obverse_right"]:
        right_side_width += right_int["dims"]["w"] + gap_px
    for right_int in grouped_intermediates["reverse_right"]:
        right_side_width = max(right_side_width, right_int["dims"]["w"] + gap_px)

    # Ensure canvas is wide enough for spine + sides + margins
    min_needed = 200 + left_side_width + spine_width + right_side_width
    canvas_w = max(canvas_w, min_needed)

    # Center the spine on the canvas
    central_column_x = (canvas_w - spine_width) // 2
    central_column_width = spine_width

    # Step 2: Place views top-to-bottom along the spine, then attach sides

    # --- Obverse top intermediates ---
    for top_int in grouped_intermediates["obverse_top"]:
        int_key = top_int["key"]
        int_data = top_int["dims"]
        int_x = central_column_x + (central_column_width - int_data["w"]) // 2
        coords[int_key] = (int_x, y_curr)
        y_curr += int_data["h"] + gap_px

    # --- Obverse row: spine view centered, sides attached ---
    obv_row_y = y_curr

    if has_obverse:
        obv_center_x = central_column_x + (central_column_width - obv_w) // 2
        coords["obverse"] = (obv_center_x, obv_row_y)

        # Place left sides going leftward from obverse
        current_x = obv_center_x - gap_px
        left_intermediates = grouped_intermediates["obverse_left"]
        left_intermediates.sort(key=lambda x: x["number"], reverse=True)
        for left_int in left_intermediates:
            int_key = left_int["key"]
            int_w = left_int["dims"]["w"]
            img_h = intermediate_dims[int_key]["h"]
            int_y = obv_row_y + (obv_h - img_h) // 2
            current_x -= int_w
            coords[int_key] = (current_x, int_y)
            current_x -= gap_px
        if has_left:
            current_x -= l_w
            coords["left"] = (current_x, obv_row_y)
            rotation_flags["left"] = False
        # Ensure nothing is clipped on the left
        leftmost_x = current_x if has_left else min((coords[li["key"]][0] for li in grouped_intermediates["obverse_left"]), default=obv_center_x)
        if leftmost_x < 100:
            shift = 100 - leftmost_x
            canvas_w += shift
            central_column_x += shift
            for k in coords:
                coords[k] = (coords[k][0] + shift, coords[k][1])
            obv_center_x += shift

        # Place right sides going rightward from obverse
        current_x = obv_center_x + obv_w + gap_px
        right_intermediates = grouped_intermediates["obverse_right"]
        right_intermediates.sort(key=lambda x: x["number"])
        for right_int in right_intermediates:
            int_key = right_int["key"]
            int_w = right_int["dims"]["w"]
            img_h = intermediate_dims[int_key]["h"]
            int_y = obv_row_y + (obv_h - img_h) // 2
            coords[int_key] = (current_x, int_y)
            current_x += int_w + gap_px
        if has_right:
            coords["right"] = (current_x, obv_row_y)
            rotation_flags["right"] = False
            current_x += r_w
        # Ensure nothing is clipped on the right
        if current_x > canvas_w - 100:
            canvas_w = current_x + 100

    y_curr += obv_h + gap_px

    # --- Obverse bottom intermediates ---
    for bottom_int in grouped_intermediates["obverse_bottom"]:
        int_key = bottom_int["key"]
        int_data = bottom_int["dims"]
        int_x = central_column_x + (central_column_width - int_data["w"]) // 2
        coords[int_key] = (int_x, y_curr)
        y_curr += int_data["h"] + gap_px

    # --- Bottom view (spine) ---
    if object_images_dict.get("bottom") is not None and b_h > 0:
        bottom_x = central_column_x + (central_column_width - b_w) // 2
        coords["bottom"] = (bottom_x, y_curr)
        y_curr += b_h + gap_px

    # --- Reverse top intermediates ---
    for top_int in grouped_intermediates["reverse_top"]:
        int_key = top_int["key"]
        int_data = top_int["dims"]
        int_x = central_column_x + (central_column_width - int_data["w"]) // 2
        coords[int_key] = (int_x, y_curr)
        y_curr += int_data["h"] + gap_px

    # --- Reverse row: spine view centered, sides attached ---
    rev_row_y = y_curr

    if has_reverse:
        rev_center_x = central_column_x + (central_column_width - rev_w) // 2
        coords["reverse"] = (rev_center_x, rev_row_y)

        # Place left sides going leftward from reverse
        current_x = rev_center_x - gap_px
        left_intermediates = grouped_intermediates["reverse_left"]
        left_intermediates.sort(key=lambda x: x["number"], reverse=True)
        for left_int in left_intermediates:
            int_key = left_int["key"]
            int_w = left_int["dims"]["w"]
            img_h = intermediate_dims[int_key]["h"]
            int_y = rev_row_y + (rev_h - img_h) // 2
            current_x -= int_w
            coords[int_key] = (current_x, int_y)
            current_x -= gap_px
        if has_left:
            current_x -= l_w
            rotated_left_y = rev_row_y + (rev_h - l_h) // 2
            coords["left_rotated"] = (current_x, rotated_left_y)
            rotation_flags["left_rotated"] = True
        # Ensure nothing is clipped on the left
        leftmost_x = current_x if has_left else min((coords[li["key"]][0] for li in grouped_intermediates["reverse_left"]), default=rev_center_x)
        if leftmost_x < 100:
            shift = 100 - leftmost_x
            canvas_w += shift
            central_column_x += shift
            for k in coords:
                coords[k] = (coords[k][0] + shift, coords[k][1])
            rev_center_x += shift

        # Place right sides going rightward from reverse
        current_x = rev_center_x + rev_w + gap_px
        right_intermediates = grouped_intermediates["reverse_right"]
        right_intermediates.sort(key=lambda x: x["number"])
        for right_int in right_intermediates:
            int_key = right_int["key"]
            int_w = right_int["dims"]["w"]
            img_h = intermediate_dims[int_key]["h"]
            int_y = rev_row_y + (rev_h - img_h) // 2
            coords[int_key] = (current_x, int_y)
            current_x += int_w + gap_px
        if has_right:
            rotated_right_y = rev_row_y + (rev_h - r_h) // 2
            coords["right_rotated"] = (current_x, rotated_right_y)
            rotation_flags["right_rotated"] = True
            current_x += r_w
        # Ensure nothing is clipped on the right
        if current_x > canvas_w - 100:
            canvas_w = current_x + 100

    y_curr += rev_h + gap_px

    for bottom_int in grouped_intermediates["reverse_bottom"]:
        int_key = bottom_int["key"]
        int_data = bottom_int["dims"]
        int_x = central_column_x + (central_column_width - int_data["w"]) // 2
        coords[int_key] = (int_x, y_curr)
        y_curr += int_data["h"] + gap_px

    if object_images_dict.get("top") is not None and t_h > 0:
        top_x = central_column_x + (central_column_width - t_w) // 2
        coords["top"] = (top_x, y_curr)
        y_curr += t_h + gap_px

    if object_images_dict.get("ruler") is not None and rul_h > 0:
        y_curr += ruler_padding_px - gap_px
        ruler_x = central_column_x + (central_column_width - rul_w) // 2

        if ruler_x < 0:
            adjustment = -ruler_x + 50
            canvas_w += adjustment
            central_column_x += adjustment
            ruler_x = central_column_x + (central_column_width - rul_w) // 2

            for key in coords:
                if coords[key] and len(coords[key]) >= 2:
                    coords[key] = (coords[key][0] + adjustment, coords[key][1])
        elif ruler_x + rul_w > canvas_w:
            adjustment = (ruler_x + rul_w) - canvas_w + 50
            canvas_w += adjustment

        coords["ruler"] = (ruler_x, y_curr)
        y_curr += rul_h

    canvas_h = y_curr + 100

    max_right_edge = 0
    elements_to_adjust = []
    for key, (x, y) in coords.items():
        if key in object_images_dict:
            img_data = object_images_dict[key]
            if isinstance(img_data, np.ndarray) and img_data.size > 0:
                img_width = img_data.shape[1]
                right_edge = x + img_width
                max_right_edge = max(max_right_edge, right_edge)
                if right_edge > canvas_w - 100:
                    elements_to_adjust.append((key, right_edge))
        elif key in intermediate_dims:
            img_width = intermediate_dims[key]["w"]
            right_edge = x + img_width
            max_right_edge = max(max_right_edge, right_edge)
            if right_edge > canvas_w - 100:
                elements_to_adjust.append((key, right_edge))
    
    if max_right_edge > canvas_w - 100:
        old_canvas_w = canvas_w
        canvas_w = max_right_edge + 100
        print(f"WARNING: Canvas width expanded from {old_canvas_w} to {canvas_w}")
        print(f"Elements extending beyond original canvas: {[key for key, _ in elements_to_adjust]}")

    modified_images_dict = create_rotated_images(object_images_dict)

    for key, data in intermediate_dims.items():
        if key in coords:
            modified_images_dict[key] = data["data"]

    return int(canvas_w), int(canvas_h), coords, modified_images_dict