import cv2
import numpy as np
import os
import sys
import math

try:
    from remove_background import (
        create_foreground_mask_from_background,
        select_contour_closest_to_image_center,
        detect_dominant_corner_background_color
    )
    from image_utils import get_mask_bounding_box
except ImportError:
    print("FATAL ERROR: object_extractor.py could not import from remove_background.py or image_utils.py.")

    def create_foreground_mask_from_background(
        *args): raise ImportError("create_foreground_mask_from_background missing")
    def select_contour_closest_to_image_center(
        *args): raise ImportError("select_contour_closest_to_image_center missing")

    def detect_dominant_corner_background_color(*args): return (0, 0, 0)
    def get_mask_bounding_box(*args): return None


DEFAULT_OUTPUT_CANVAS_BACKGROUND_BGR = (0, 0, 0)
DEFAULT_SOURCE_IMAGE_BACKGROUND_BGR_TO_REMOVE = (0, 0, 0)
DEFAULT_EDGE_FEATHER_RADIUS_PIXELS = 10
DEFAULT_EXTRACTED_OBJECT_FILENAME_SUFFIX = "_object.tif"
DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE = 40
DEFAULT_MINIMUM_OBJECT_CONTOUR_AREA_FRACTION = 0.010
DEFAULT_OBJECT_CONTOUR_SMOOTHING_KERNEL_SIZE = 100


def _create_feathered_alpha_blend_mask(binary_object_isolate_mask, feather_radius_px):
    if feather_radius_px <= 0:
        normalized_alpha_mask = binary_object_isolate_mask.astype(np.float32) / 255.0
    else:
        gaussian_kernel_size = feather_radius_px * 4 + 1
        gaussian_sigma_value = feather_radius_px * 0.8
        feathered_mask_blurred_grayscale = cv2.GaussianBlur(
            binary_object_isolate_mask,
            (gaussian_kernel_size, gaussian_kernel_size),
            gaussian_sigma_value
        )
        normalized_alpha_mask = feathered_mask_blurred_grayscale.astype(
            np.float32) / 255.0
    return cv2.merge([normalized_alpha_mask] * 3)


def _blend_original_on_new_background(
    original_image_bgr_array,
    feathered_alpha_mask_3_channel,
    new_background_bgr_color_tuple
):
    output_canvas_array = np.full_like(
        original_image_bgr_array, new_background_bgr_color_tuple, dtype=np.uint8)
    blended_image_float_precision = (
        output_canvas_array.astype(np.float32) * (1.0 - feathered_alpha_mask_3_channel)
        + original_image_bgr_array.astype(np.float32) * feathered_alpha_mask_3_channel
    )
    return blended_image_float_precision.astype(np.uint8)


def _crop_image_to_object_bounds(image_array_to_crop, binary_mask_for_bounding_box):
    object_bounding_box = get_mask_bounding_box(binary_mask_for_bounding_box)
    if object_bounding_box is None:
        return image_array_to_crop
    xmin, ymin, xmax, ymax = object_bounding_box
    return image_array_to_crop[ymin:ymax, xmin:xmax]


def extract_specific_contour_to_image_array(
    source_image_array,
    contour_to_extract,
    background_color=(0, 0, 0),
    padding_px=0,
    contour_smoothing_kernel_size=None
):
    """
    Extract a specific contour from the source image into a new image array.
    Used for ruler extraction.

    Args:
        source_image_array: Source image as a numpy array
        contour_to_extract: Contour to extract
        background_color: Background color for the output image
        padding_px: Padding in pixels
        contour_smoothing_kernel_size: Optional parameter for compatibility, not used

    Returns:
        Image array with only the extracted contour
    """

    x, y, w, h = cv2.boundingRect(contour_to_extract)

    x = max(0, x - padding_px)
    y = max(0, y - padding_px)
    w = min(source_image_array.shape[1] - x, w + 2 * padding_px)
    h = min(source_image_array.shape[0] - y, h + 2 * padding_px)

    result = np.full((h, w, 3), background_color, dtype=np.uint8)

    mask = np.zeros(
        (source_image_array.shape[0], source_image_array.shape[1]), dtype=np.uint8)
    cv2.drawContours(mask, [contour_to_extract], -1, 255, -1)

    for c in range(3):
        result[:, :, c] = background_color[c]

        roi_source = source_image_array[y:y + h, x:x + w, c]
        roi_mask = mask[y:y + h, x:x + w]
        result[:, :, c] = np.where(roi_mask > 0, roi_source, result[:, :, c])

    return result


def extract_and_save_center_object(
    input_image_filepath,
    source_background_detection_mode="auto",
    output_image_background_color=DEFAULT_OUTPUT_CANVAS_BACKGROUND_BGR,
    feather_radius_px=DEFAULT_EDGE_FEATHER_RADIUS_PIXELS,
    output_filename_suffix=DEFAULT_EXTRACTED_OBJECT_FILENAME_SUFFIX,
    background_color_tolerance_value=DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE,
    min_object_area_as_image_fraction=DEFAULT_MINIMUM_OBJECT_CONTOUR_AREA_FRACTION,
    object_contour_smoothing_kernel_size=DEFAULT_OBJECT_CONTOUR_SMOOTHING_KERNEL_SIZE,
    museum_selection=None
):
    print(f"  Extracting central object from: {os.path.basename(input_image_filepath)}")
    original_image_bgr_array = cv2.imread(input_image_filepath)
    if original_image_bgr_array is None:
        raise FileNotFoundError(
            f"Could not load image for object extraction: {input_image_filepath}")

    actual_source_background_bgr_color = DEFAULT_SOURCE_IMAGE_BACKGROUND_BGR_TO_REMOVE
    if source_background_detection_mode == "auto":
        actual_source_background_bgr_color = detect_dominant_corner_background_color(
            original_image_bgr_array, museum_selection=museum_selection)
    elif source_background_detection_mode == "white":
        actual_source_background_bgr_color = (255, 255, 255)

    initial_foreground_mask = create_foreground_mask_from_background(
        original_image_bgr_array, actual_source_background_bgr_color, background_color_tolerance_value
    )
    if initial_foreground_mask is None or np.sum(initial_foreground_mask) == 0:
        raise ValueError(
            "No foreground objects found against the specified/detected background.")

    center_artifact_main_contour = select_contour_closest_to_image_center(
        original_image_bgr_array, initial_foreground_mask, min_object_area_as_image_fraction
    )
    if center_artifact_main_contour is None:
        raise ValueError("No suitable center artifact contour found meeting criteria.")

    extracted_artifact_image_array = extract_specific_contour_to_image_array(
        original_image_bgr_array, center_artifact_main_contour,
        output_image_background_color, feather_radius_px,
        contour_smoothing_kernel_size=object_contour_smoothing_kernel_size
    )

    base_filepath, _ = os.path.splitext(input_image_filepath)
    output_image_filepath = f"{base_filepath}{output_filename_suffix}"
    try:
        if not cv2.imwrite(output_image_filepath, extracted_artifact_image_array):
            raise IOError("cv2.imwrite failed to save extracted artifact.")
        print(f"    Successfully saved extracted artifact: {output_image_filepath}")
        return output_image_filepath, center_artifact_main_contour
    except Exception as e:
        raise IOError(
            f"Error saving extracted artifact to {output_image_filepath}: {e}")

    if output_image_background_color is not None:
        output_image_background_color = tuple(int(c) for c in output_image_background_color)
    else:
        output_image_background_color = (0, 0, 0)
    background_color_tolerance_value = int(background_color_tolerance_value)
