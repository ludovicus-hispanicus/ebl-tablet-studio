import os
import json
from datetime import datetime
from typing import Dict, List
try:
    import pandas as pd
except ImportError:
    pd = None


def calculate_deviation_percentage(reference_value: float, calculated_value: float) -> float:
    """
    Calculate percentage deviation between reference and calculated values.

    Args:
        reference_value: Value from database
        calculated_value: Value calculated from photograph

    Returns:
        Percentage deviation (calculated - reference) / reference * 100
    """
    if reference_value == 0:
        return float('inf') if calculated_value != 0 else 0.0

    return ((calculated_value - reference_value) / reference_value) * 100


def load_sippar_reference_data() -> Dict[str, Dict]:
    """
    Load BM reference measurements from assets/bm_measurements.json.
    (Historical name kept for backward compatibility.)

    Returns:
        Dictionary mapping object IDs to their reference measurements
    """
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bm_path = os.path.join(script_dir, "assets", "bm_measurements.json")

        if not os.path.exists(bm_path):
            # Try old name as fallback
            bm_path = os.path.join(script_dir, "assets", "sippar.json")
            if not os.path.exists(bm_path):
                print(f"Warning: bm_measurements.json not found at {script_dir}/assets/")
                return {}

        with open(bm_path, 'r', encoding='utf-8') as f:
            bm_list = json.load(f)

        bm_dict = {}
        for item in bm_list:
            if isinstance(item, dict) and "_id" in item:
                bm_dict[item["_id"]] = item

        print(f"Loaded {len(bm_dict)} reference measurements from {os.path.basename(bm_path)}")
        return bm_dict

    except Exception as e:
        print(f"Error loading BM measurements: {e}")
        import traceback
        traceback.print_exc()
        return {}


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


def create_comparison_excel(output_dir: str = None, photographer_name: str = None) -> bool:
    """
    Create Excel file with measurement comparisons for measurements that have reference data.

    Args:
        output_dir: Directory to save the Excel file
        photographer_name: Full photographer name from GUI

    Returns:
        True if Excel file was created successfully, False otherwise
    """
    try:
        if pd is None:
            print("Error: pandas is required for Excel export")
            print("Install with: pip install pandas openpyxl")
            return False

        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))

        calculated_measurements = load_existing_measurements(output_dir)

        if not calculated_measurements:
            print("No measurements found in calculated_measurements.json")
            return False

        sippar_data = load_sippar_reference_data()

        comparisons = []

        for measurement in calculated_measurements:
            object_id = measurement.get("_id")
            if not object_id:
                continue

            if object_id not in sippar_data:
                continue

            calc_width = measurement.get("width", {}).get("value", 0) if isinstance(
                measurement.get("width"), dict) else measurement.get("width", 0)
            calc_length = measurement.get("length", {}).get("value", 0) if isinstance(
                measurement.get("length"), dict) else measurement.get("length", 0)

            ref_data = sippar_data[object_id]
            ref_width = ref_data.get("width", 0)
            ref_length = ref_data.get("length", 0)

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

            comparisons.append(comparison_record)

        if not comparisons:
           return False

        today = datetime.now().strftime("%Y.%m.%d")

        if photographer_name:

            photographer_parts = photographer_name.strip().split()
            last_name = photographer_parts[-1] if photographer_parts else "Unknown"
        else:
            last_name = "Unknown"

        filename = f"measurement_comparison_{last_name}_{today}.xlsx"
        excel_path = os.path.join(output_dir, filename)

        df = pd.DataFrame(comparisons)
        df.to_excel(excel_path, index=False, sheet_name="Measurement Comparison")

        print(f"Excel comparison file created: {excel_path}")
        print(f"Exported {len(comparisons)} measurement comparisons with reference data")

        return True

    except ImportError:
        print("Error: pandas and openpyxl are required for Excel export")
        print("Install with: pip install pandas openpyxl")
        return False
    except Exception as e:
        print(f"Error creating Excel comparison file: {e}")
        return False


def finalize_measurements_with_comparison(output_dir: str = None, photographer_name: str = None) -> bool:
    """
    Finalize the measurements process by creating Excel output.
    Call this at the end of your processing workflow.

    Args:
        output_dir: Directory to save output files
        photographer_name: Full photographer name from GUI

    Returns:
        True if successful, False otherwise
    """
    try:

        excel_created = create_comparison_excel(output_dir, photographer_name)

        return True

    except Exception as e:
        print(f"Error finalizing measurements: {e}")
        return False
