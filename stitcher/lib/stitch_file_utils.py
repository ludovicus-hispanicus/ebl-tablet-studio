import os
import cv2
import re
try:
    from image_utils import convert_to_bgr_if_needed
except ImportError:
    print("FATAL ERROR: stitch_file_utils.py cannot import from image_utils.py")
    def convert_to_bgr_if_needed(img): return img
from stitch_config import (
    OBJECT_FILE_SUFFIX,
    SCALED_RULER_FILE_SUFFIX,
    INTERMEDIATE_SUFFIX_FOR_OBJECTS,
    get_extended_intermediate_suffixes
)


def find_processed_image_file(subfolder_path, base_name, view_specific_part, general_suffix):
    target_filename = f"{base_name}{view_specific_part}{general_suffix}"
    path = os.path.join(subfolder_path, target_filename)
    if os.path.exists(path):
        return path
    if view_specific_part.startswith("_0") and len(view_specific_part) == 3:
        alt_part = "_" + view_specific_part[2]
        alt_filename = f"{base_name}{alt_part}{general_suffix}"
        alt_path = os.path.join(subfolder_path, alt_filename)
        if os.path.exists(alt_path):
            return alt_path
    # Fallback: folder name may differ from file base name (e.g., folder "Si 6" but files "Si.6_01...")
    # Try to find a file matching the view pattern with any base name
    if view_specific_part and os.path.isdir(subfolder_path):
        suffix_to_match = f"{view_specific_part}{general_suffix}".lower()
        for f in os.listdir(subfolder_path):
            if f.lower().endswith(suffix_to_match):
                return os.path.join(subfolder_path, f)
    return None


def find_image_paths_for_stitching(subfolder_path, image_base_name, view_patterns, include_intermediates=True, intermediate_suffix_patterns=None):
    """
    Find all image file paths for stitching without loading pixel data.
    Returns dict of view_key -> file_path.
    """
    image_paths = {}

    for view_key, pattern_part in view_patterns.items():
        if view_key == "ruler":
            fp = find_processed_image_file(
                subfolder_path, image_base_name, "", SCALED_RULER_FILE_SUFFIX)
        else:
            fp = find_processed_image_file(
                subfolder_path, image_base_name, pattern_part, OBJECT_FILE_SUFFIX)

        if fp:
            print(f"      Stitch - Found {view_key}: {os.path.basename(fp)}")
            image_paths[view_key] = fp

    if include_intermediates:
        suffix_patterns_to_use = intermediate_suffix_patterns or get_extended_intermediate_suffixes()
        # Detect intermediates but only get paths, not loaded images
        extended_suffixes = get_extended_intermediate_suffixes()
        all_files = os.listdir(subfolder_path)
        normalized = image_base_name.replace(' ', '.')

        for file_name in all_files:
            if not file_name.endswith(OBJECT_FILE_SUFFIX):
                continue
            if not file_name.startswith(image_base_name) and not file_name.startswith(normalized):
                continue
            match = re.search(r'_([a-z]{2}\d*|\d{2})_', file_name.lower())
            if not match:
                continue
            suffix_code = match.group(1)
            if suffix_code in extended_suffixes:
                position = extended_suffixes[suffix_code]
                fp = os.path.join(subfolder_path, file_name)
                if position not in image_paths:
                    image_paths[position] = fp
                    print(f"      Stitch - Found {position}: {file_name}")

    return image_paths


def load_image_dimensions(image_paths):
    """
    Load only dimensions of images (not pixel data) for layout calculation.
    Returns dict of view_key -> numpy array (loaded into memory).
    This is the same as full loading but kept for compatibility.
    For true lazy loading, use load_single_image().
    """
    loaded = {}
    for view_key, fp in image_paths.items():
        try:
            img = cv2.imread(fp, cv2.IMREAD_UNCHANGED)
            if img is not None:
                img = convert_to_bgr_if_needed(img)
                loaded[view_key] = img
        except Exception as e:
            print(f"      Error loading {view_key}: {e}")
    return loaded


def load_single_image(file_path):
    """Load a single image from disk. Used for lazy loading during canvas painting."""
    try:
        img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
        if img is not None:
            return convert_to_bgr_if_needed(img)
    except Exception as e:
        print(f"      Error loading {os.path.basename(file_path)}: {e}")
    return None


def load_images_for_stitching_process(subfolder_path, image_base_name, view_patterns, include_intermediates=True, intermediate_suffix_patterns=None):
    """
    Load all images needed for the stitching process.

    Args:
        subfolder_path: Path to the folder containing the images
        image_base_name: Base name of the tablet images
        view_patterns: Dictionary mapping view names to file patterns
        include_intermediates: Whether to include intermediate images
        intermediate_suffix_patterns: Dictionary mapping suffix codes to position names

    Returns:
        Dictionary of loaded images for each view
    """
    loaded_image_arrays = {}

    for view_key, pattern_part in view_patterns.items():
        if view_key == "ruler":
            fp = find_processed_image_file(
                subfolder_path, image_base_name, "", SCALED_RULER_FILE_SUFFIX)
        else:
            fp = find_processed_image_file(
                subfolder_path, image_base_name, pattern_part, OBJECT_FILE_SUFFIX)

        if fp:
            try:
                img_array = cv2.imread(fp, cv2.IMREAD_UNCHANGED)
                if img_array is None:
                    print(f"      Warn: Stitch - Failed to load {view_key} from {fp}")
                    continue

                img_array = convert_to_bgr_if_needed(img_array)
                print(f"      Stitch - Loaded {view_key} from {os.path.basename(fp)}")
                loaded_image_arrays[view_key] = img_array
            except Exception as e:
                print(f"      Error loading {view_key}: {e}")

    if include_intermediates:

        suffix_patterns_to_use = intermediate_suffix_patterns
        if not suffix_patterns_to_use:
            suffix_patterns_to_use = get_extended_intermediate_suffixes()

        intermediate_images = detect_intermediate_images(
            subfolder_path,
            image_base_name,
            suffix_patterns_to_use,
            INTERMEDIATE_SUFFIX_FOR_OBJECTS
        )

        loaded_image_arrays.update(intermediate_images)

    return loaded_image_arrays


def detect_intermediate_images(subfolder_path, base_name, intermediate_suffix_base, intermediate_suffix_for_objects):
    """
    Automatically detect images with intermediate position suffixes.

    Args:
        subfolder_path: Path to the folder containing the images
        base_name: Base name of the images
        intermediate_suffix_base: Dictionary mapping suffix codes to position names
        intermediate_suffix_for_objects: Dictionary mapping suffix codes to object file patterns

    Returns:
        Dictionary mapping positions to file paths
    """
    detected_images = {}
    all_files = os.listdir(subfolder_path)

    extended_suffixes = get_extended_intermediate_suffixes()

    for file_name in all_files:
        if not file_name.endswith(OBJECT_FILE_SUFFIX):
            continue
        # Match files that start with the base_name, or with a variant
        # (e.g., folder "Si 10" but files named "Si.10_...")
        if not file_name.startswith(base_name):
            # Check if file matches a normalized form of the base name
            # e.g., "Si 10" -> also accept "Si.10"
            normalized = base_name.replace(' ', '.')
            if not file_name.startswith(normalized):
                continue
        match = re.search(r'_([a-z]{2}\d*|\d{2})_', file_name.lower())
        if not match:
            continue

        suffix_code = match.group(1)
        if suffix_code in extended_suffixes:
            position = extended_suffixes[suffix_code]
            file_path = os.path.join(subfolder_path, file_name)

            if position in detected_images:

                if len(suffix_code) > 2:
                    variant_num = int(suffix_code[2:])

                    indexed_position = f"{position}_{variant_num}"
                    detected_images[indexed_position] = file_path
                    print(
                        f"      Detected additional intermediate image: {indexed_position} from {file_name}")
            else:
                detected_images[position] = file_path
                print(
                    f"      Detected processed intermediate image: {position} from {file_name}")

    loaded_intermediates = {}
    for position, file_path in detected_images.items():
        try:
            if not os.path.exists(file_path):
                print(f"      Warn: {position} file not found: {file_path}")
                continue

            img_array = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if img_array is None:
                print(f"      Warn: Failed to load {position} from {file_path}")
                continue

            img_array = convert_to_bgr_if_needed(img_array)
            print(
                f"      Stitch - Loaded {position} from {os.path.basename(file_path)}")
            loaded_intermediates[position] = img_array
        except Exception as e:
            print(f"      Error loading {position}: {e}")

    return loaded_intermediates
