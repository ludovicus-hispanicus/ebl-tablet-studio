import json
import os
import re
from typing import List, Dict, Optional, Tuple, Union


def organize_project_subfolders(source_folder_path: str, image_extensions: tuple, organize_files_func) -> List[str]:
    """
    Checks for existing subfolders or organizes images into subfolders.
    Returns a list of paths to processable subfolders.
    """
    print("Step 0: Checking for existing subfolders or organizing images...")
    processed_subfolders = []

    images_in_root = False
    if os.path.isdir(source_folder_path):
        for item in os.listdir(source_folder_path):
            if os.path.isfile(os.path.join(source_folder_path, item)) and item.lower().endswith(image_extensions):
                images_in_root = True
                break

    subfolders_with_images = []
    if os.path.isdir(source_folder_path):
        potential_subdirs = [d for d in os.listdir(
            source_folder_path) if os.path.isdir(os.path.join(source_folder_path, d))]
        for subdir_name in potential_subdirs:
            subdir_path = os.path.join(source_folder_path, subdir_name)
            has_images = False
            for item in os.listdir(subdir_path):
                if os.path.isfile(os.path.join(subdir_path, item)) and item.lower().endswith(image_extensions):
                    has_images = True
                    break
            if has_images:
                subfolders_with_images.append(subdir_path)

    if not images_in_root and subfolders_with_images:
        print(
            f"   No images in root, but found {len(subfolders_with_images)} subfolder(s) with images. Skipping file organization step.")
        processed_subfolders = subfolders_with_images
    else:
        if images_in_root:
            print("   Images found in root folder. Running file organization...")
        elif not subfolders_with_images:
            print(
                "   No images in root and no subfolders with images found. Running file organization...")

        try:
            organized_paths = organize_files_func(source_folder_path)
            processed_subfolders = [os.path.join(source_folder_path, p) if not os.path.isabs(
                p) else p for p in organized_paths]

            if not processed_subfolders and images_in_root:
                print(
                    "   Organize_files returned no subfolders, but source folder contains images. Treating source as a single set.")
                processed_subfolders = [source_folder_path]
            elif not processed_subfolders and not images_in_root and not subfolders_with_images:
                print("   No image sets found after attempting organization.")
        except Exception as e:
            print(f"   ERROR during file organization: {e}")

            raise

    return processed_subfolders


def determine_ruler_image_for_scaling(
    custom_layout_config: Optional[Dict],
    orig_views_fps: dict,
    image_files_for_layout: List,
    pr02_reverse: Optional[str],
    pr03_top: Optional[str],
    pr04_bottom: Optional[str],
    rel_count: int
) -> Optional[str]:
    """Determines the file path of the image to be used for ruler scale detection."""
    ruler_for_scale_fp = None
    if custom_layout_config:
        if custom_layout_config.get("obverse"):
            ruler_for_scale_fp = custom_layout_config["obverse"]
        elif custom_layout_config.get("reverse"):
            ruler_for_scale_fp = custom_layout_config["reverse"]
        elif custom_layout_config.get("bottom"):
            ruler_for_scale_fp = custom_layout_config["bottom"]

        if not ruler_for_scale_fp:
            for view_designation, path_or_list in custom_layout_config.items():
                if isinstance(path_or_list, str) and os.path.exists(path_or_list):
                    ruler_for_scale_fp = path_or_list
                    print(
                        f"   INFO: Using '{view_designation}' image from custom layout as ruler image (first available).")
                    break
                elif isinstance(path_or_list, list):
                    for item_path in path_or_list:
                        if os.path.exists(item_path):
                            ruler_for_scale_fp = item_path
                            print(
                                f"   INFO: Using first image from '{view_designation}' list in custom layout as ruler image.")
                            break
                if ruler_for_scale_fp:
                    break

        if not ruler_for_scale_fp and image_files_for_layout:
            ruler_for_scale_fp = image_files_for_layout[0]
            print(
                f"   WARNING: No specific ruler image identifiable from custom layout. Using first available image: {os.path.basename(ruler_for_scale_fp)} for scaling. This may be incorrect.")

    if not ruler_for_scale_fp:
        if rel_count == 2 and pr02_reverse:
            ruler_for_scale_fp = pr02_reverse
        elif rel_count >= 6 and pr03_top:
            ruler_for_scale_fp = pr03_top
        elif pr02_reverse:
            ruler_for_scale_fp = pr02_reverse
        elif pr03_top:
            ruler_for_scale_fp = pr03_top
        elif pr04_bottom:
            ruler_for_scale_fp = pr04_bottom
        elif orig_views_fps:
            ruler_for_scale_fp = (
                orig_views_fps.get("obverse")
                or orig_views_fps.get("reverse")
                or orig_views_fps.get("top")
                or orig_views_fps.get("bottom")
                or next(iter(orig_views_fps.values()), None)
            )

        if not ruler_for_scale_fp and image_files_for_layout:
            ruler_for_scale_fp = image_files_for_layout[0]
            print(
                f"   WARNING: Could not determine ruler image by standard patterns. Using first image found: {os.path.basename(ruler_for_scale_fp)} for scaling. This may be incorrect.")

    return ruler_for_scale_fp


def determine_pixels_per_cm_from_measurement(
    image_path: str,
    tablet_width_cm: float,
    should_extract_object: bool = True,
    bg_color_tolerance: int = 20
) -> float:
    """
    Calculate pixels per cm based on a known width measurement.

    Args:
        image_path: Path to the image
        tablet_width_cm: Known width of the tablet in cm
        should_extract_object: Whether to extract the object first (default: True)
        bg_color_tolerance: Background color tolerance for extraction

    Returns:
        Pixels per cm value
    """
    import cv2
    from remove_background import (
        detect_dominant_corner_background_color,
        create_foreground_mask_from_background,
        select_contour_closest_to_image_center
    )

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    img_height, img_width = img.shape[:2]

    if should_extract_object:
        print(
            f"   Extracting object for measurement calculation from {os.path.basename(image_path)}")

        bg_color = detect_dominant_corner_background_color(img)

        fg_mask = create_foreground_mask_from_background(
            img, bg_color, bg_color_tolerance)

        main_contour = select_contour_closest_to_image_center(
            img, fg_mask, min_contour_area_as_image_fraction=0.001
        )

        if main_contour is None:
            print(
                f"   Warning: Could not detect main object in {os.path.basename(image_path)}")
            print(
                f"   Using full image width instead: {img_width}px / {tablet_width_cm}cm")
            return img_width / tablet_width_cm

        x, y, w, h = cv2.boundingRect(main_contour)

        obj_width_px = w
        print(
            f"   Extracted object width: {obj_width_px}px (full image: {img_width}px)")

        pixels_per_cm = obj_width_px / tablet_width_cm
    else:

        pixels_per_cm = img_width / tablet_width_cm

    print(
        f"   Calculated from measurement: {obj_width_px if should_extract_object else img_width}px / {tablet_width_cm}cm = {pixels_per_cm:.2f} px/cm")
    return pixels_per_cm
