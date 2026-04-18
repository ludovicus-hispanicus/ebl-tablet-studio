import os
from hdr_processor import HDR_SUFFIX
from stitch_config import SCALED_RULER_FILE_SUFFIX
import shutil


def cleanup_intermediate_files(processed_subfolders, object_artifact_suffix, ruler_suffix=SCALED_RULER_FILE_SUFFIX):
    """
    Clean up intermediate files: move _object.tif files to _cleaned/ subfolder,
    remove ruler and temp files.

    The _object.tif files (background-removed by rembg) are saved in a _cleaned/
    subfolder so originals stay untouched in the tablet folder. The renamer app
    won't see _cleaned/ because it skips subfolders inside tablet folders.
    """
    print("\n--- Cleaning up intermediate files ---")
    total_removed = 0
    total_cleaned = 0

    for subfolder_path in processed_subfolders:
        folder_name = os.path.basename(subfolder_path)

        try:
            cleaned_dir = os.path.join(subfolder_path, "_cleaned")

            # First pass: move _object.tif files to _cleaned/
            for filename in os.listdir(subfolder_path):
                if not filename.endswith(object_artifact_suffix):
                    continue

                object_path = os.path.join(subfolder_path, filename)
                if not os.path.isfile(object_path):
                    continue

                # Create _cleaned/ on first use
                if not os.path.exists(cleaned_dir):
                    os.makedirs(cleaned_dir)

                # "Si.1_01_object.tif" -> "Si.1_01.tif"
                clean_name = filename[:-len(object_artifact_suffix)] + '.tif'
                clean_path = os.path.join(cleaned_dir, clean_name)

                try:
                    shutil.move(object_path, clean_path)
                    total_cleaned += 1
                except Exception as e:
                    print(f"  Error moving {filename} to _cleaned/: {e}")

            # Second pass: remove ruler and temp files
            for filename in os.listdir(subfolder_path):
                file_path = os.path.join(subfolder_path, filename)
                if os.path.isfile(file_path) and (
                    filename.endswith(ruler_suffix)
                    or "temp_isolated_ruler" in filename
                    or "_rawscale.tif" in filename
                ):
                    try:
                        os.remove(file_path)
                        total_removed += 1
                    except Exception as e:
                        print(f"  Error removing {filename}: {e}")

        except Exception as e:
            print(f"  Error accessing folder {folder_name}: {e}")

    if processed_subfolders:
        main_folder = os.path.dirname(processed_subfolders[0])
        hdr_folders_removed = 0

        try:
            print(
                f"\n  Checking for HDR folders in main directory: {main_folder}")
            for item_name in os.listdir(main_folder):
                item_path = os.path.join(main_folder, item_name)
                if os.path.isdir(item_path) and item_name.endswith(HDR_SUFFIX):
                    try:
                        # Check for and preserve calculated_measurements.json before removing HDR folder
                        measurements_file = os.path.join(item_path, "calculated_measurements.json")
                        if os.path.exists(measurements_file):
                            # Extract base tablet ID (remove _HDR suffix)
                            base_tablet_id = item_name[:-len(HDR_SUFFIX)] if item_name.endswith(HDR_SUFFIX) else item_name
                            preserved_path = os.path.join(main_folder, f"{base_tablet_id}_measurements.json")
                            shutil.copy2(measurements_file, preserved_path)
                            print(f"    Preserved measurements: {base_tablet_id}_measurements.json")
                        
                        shutil.rmtree(item_path)
                        hdr_folders_removed += 1
                        total_removed += 1
                        print(f"    Removed HDR folder: {item_name}")
                    except Exception as e:
                        print(f"  Error removing HDR folder {item_name}: {e}")

            if hdr_folders_removed > 0:
                print(
                    f"  Removed {hdr_folders_removed} HDR folders from main directory")

        except Exception as e:
            print(f"  Error accessing main directory {main_folder}: {e}")

    if total_cleaned > 0:
        print(f"  Moved {total_cleaned} clean image(s) to _cleaned/ subfolders")
    print(f"--- Cleanup complete: {total_cleaned} moved to _cleaned/, {total_removed} files/folders removed ---")


def normalize_subfolder_names(processed_subfolders):
    """
    Normalize subfolder names by replacing spaces with dots.
    E.g., 'Si 10' -> 'Si.10'
    """
    import re
    renamed_count = 0

    for subfolder_path in processed_subfolders:
        folder_name = os.path.basename(subfolder_path)
        normalized = re.sub(r'(\w+)\s+(\d+)', r'\1.\2', folder_name)

        if normalized != folder_name:
            new_path = os.path.join(os.path.dirname(subfolder_path), normalized)
            if not os.path.exists(new_path):
                try:
                    os.rename(subfolder_path, new_path)
                    renamed_count += 1
                except OSError as e:
                    print(f"  Warning: Could not rename folder '{folder_name}' to '{normalized}': {e}")

    if renamed_count > 0:
        print(f"  Normalized {renamed_count} folder name(s) (spaces -> dots)")


def cleanup_temp_files(*file_paths):
    """
    Clean up temporary files if they exist.

    Args:
        *file_paths: Variable number of file paths to clean up
    """
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"    Removed temp file: {os.path.basename(file_path)}")
            except Exception as e:
                print(
                    f"  Warning: Could not remove temp file {file_path}: {e}")
