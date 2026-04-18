import json
import os
import re

try:
    import pandas as pd
except ImportError:
    pd = None


def load_measurements_from_json(json_path):
    """
    Load measurements data from a JSON file.

    Args:
        json_path: Path to the JSON file containing measurements

    Returns:
        Dictionary mapping tablet IDs to their measurements, or empty dict if file not found
    """

    if not os.path.exists(json_path):
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        measurements_dict = {}
        for item in data:
            if "_id" in item and "width" in item:
                measurements_dict[item["_id"]] = item

        return measurements_dict
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from measurements file: {e}")
        return {}
    except Exception as e:
        print(f"Error loading measurements file: {e}")
        return {}


def extract_tablet_id_from_path(folder_path):
    """
    Extract tablet ID from folder path.

    Args:
        folder_path: Path to the tablet folder

    Returns:
        Extracted tablet ID or None if not found
    """

    folder_name = os.path.basename(folder_path)

    # Try to match common prefix + number formats (e.g., CBS.5256, BM 12345, Si 4, Si.4)
    known_prefixes = ['CBS', 'BM', 'VAM', 'IM', 'Si', 'K', 'Sm', 'Rm']
    for prefix in known_prefixes:
        match = re.search(rf'{prefix}[_\s\.]*(\d+)', folder_name, re.IGNORECASE)
        if match:
            return f"{prefix}.{match.group(1)}"

    # Finally, just try to extract any number
    number_match = re.search(r'(\d+)', folder_name)
    if number_match:
        return number_match.group(1)

    return None


def get_tablet_width_from_measurements(folder_path, measurements_dict):
    """
    Get tablet width from measurements based on folder path.

    Args:
        folder_path: Path to the tablet folder
        measurements_dict: Dictionary with measurements data

    Returns:
        Width in cm if found, None otherwise
    """
    tablet_id = extract_tablet_id_from_path(folder_path)
    if not tablet_id:
        return None

    # If we got a full ID (like CBS.5256), try it directly first
    if tablet_id in measurements_dict:
        width_cm = measurements_dict[tablet_id].get("width")
        if width_cm is not None and isinstance(width_cm, (int, float)) and width_cm > 0:
            print(f"Found width measurement for ID {tablet_id}: {width_cm} cm")
            return width_cm

    # Check for joined tablet entries (e.g., "Si.4 + Si.5" contains "Si.4")
    for key in measurements_dict.keys():
        if '+' in key:
            # Split joined key and check each part
            parts = [p.strip() for p in key.split('+')]
            for part in parts:
                # Also handle partial IDs like "Si.31/52" → matches "Si.31"
                part_base = part.split('/')[0].strip()
                if part == tablet_id or part_base == tablet_id:
                    width_cm = measurements_dict[key].get("width")
                    if width_cm is not None and isinstance(width_cm, (int, float)) and width_cm > 0:
                        print(f"Found width measurement for ID {tablet_id} in joined entry {key}: {width_cm} cm")
                        return width_cm

    # Extract just the numeric part for additional matching attempts
    numeric_part = re.search(r'(\d+)', tablet_id)
    if numeric_part:
        numeric_id = numeric_part.group(1)

        potential_ids = [numeric_id]  # Start with just the numeric ID

        pattern = rf'^([A-Z]+|[A-Z][a-z]+-[IV]+|[A-Z][a-z]+)[\.\s_]{re.escape(numeric_id)}$'

        for key in measurements_dict.keys():
            if re.match(pattern, key):
                potential_ids.append(key)

        common_prefixes = ['BM', 'CBS', 'VAM', 'IM', 'K', 'Sm', 'Rm', 'Si']
        separators = ['.', ' ', '_']

        for prefix in common_prefixes:
            for sep in separators:
                candidate_id = f"{prefix}{sep}{numeric_id}"
                if candidate_id not in potential_ids:
                    potential_ids.append(candidate_id)

        for id_format in potential_ids:
            if id_format in measurements_dict:
                width_cm = measurements_dict[id_format].get("width")
                if width_cm is not None and isinstance(width_cm, (int, float)) and width_cm > 0:
                    print(f"Found width measurement for ID {id_format}: {width_cm} cm")
                    return width_cm

    print(f"No width measurement found for tablet ID: {tablet_id}")
    return None


def is_valid_measurements_file(file_path):
    """
    Check if the given file is a valid measurements JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        True if valid, False otherwise
    """
    if not os.path.exists(file_path):
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            return False

        return "_id" in data[0] and "width" in data[0]
    except:
        return False


def load_measurements_from_excel(excel_path):
    """
    Load width measurements data from an Excel file.
    Expects _id in first column and width in second column.

    Args:
        excel_path: Path to the Excel file containing width measurements

    Returns:
        Dictionary mapping tablet IDs to their width measurements, or empty dict if file not found
    """
    if pd is None:
        print("Error: pandas is required for Excel file loading")
        print("Install with: pip install pandas openpyxl")
        return {}

    if not os.path.exists(excel_path):
        print(f"Excel file not found: {excel_path}")
        return {}

    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        if df.empty or len(df.columns) < 2:
            print("Error: Excel file must have at least 2 columns")
            return {}

        measurements_dict = {}
        
        for index, row in df.iterrows():
            try:
                tablet_id = str(row.iloc[0]).strip()
                width_value = float(row.iloc[1])
                
                if tablet_id and width_value > 0:
                    measurements_dict[tablet_id] = {
                        "_id": tablet_id,
                        "width": width_value
                    }
                    
            except (ValueError, TypeError):
                # Skip invalid rows
                continue

        print(f"Loaded {len(measurements_dict)} width measurements from Excel file")
        return measurements_dict

    except Exception as e:
        print(f"Error loading Excel measurements file: {e}")
        return {}


def is_valid_excel_measurements_file(file_path):
    """
    Check if the given Excel file is valid for measurements.

    Args:
        file_path: Path to the Excel file

    Returns:
        True if valid, False otherwise
    """
    if pd is None:
        return False
        
    if not os.path.exists(file_path):
        return False

    try:
        df = pd.read_excel(file_path)
        return not df.empty and len(df.columns) >= 2
    except:
        return False


def merge_measurements_dicts(dict1, dict2):
    """
    Merge two measurements dictionaries, with dict2 taking precedence.
    
    Args:
        dict1: First measurements dictionary
        dict2: Second measurements dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    merged = dict1.copy()
    
    for tablet_id, measurements in dict2.items():
        if tablet_id in merged:
            # Update existing entry with new measurements
            merged[tablet_id].update(measurements)
        else:
            # Add new entry
            merged[tablet_id] = measurements.copy()
    
    return merged
