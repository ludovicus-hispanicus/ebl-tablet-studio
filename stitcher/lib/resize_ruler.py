import cv2
import numpy as np
import os
from stitch_config import SCALED_RULER_FILE_SUFFIX
try:
    import cairosvg
    from io import BytesIO
    SVG_SUPPORT = True
except (ImportError, OSError) as e:
    SVG_SUPPORT = False
    print(f"Warning: cairosvg or its dependencies not found ({e}). SVG ruler support is disabled.")

RULER_TARGET_PHYSICAL_WIDTHS_CM_BRITISH_MUSEUM = {
    "1cm": 1.752173913043478,
    "2cm": 2.802631578947368,
    "5cm": 5.955752212389381
}
RULER_TARGET_PHYSICAL_WIDTHS_CM_JENA = {
    "1cm": 1,
    "2cm": 2,
    "5cm": 5
}
IMAGE_RESIZE_INTERPOLATION_METHOD = cv2.INTER_CUBIC


def svg_to_image(svg_file_path):
    """
    Convert SVG file to a NumPy array suitable for use with OpenCV.

    Args:
        svg_file_path: Path to the SVG file

    Returns:
        NumPy array representing the image
    """
    if not SVG_SUPPORT:
        raise ValueError(
            "SVG support is not available. Please install cairosvg module.")
    try:

        png_data = cairosvg.svg2png(url=svg_file_path, dpi=600)

        png_bytes = BytesIO(png_data)

        nparr = np.frombuffer(png_bytes.getvalue(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)

        if img.shape[2] == 4:

            alpha = img[:, :, 3]

            white_background = np.ones_like(img[:, :, :3], dtype=np.uint8) * 255

            rgb = img[:, :, :3]

            alpha_factor = alpha[:, :, np.newaxis].astype(np.float32) / 255.0
            blended = (rgb * alpha_factor + white_background
                       * (1 - alpha_factor)).astype(np.uint8)
            return blended

        return img
    except Exception as e:
        raise ValueError(f"Error converting SVG to image: {e}")


def resize_and_save_ruler_template(
    pixels_per_centimeter_scale,
    chosen_digital_ruler_template_path,
    output_base_name,
    output_directory_path,
    custom_ruler_size_cm=None,
    museum_selection=None
):
    """
    Resizes a digital ruler template to match the detected physical scale, 
    and saves it to the output directory.

    Args:
        pixels_per_centimeter_scale: The number of pixels per centimeter in the source image
        chosen_digital_ruler_template_path: Path to the digital ruler template to scale
        output_base_name: Base name for the output file
        output_directory_path: Directory to save the scaled ruler
        custom_ruler_size_cm: Optional, custom size of the ruler in cm (for SVG rulers)
        museum_selection: Museum selection to determine ruler sizing

    Returns:
        The path to the scaled ruler file that was created
    """
    from stitch_config import MUSEUM_CONFIGS
    
    if pixels_per_centimeter_scale <= 1:
        raise ValueError(
            f"Invalid pixels_per_centimeter: {pixels_per_centimeter_scale}")
    if not os.path.exists(chosen_digital_ruler_template_path):
        raise FileNotFoundError(
            f"Chosen digital ruler template file not found: {chosen_digital_ruler_template_path}")
    if not os.path.isdir(output_directory_path):
        raise NotADirectoryError(
            f"Output directory not found or is not a directory: {output_directory_path}")

    if custom_ruler_size_cm is not None:
        target_physical_width_cm = custom_ruler_size_cm
    else:
        template_filename = os.path.basename(chosen_digital_ruler_template_path)
        target_physical_width_cm = None
        
        if museum_selection == "General (black background)":
            ruler_constants = RULER_TARGET_PHYSICAL_WIDTHS_CM_JENA
        else:
            ruler_constants = RULER_TARGET_PHYSICAL_WIDTHS_CM_BRITISH_MUSEUM
            
        for key_cm_str, width_val_cm in ruler_constants.items():
            if key_cm_str in template_filename.lower():
                target_physical_width_cm = width_val_cm
                break
                    
        if target_physical_width_cm is None:
            raise ValueError(
                f"Could not determine target cm size from chosen digital template: {template_filename}")

    target_pixel_width = int(
        round(pixels_per_centimeter_scale * target_physical_width_cm))
    if target_pixel_width <= 0:
        raise ValueError(
            f"Calculated target pixel width ({target_pixel_width}) for digital ruler is invalid.")

    if chosen_digital_ruler_template_path.lower().endswith('.svg'):
        digital_ruler_image_array = svg_to_image(chosen_digital_ruler_template_path)
    else:
        digital_ruler_image_array = cv2.imread(
            chosen_digital_ruler_template_path, cv2.IMREAD_UNCHANGED)

    if digital_ruler_image_array is None:
        raise ValueError(
            f"Could not load digital ruler template image from: {chosen_digital_ruler_template_path}")

    current_h_px, current_w_px = digital_ruler_image_array.shape[:2]
    if current_w_px <= 0 or current_h_px <= 0:
        raise ValueError(
            f"Invalid dimensions for digital ruler template: {current_w_px}x{current_h_px}")

    aspect_ratio_val = current_h_px / current_w_px if current_w_px > 0 else 0
    target_pixel_height = int(
        round(target_pixel_width * aspect_ratio_val)) if aspect_ratio_val > 0 else 0

    if target_pixel_width > 0 and target_pixel_height <= 0:
        target_pixel_height = 1
    if target_pixel_width <= 0 or target_pixel_height <= 0:
        raise ValueError(
            f"Final calculated target digital ruler dimensions invalid: {target_pixel_width}x{target_pixel_height}")

    resized_digital_ruler_img_array = cv2.resize(
        digital_ruler_image_array,
        (target_pixel_width, target_pixel_height),
        interpolation=IMAGE_RESIZE_INTERPOLATION_METHOD
    )

    output_ruler_filename = f"{output_base_name}{SCALED_RULER_FILE_SUFFIX}"
    output_ruler_filepath = os.path.join(
        output_directory_path, output_ruler_filename)

    try:
        if not cv2.imwrite(output_ruler_filepath, resized_digital_ruler_img_array):
            raise IOError("cv2.imwrite failed for resized digital ruler.")
        print(
            f"    Successfully saved scaled digital ruler: {output_ruler_filepath}")
        return output_ruler_filepath
    except Exception as e:
        raise IOError(
            f"Error saving resized digital ruler to {output_ruler_filepath}: {e}")
