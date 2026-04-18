from stitch_config import get_extended_intermediate_suffixes
import os
import sys
import cv2
import numpy as np
import re

script_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(script_directory)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)


def generate_position_patterns():
    """
    Generate regex patterns for intermediate image positions based on configuration.
    """
    intermediate_suffixes = get_extended_intermediate_suffixes()
    all_codes = list(intermediate_suffixes.keys())
    code_pattern = r'_(' + '|'.join(all_codes) + r')_'
    full_name_pattern = r'intermediate_[^_]+_([^_\.]+)(?:_\d+)?'
    
    return [code_pattern, full_name_pattern]


def apply_blending_mask_to_intermediate(
    image_array,
    intermediate_position,
    background_color=(0, 0, 0),
    gradient_width_fraction=0.8
):
    """
    Apply a gradient blending mask to an intermediate image based on its position.

    Args:
        image_array: The BGR image array to apply the mask to
        intermediate_position: String indicating the position (e.g., "intermediate_obverse_left", "ol", etc.)
        background_color: BGR tuple for the background color
        gradient_width_fraction: How much of the image should be covered by the gradient (0.0-1.0)

    Returns:
        The image with gradient mask applied
    """
    if image_array is None or image_array.size == 0:
        return image_array

    h, w = image_array.shape[:2]
    if h == 0 or w == 0:
        return image_array

    position = _normalize_position_name(intermediate_position)

    mask = np.ones((h, w), dtype=np.float32)

    gradient_size_px = {
        "left": int(w * gradient_width_fraction),
        "right": int(w * gradient_width_fraction),
        "top": int(h * gradient_width_fraction),
        "bottom": int(h * gradient_width_fraction)
    }

    if "right" in position:

        for x in range(min(gradient_size_px["right"], w)):
            alpha = x / gradient_size_px["right"]
            mask[:, x] = alpha

    elif "left" in position:

        for x in range(min(gradient_size_px["left"], w)):
            alpha = x / gradient_size_px["left"]
            mask[:, w - x - 1] = alpha

    elif "top" in position:

        for y in range(min(gradient_size_px["top"], h)):
            alpha = y / gradient_size_px["top"]
            mask[h - y - 1, :] = alpha

    elif "bottom" in position:

        for y in range(min(gradient_size_px["bottom"], h)):
            alpha = y / gradient_size_px["bottom"]
            mask[y, :] = alpha

    background = np.full_like(image_array, background_color, dtype=np.uint8)

    mask_3ch = np.stack([mask] * 3, axis=2)
    blended = cv2.convertScaleAbs(
        image_array * mask_3ch + background * (1 - mask_3ch)
    )

    return blended


def _normalize_position_name(position):
    """Normalize various position name formats to a standard form"""
    position = position.lower()
    base_position = re.sub(r'\d+$', '', position)
    if base_position == '07' or position == '07':
        return 'left'
    elif base_position == '08' or position == '08':
        return 'right'
    elif base_position == 'ol' or base_position == 'rl':
        return 'left'
    elif base_position == 'or' or base_position == 'rr':
        return 'right'
    elif base_position == 'ot' or base_position == 'rt':
        return 'top'
    elif base_position == 'ob' or base_position == 'rb':
        return 'bottom'
    if 'left' in position:
        return 'left'
    elif 'right' in position:
        return 'right'
    elif 'top' in position:
        return 'top'
    elif 'bottom' in position:
        return 'bottom'

    return position


def process_intermediate_image_with_mask(
    input_image_path,
    background_color=(0, 0, 0),
    gradient_width_fraction=0.5
):
    """
    Load an intermediate image, apply the appropriate blending mask, and save it back.

    Args:
        input_image_path: Path to the intermediate image (must contain position indicator)
        background_color: BGR tuple for the background color
        gradient_width_fraction: How much of the image should be covered by the gradient (0.0-1.0)

    Returns:
        Path to the processed image (same as input path)
    """

    basename = os.path.basename(input_image_path)

    position = None
    position_patterns = generate_position_patterns()
    for pattern in position_patterns:
        match = re.search(pattern, basename.lower())
        if match:
            position = match.group(1)
            break
    if not position:
        for code in get_extended_intermediate_suffixes().keys():
            if f"_{code}_" in basename.lower():
                position = code
                break

    if not position:
        print(f"  Warning: Could not detect intermediate position from {basename}")
        return input_image_path

    image = cv2.imread(input_image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        print(f"  Error: Failed to load intermediate image: {input_image_path}")
        return input_image_path

    blended_image = apply_blending_mask_to_intermediate(
        image, position, background_color, gradient_width_fraction
    )

    if not cv2.imwrite(input_image_path, blended_image):
        print(f"  Error: Failed to save blended intermediate image: {input_image_path}")

    return input_image_path
