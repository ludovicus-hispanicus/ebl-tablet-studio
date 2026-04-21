import cv2
import numpy as np
import json
import os
from typing import Optional, Tuple, Dict, Any, List

_fallback_comparisons = []


def calculate_object_measurements(object_image_path: str, pixels_per_cm: float,
                                  file_id: str, gap_pixels: int = 0) -> Optional[Dict[str, Any]]:
    """
    Calculate the width and height of an extracted object in centimeters.

    Args:
        object_image_path (str): Path to the _object.tif file
        pixels_per_cm (float): Conversion factor from pixels to centimeters
        file_id (str): The base filename without suffixes
        gap_pixels (int): Number of gap pixels added on sides during extraction

    Returns:
        Dict containing measurement data or None if failed
    """
    try:
        img = cv2.imread(object_image_path)
        if img is None:
            print(f"Error: Could not load object image at {object_image_path}")
            return None

        height, width, _ = img.shape

        actual_width_pixels = width - (2 * gap_pixels)
        actual_height_pixels = height - (2 * gap_pixels)

        width_cm = actual_width_pixels / pixels_per_cm
        height_cm = actual_height_pixels / pixels_per_cm

        measurement_record = {
            "_id": file_id,
            "width": {
                "value": round(width_cm, 2),
                "note": "(ca.)"
            },
            "length": {
                "value": round(height_cm, 2),
                "note": "(ca.)"
            },
            "pixels_per_cm": pixels_per_cm,
        }

        print(
            f"Calculated measurements for {file_id}: {width_cm:.2f}cm x {height_cm:.2f}cm")
        return measurement_record

    except Exception as e:
        print(f"Error calculating measurements for {file_id}: {e}")
        return None


def track_fallback_comparison(object_id: str, calculated_measurements: Dict,
                              reference_measurements: Dict, was_fallback: bool = True):
    """
    Track a comparison between calculated and reference measurements for fallback cases.

    Args:
        object_id: The object ID
        calculated_measurements: Measurements calculated from photograph
        reference_measurements: Reference measurements from sippar.json
        was_fallback: True if measurements were used as fallback (not primary)
    """
    global _fallback_comparisons

    if not was_fallback:
        return

    try:
        from extract_measurements_excel import calculate_deviation_percentage

        calc_width = calculated_measurements.get("width", {}).get("value", 0)
        calc_length = calculated_measurements.get("length", {}).get("value", 0)

        ref_width = reference_measurements.get("width", 0)
        ref_length = reference_measurements.get("length", 0)

        width_deviation = calculate_deviation_percentage(ref_width, calc_width)
        length_deviation = calculate_deviation_percentage(ref_length, calc_length)

        if width_deviation != float('inf') and length_deviation != float('inf'):
            global_deviation = (abs(width_deviation) + abs(length_deviation)) / 2
        else:
            global_deviation = float('inf')

        comparison_record = {
            'Object_id': object_id,
            'Width × Length (From database)': f"{ref_width} × {ref_length}",
            'Width × Length (Calculated from photograph)': f"{calc_width} × {calc_length}",
            'Width Deviation (%)': round(width_deviation, 2) if width_deviation != float('inf') else 'N/A',
            'Length Deviation (%)': round(length_deviation, 2) if length_deviation != float('inf') else 'N/A',
            'Global Deviation (%)': round(global_deviation, 2) if global_deviation != float('inf') else 'N/A'
        }

        _fallback_comparisons.append(comparison_record)
        print(
            f"Tracked fallback comparison for {object_id}: Global deviation {comparison_record['Global Deviation (%)']}%")

    except Exception as e:
        print(f"Error tracking fallback comparison for {object_id}: {e}")


def clear_fallback_comparisons():
    """Clear the global fallback comparisons list (useful for new processing runs)."""
    global _fallback_comparisons
    _fallback_comparisons = []
    print("Cleared fallback comparison tracking")


def save_measurements_to_json(measurements_list: list, output_dir: str = None) -> bool:
    """
    Save measurements list to calculated_measurements.json file.

    Args:
        measurements_list (list): List of measurement dictionaries
        output_dir (str): Directory to save the file (defaults to script directory)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))

        json_path = os.path.join(output_dir, "calculated_measurements.json")

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(measurements_list, f, indent=2, ensure_ascii=False)

        print(f"Measurements saved to: {json_path}")
        return True

    except Exception as e:
        print(f"Error saving measurements to JSON: {e}")
        return False


def load_existing_measurements(output_dir: str = None) -> list:
    """
    Load existing measurements from calculated_measurements.json if it exists.

    Args:
        output_dir (str): Directory containing the JSON file

    Returns:
        list: Existing measurements or empty list if file doesn't exist
    """
    try:
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))

        json_path = os.path.join(output_dir, "calculated_measurements.json")

        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return []

    except Exception as e:
        print(f"Error loading existing measurements: {e}")
        return []


def add_measurement_record(object_image_path: str, pixels_per_cm: float,
                           file_id: str, gap_pixels: int = 0, output_dir: str = None,
                           was_fallback_measurement: bool = False, 
                           known_width_cm: float = None) -> bool:
    """
    Calculate measurements for an object and add to the JSON file.
    If known_width_cm is provided, uses it instead of calculating width.

    Args:
        object_image_path (str): Path to the _object.tif file
        pixels_per_cm (float): Conversion factor from pixels to centimeters
        file_id (str): The base filename without suffixes
        gap_pixels (int): Number of gap pixels added during extraction
        output_dir (str): Directory to save the JSON file
        was_fallback_measurement (bool): True if measurements were used as fallback
        known_width_cm (float): Known width from Excel (if provided)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if known_width_cm is not None:
            # Use known width from Excel and calculate only length
            measurement_record = create_measurement_record_with_known_width(
                object_image_path, pixels_per_cm, file_id, known_width_cm, gap_pixels)
        else:
            # Calculate both width and length from pixels
            measurement_record = calculate_object_measurements(
                object_image_path, pixels_per_cm, file_id, gap_pixels)

        if measurement_record is None:
            return False

        if was_fallback_measurement:
            from extract_measurements_excel import load_sippar_reference_data
            
            sippar_data = load_sippar_reference_data()
            
            if file_id in sippar_data:
                track_fallback_comparison(
                    file_id, measurement_record, sippar_data[file_id], was_fallback=True)
            else:
                available_keys = list(sippar_data.keys())[:5]

        existing_measurements = load_existing_measurements(output_dir)

        existing_measurements = [m for m in existing_measurements if m.get("_id") != file_id]

        existing_measurements.append(measurement_record)

        return save_measurements_to_json(existing_measurements, output_dir)

    except Exception as e:
        print(f"Error adding measurement record for {file_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_measurement_record_with_known_width(object_image_path: str, pixels_per_cm: float,
                                               file_id: str, known_width_cm: float, 
                                               gap_pixels: int = 0) -> Optional[Dict[str, Any]]:
    """
    Create measurement record with known width (from Excel) and calculated length.

    Args:
        object_image_path (str): Path to the _object.tif file
        pixels_per_cm (float): Conversion factor from pixels to centimeters
        file_id (str): The base filename without suffixes
        known_width_cm (float): Known width from Excel file
        gap_pixels (int): Number of gap pixels added on sides during extraction

    Returns:
        Dict containing measurement data or None if failed
    """
    try:
        img = cv2.imread(object_image_path)
        if img is None:
            print(f"Error: Could not load object image at {object_image_path}")
            return None

        height, width, _ = img.shape

        actual_height_pixels = height - (2 * gap_pixels)
        height_cm = actual_height_pixels / pixels_per_cm

        measurement_record = {
            "_id": file_id,
            "width": {
                "value": round(known_width_cm, 2),
                "note": ""
            },
            "length": {
                "value": round(height_cm, 2),
                "note": "(ca.)"
            },
            "pixels_per_cm": pixels_per_cm,
        }

        print(f"Measurements for {file_id}: width={known_width_cm:.2f}cm (Excel), length={height_cm:.2f}cm (calculated)")
        return measurement_record

    except Exception as e:
        print(f"Error creating measurement record for {file_id}: {e}")
        return None


def get_scale_from_excel_measurement(image_path: str, subfolder_path: str, 
                                   measurements_dict: dict, file_id: str,
                                   background_color_tolerance: int = 20) -> tuple:
    """
    Get scale from Excel measurements WITHOUT extracting objects during scale detection.
    This function only validates that a measurement exists and returns a placeholder scale.
    The actual pixels_per_cm calculation happens after main object extraction.

    Args:
        image_path: Path to the ruler/first image (not used for calculation)
        subfolder_path: Path to the subfolder (for ID extraction)
        measurements_dict: Dictionary of Excel measurements
        file_id: The tablet ID
        background_color_tolerance: Background tolerance (not used)

    Returns:
        tuple: (placeholder_scale, measurements_used) or (None, False) if failed
    """
    try:
        from measurements_utils import get_tablet_width_from_measurements
        
        # Get Excel width measurement to validate it exists
        tablet_width_cm = get_tablet_width_from_measurements(subfolder_path, measurements_dict)
        if tablet_width_cm is None or tablet_width_cm <= 0:
            return None, False

        print(f"   Found Excel measurement for {file_id}: {tablet_width_cm} cm")
        print(f"   Scale calculation deferred to after object extraction")
        print(f"   Returning placeholder scale: 100.0 px/cm")
        
        # Return a placeholder scale that will be recalculated later
        # Using a reasonable default that will be overridden
        placeholder_scale = 100.0  # pixels per cm placeholder
        
        return placeholder_scale, True

    except Exception as e:
        print(f"   Error validating Excel measurement: {e}")
        return None, False


def calculate_scale_from_measurement_and_object(object_image_path: str, tablet_width_cm: float,
                                               gap_pixels: int = 50) -> float:
    """
    Calculate pixels per cm from extracted object and known measurement.
    This function calculates the actual scale using the final extracted object.

    Args:
        object_image_path: Path to the final _object.tif file
        tablet_width_cm: Known width from Excel or Sippar.json
        gap_pixels: Gap pixels added during extraction

    Returns:
        float: Calculated pixels per cm
    """
    try:
        import cv2
        
        img = cv2.imread(object_image_path)
        if img is None:
            raise ValueError(f"Could not load object image: {object_image_path}")

        height, width, _ = img.shape
        actual_width_pixels = width - (2 * gap_pixels)
        
        pixels_per_cm = actual_width_pixels / tablet_width_cm
        
        print(f"   Calculated scale from extracted object: {actual_width_pixels}px / {tablet_width_cm}cm = {pixels_per_cm:.2f} px/cm")
        return pixels_per_cm

    except Exception as e:
        print(f"   Error calculating scale from object: {e}")
        raise


def create_measurement_record_from_excel(object_image_path: str, pixels_per_cm: float,
                                       file_id: str, measurements_dict: dict, 
                                       subfolder_path: str, gap_pixels: int = 50) -> bool:
    """
    Create measurement record from Excel measurements using the final extracted object.
    This function is called AFTER main object extraction to ensure measurements
    are calculated on the correct final object file.

    Args:
        object_image_path: Path to the final _object.tif file from main workflow
        pixels_per_cm: Pixels per cm calculated during scale detection
        file_id: The tablet ID
        measurements_dict: Dictionary of Excel measurements
        subfolder_path: Path to the subfolder
        gap_pixels: Number of gap pixels added during extraction

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from measurements_utils import get_tablet_width_from_measurements

        # Write records to the MAIN folder (parent of the tablet subfolder) so
        # that finalize_measurements_with_comparison can find them. The existence
        # check targets the same location — per-subfolder JSONs from older runs
        # are intentionally ignored.
        main_dir = os.path.dirname(subfolder_path)

        if measurement_record_exists(file_id, main_dir):
            print(f"   Measurement record already exists for {file_id}, skipping creation")
            return True

        # Get Excel width measurement
        tablet_width_cm = get_tablet_width_from_measurements(subfolder_path, measurements_dict)
        if tablet_width_cm is None or tablet_width_cm <= 0:
            print(f"   Warning: Could not get Excel width measurement for {file_id}")
            return False

        # Create measurement record with Excel width and calculated length
        measurement_record = create_measurement_record_with_known_width(
            object_image_path, pixels_per_cm, file_id, tablet_width_cm, gap_pixels
        )

        if measurement_record:
            existing_measurements = load_existing_measurements(main_dir)
            existing_measurements = [m for m in existing_measurements if m.get("_id") != file_id]
            existing_measurements.append(measurement_record)
            save_measurements_to_json(existing_measurements, main_dir)
            print(f"   ✓ Excel measurement record created for {file_id} using final extracted object")
            return True
        else:
            print(f"   Error: Could not create measurement record for {file_id}")
            return False

    except Exception as e:
        print(f"   Error creating Excel measurement record for {file_id}: {e}")
        return False


def get_scale_from_excel_and_create_measurement(image_path: str, subfolder_path: str, 
                                              measurements_dict: dict, file_id: str,
                                              background_color_tolerance: int = 20) -> tuple:
    """
    DEPRECATED: Get scale from Excel measurements and create measurement record.
    
    This function is deprecated and should not be used. It creates measurement records
    during scale detection which uses temporary object extractions, not the final ones.
    
    Use get_scale_from_excel_measurement() for scale detection and 
    create_measurement_record_from_excel() after main object extraction instead.

    Args:
        image_path: Path to the ruler/first image
        subfolder_path: Path to the subfolder (for ID extraction)
        measurements_dict: Dictionary of Excel measurements
        file_id: The tablet ID
        background_color_tolerance: Background tolerance for object extraction

    Returns:
        tuple: (pixels_per_cm, measurements_used) or (None, False) if failed
    """
    print(f"   WARNING: Using deprecated get_scale_from_excel_and_create_measurement()")
    print(f"   This creates measurement records at wrong time - use new split functions instead")
    
    try:
        from measurements_utils import get_tablet_width_from_measurements
        from workflow_processing_steps import determine_pixels_per_cm_from_measurement
        
        # Get Excel width measurement
        tablet_width_cm = get_tablet_width_from_measurements(subfolder_path, measurements_dict)
        if tablet_width_cm is None or tablet_width_cm <= 0:
            return None, False

        print(f"   Found Excel measurement for {file_id}: {tablet_width_cm} cm")

        # Calculate pixels_per_cm using existing function (extracts object first)
        pixels_per_cm = determine_pixels_per_cm_from_measurement(
            image_path,
            tablet_width_cm,
            should_extract_object=True,
            bg_color_tolerance=background_color_tolerance
        )

        # Find the extracted object file to create measurement record
        object_files = [f for f in os.listdir(subfolder_path) if f.endswith('_object.tif')]
        if object_files:
            object_path = os.path.join(subfolder_path, object_files[0])
            
            # Create measurement record with Excel width and calculated length
            measurement_record = create_measurement_record_with_known_width(
                object_path, pixels_per_cm, file_id, tablet_width_cm, gap_pixels=50
            )
            
            if measurement_record:
                # Save the measurement record
                existing_measurements = load_existing_measurements(subfolder_path)
                existing_measurements = [m for m in existing_measurements if m.get("_id") != file_id]
                existing_measurements.append(measurement_record)
                save_measurements_to_json(existing_measurements, subfolder_path)
                print(f"   ✓ Excel measurement workflow complete for {file_id}")

        print(f"   Using Excel measurement: {tablet_width_cm} cm, calculated {pixels_per_cm:.2f} px/cm")
        return pixels_per_cm, True

    except Exception as e:
        print(f"   Error using Excel measurement: {e}")
        return None, False


def get_measurement_record(file_id: str, output_dir: str = None) -> dict:
    """Get the measurement record for a tablet, or None if not found."""
    try:
        existing = load_existing_measurements(output_dir)
        for m in existing:
            if m.get("_id") == file_id or m.get("object_id") == file_id:
                return m
    except Exception:
        pass
    return None


def measurement_record_exists(file_id: str, output_dir: str = None) -> bool:
    """
    Check if a measurement record already exists for the given file_id.

    Args:
        file_id (str): The tablet ID to check
        output_dir (str): Directory containing the JSON file

    Returns:
        bool: True if measurement record exists, False otherwise
    """
    try:
        existing_measurements = load_existing_measurements(output_dir)
        return any(m.get("_id") == file_id for m in existing_measurements)
    except Exception:
        return False
