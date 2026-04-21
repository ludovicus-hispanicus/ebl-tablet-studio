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
    Legacy stub. The old workflow loaded `assets/bm_measurements.json` — a
    bundled BM/Sippar ground-truth dataset — to generate a deviation report.
    That file was dropped in Phase B (see stitcher/README.md), and the
    deviation report now uses the user-supplied measurements file instead
    (threaded through `create_comparison_excel(reference_measurements=...)`).

    Kept as a no-op so the rarely-triggered fallback-comparison branch in
    `extract_measurements.add_measurement_record` stays callable.
    """
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


def create_comparison_excel(output_dir: str = None, photographer_name: str = None,
                            reference_measurements: Dict[str, Dict] = None) -> bool:
    """
    Create Excel file with measurement comparisons for measurements that have reference data.

    Args:
        output_dir: Directory to save the Excel file.
        photographer_name: Full photographer name from GUI.
        reference_measurements: Dict keyed by tablet ID, with `width` / `length`
            fields (in cm) from the user-supplied measurements file. When None
            or empty, the deviation report is skipped silently — nothing to
            compare against.

    Returns:
        True if Excel file was created successfully, False otherwise.
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

        reference = reference_measurements or {}
        if not reference:
            print("No reference measurements supplied; skipping deviation report.")
            return False

        comparisons = []

        for measurement in calculated_measurements:
            object_id = measurement.get("_id")
            if not object_id:
                continue

            if object_id not in reference:
                continue

            calc_width = measurement.get("width", {}).get("value", 0) if isinstance(
                measurement.get("width"), dict) else measurement.get("width", 0)
            calc_length = measurement.get("length", {}).get("value", 0) if isinstance(
                measurement.get("length"), dict) else measurement.get("length", 0)

            ref_data = reference[object_id]
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


def finalize_measurements_with_comparison(output_dir: str = None, photographer_name: str = None,
                                          reference_measurements: Dict[str, Dict] = None) -> bool:
    """
    Finalize the measurements process by creating the deviation Excel.

    Args:
        output_dir: Directory containing `calculated_measurements.json` and
            where the comparison .xlsx will be written.
        photographer_name: Full photographer name from GUI (used in filename).
        reference_measurements: Dict keyed by tablet ID with ground-truth
            `width` / `length` (cm). Typically the `measurements_dict` loaded
            from the user's `--measurements` file. When None / empty, the
            comparison is skipped silently.

    Returns:
        True if successful, False otherwise
    """
    try:
        create_comparison_excel(output_dir, photographer_name, reference_measurements)
        return True

    except Exception as e:
        print(f"Error finalizing measurements: {e}")
        return False
