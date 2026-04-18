from stitch_config import STITCH_VIEW_PATTERNS_BASE, get_extended_intermediate_suffixes, MAX_ADDITIONAL_INTERMEDIATES
import os
import re
import shutil
import sys
from collections import defaultdict

script_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(script_directory)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)


def generate_subfoldering_pattern():
    """
    Generate regex pattern for filename matching based on config.
    """

    all_codes = get_extended_intermediate_suffixes()

    pattern = r"(.+)_(\d+|" + '|'.join(all_codes) + r")\.(.+)"

    return re.compile(pattern, re.IGNORECASE)


FILENAME_PATTERN_FOR_SUBFOLDERING = generate_subfoldering_pattern()


def group_and_move_files_to_subfolders(
    folder_path,
    filename_pattern=None,
    extensions=('.jpg', '.jpeg', '.tif', '.tiff', '.png', '.cr2', '.CR2'),
    recursive=False,
    dry_run=False
):
    """
    Group files in a folder based on their common prefix (ID) and move them into subfolders.

    Args:
        folder_path: Path to the folder containing files to organize
        filename_pattern: Optional regex pattern for filename matching (defaults to FILENAME_PATTERN_FOR_SUBFOLDERING)
        extensions: Tuple of file extensions to include
        recursive: Whether to process subfolders recursively
        dry_run: If True, only prints planned actions without moving files

    Returns:
        Dictionary mapping subfolder names to lists of moved files
    """

    if filename_pattern is None:
        filename_pattern = FILENAME_PATTERN_FOR_SUBFOLDERING

    if not os.path.isdir(folder_path):
        print(f"Error: Source directory '{folder_path}' not found.")
        return []

    files_grouped_by_base_name = defaultdict(list)
    matched_files_count = 0
    skipped_files_count = 0

    for item_name in os.listdir(folder_path):
        item_full_path = os.path.join(folder_path, item_name)
        if os.path.isfile(item_full_path):
            match_result = filename_pattern.match(item_name)
            if match_result:
                base_name_key = match_result.group(1)
                files_grouped_by_base_name[base_name_key].append(item_full_path)
                matched_files_count += 1
            else:
                skipped_files_count += 1

    if not files_grouped_by_base_name:
        print(f"No files in '{folder_path}' matched pattern for subfoldering.")
        return []

    processed_subfolder_paths = []
    for base_name_key, list_of_file_paths in files_grouped_by_base_name.items():
        target_subfolder_path = os.path.join(folder_path, base_name_key)
        try:
            os.makedirs(target_subfolder_path, exist_ok=True)

            for file_path_to_move in list_of_file_paths:
                current_file_name = os.path.basename(file_path_to_move)
                destination_file_path = os.path.join(
                    target_subfolder_path, current_file_name)
                if not (os.path.exists(destination_file_path)
                        and os.path.samefile(file_path_to_move, destination_file_path)):
                    shutil.move(file_path_to_move, destination_file_path)

            if target_subfolder_path not in processed_subfolder_paths:
                processed_subfolder_paths.append(target_subfolder_path)
        except OSError as os_err:
            print(f"OS Error processing subfolder '{target_subfolder_path}': {os_err}")
        except Exception as general_err:
            print(f"Unexpected error for base name '{base_name_key}': {general_err}")

    print(f"File organization: {len(processed_subfolder_paths)} subfolders processed.")
    print(f"  {matched_files_count} files matched pattern; {skipped_files_count} files skipped.")
    return processed_subfolder_paths
