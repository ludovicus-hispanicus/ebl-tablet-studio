import cv2
import numpy as np
import math

import cv2
import numpy as np


def detect_dominant_corner_background_color(
    image_bgr_array,
    corner_fraction=0.025,
    dark_snap_threshold=50,
    light_snap_threshold=205,
    museum_selection=None
):
    """
    Detects the dominant background color by averaging corner pixels.
    Snaps to pure black or pure white if the average color is very dark or very bright.

    Args:
        image_bgr_array: The input image as a NumPy BGR array.
        corner_fraction: The fraction of image dimensions to define corner sample size.
                         Default is 0.7, which is very large and might include foreground.
                         Recommended to use a smaller value like 0.05 or 0.1.
        dark_snap_threshold: If avg. corner grayscale intensity < this, returns black.
        light_snap_threshold: If avg. corner grayscale intensity > this, returns white.
        museum_selection: Unused parameter.

    Returns:
        A tuple representing the determined background BGR color.
    """
    img_height, img_width = image_bgr_array.shape[:2]

    sample_size_h = max(1, int(img_height * corner_fraction))
    sample_size_w = max(1, int(img_width * corner_fraction))

    corner_sections_list = [
        image_bgr_array[0:sample_size_h, 0:sample_size_w],
        image_bgr_array[0:sample_size_h, img_width - sample_size_w:img_width],
        image_bgr_array[img_height - sample_size_h:img_height, 0:sample_size_w],
        image_bgr_array[img_height - sample_size_h:img_height,
                        img_width - sample_size_w:img_width]
    ]

    all_corner_pixels = []
    for section in corner_sections_list:
        if section.size > 0:
            reshaped_section = section.reshape(-1, 3)
            all_corner_pixels.extend(reshaped_section)

    if not all_corner_pixels:

        if dark_snap_threshold >= 0:
            return (0, 0, 0)

    all_corner_pixels_np = np.array(all_corner_pixels)
    average_bgr_color_float = np.mean(all_corner_pixels_np, axis=0)

    clipped_bgr_color = np.clip(average_bgr_color_float, 0, 255)

    gray_intensity = (0.114 * clipped_bgr_color[0]
                      + 0.587 * clipped_bgr_color[1]
                      + 0.299 * clipped_bgr_color[2])

    if gray_intensity < dark_snap_threshold:
        final_bgr_color_tuple = (0, 0, 0)
    elif gray_intensity > light_snap_threshold:
        final_bgr_color_tuple = (255, 255, 255)
    else:

        final_bgr_color_tuple = tuple(average_bgr_color_float.astype(int))

        final_bgr_color_tuple = tuple(np.clip(final_bgr_color_tuple, 0, 255))

    return final_bgr_color_tuple


def get_museum_background_color(museum_selection=None, detected_bg_color=(0, 0, 0)):
    # Prefer the active project's configured background color if available
    try:
        import project_manager
        active = project_manager.get_active_project()
        if active is not None and active.get("name") == museum_selection:
            bg = project_manager.get_project_background_color(active)
            return bg
    except Exception:
        pass

    if museum_selection is None or museum_selection == "British Museum" or museum_selection == "General (black background)":
        return (0, 0, 0)
    else:

        return (255, 255, 255)


def create_foreground_mask_from_background(
    image_bgr_array, background_bgr_color_tuple, color_similarity_tolerance
):
    """Create foreground mask by removing background color."""

    if background_bgr_color_tuple is not None:
        background_bgr_color_tuple = tuple(int(c) for c in background_bgr_color_tuple)
    else:
        background_bgr_color_tuple = (0, 0, 0)
    
    color_similarity_tolerance = int(color_similarity_tolerance)

    lower_bound = tuple(max(0, int(c) - color_similarity_tolerance) for c in background_bgr_color_tuple)
    upper_bound = tuple(min(255, int(c) + color_similarity_tolerance) for c in background_bgr_color_tuple)

    lower_bound = np.array(lower_bound, dtype=np.uint8)
    upper_bound = np.array(upper_bound, dtype=np.uint8)

    mask = cv2.inRange(image_bgr_array, lower_bound, upper_bound)
    return cv2.bitwise_not(mask)  # Invert to get foreground


def select_contour_closest_to_image_center(
    image_bgr_array, foreground_objects_mask, min_contour_area_as_image_fraction
):
    img_height, img_width = image_bgr_array.shape[:2]
    img_center_x, img_center_y = img_width / 2, img_height / 2
    img_total_area = img_height * img_width

    contours_found, _ = cv2.findContours(
        foreground_objects_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours_found:
        return None

    qualifying_contours = [
        cnt for cnt in contours_found
        if cv2.contourArea(cnt) >= img_total_area * min_contour_area_as_image_fraction
    ]
    if not qualifying_contours:
        return None

    best_contour, shortest_distance = None, float('inf')
    for contour_candidate in qualifying_contours:
        moments_data = cv2.moments(contour_candidate)
        if moments_data["m00"] == 0:
            continue

        centroid_x_pos = int(moments_data["m10"] / moments_data["m00"])
        centroid_y_pos = int(moments_data["m01"] / moments_data["m00"])

        current_distance = math.sqrt(
            (centroid_x_pos - img_center_x)**2 + (centroid_y_pos - img_center_y)**2)
        if current_distance < shortest_distance:
            shortest_distance, best_contour = current_distance, contour_candidate
    return best_contour


def select_ruler_like_contour_from_list(
    list_of_all_contours, image_pixel_width, image_pixel_height,
    excluded_obj_contour=None, min_aspect_ratio_for_ruler=2.5,
    max_width_fraction_of_image=0.95, min_width_fraction_of_image=0.05,
    min_height_fraction_of_image=0.01, max_height_fraction_of_image=0.25
):
    plausible_ruler_contours = []
    for current_contour in list_of_all_contours:
        if excluded_obj_contour is not None and \
           cv2.matchShapes(current_contour, excluded_obj_contour, cv2.CONTOURS_MATCH_I1, 0.0) < 0.1:
            continue

        x_val, y_val, width_val, height_val = cv2.boundingRect(current_contour)
        if width_val == 0 or height_val == 0:
            continue

        actual_aspect_ratio = float(
            width_val) / height_val if width_val > height_val else float(height_val) / width_val
        width_as_image_fraction = float(width_val) / image_pixel_width
        height_as_image_fraction = float(height_val) / image_pixel_height

        is_plausible_width = min_width_fraction_of_image < width_as_image_fraction < max_width_fraction_of_image
        is_plausible_height = min_height_fraction_of_image < height_as_image_fraction < max_height_fraction_of_image

        if actual_aspect_ratio >= min_aspect_ratio_for_ruler and is_plausible_width and is_plausible_height:
            plausible_ruler_contours.append(
                {"contour": current_contour, "area": cv2.contourArea(current_contour)})

    if not plausible_ruler_contours:
        return None
    plausible_ruler_contours.sort(key=lambda c: c["area"], reverse=True)
    return plausible_ruler_contours[0]["contour"]
