"""
Converts mislabeled image files (HEIC, CR3, etc.) that have .jpg/.jpeg extensions
to actual JPEG format. Preserves original raw files in a _Raw/ archive folder.

Common cases:
- iPhone photos downloaded from cloud services (HEIC -> .jpg)
- Canon raw files renamed as .jpg (CR3 -> .jpg)
"""

import os
import shutil

RAW_ARCHIVE_FOLDER = "_Raw"


def detect_true_format(file_path):
    """
    Detect the true format of a file by reading its header.
    Returns 'jpeg', 'heic', 'cr3', or 'unknown'.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

        if len(header) < 8:
            return 'unknown'

        # JPEG: starts with FF D8
        if header[:2] == b'\xff\xd8':
            return 'jpeg'

        # ISO BMFF container (HEIC, CR3, etc.): bytes 4-8 = 'ftyp'
        if header[4:8] == b'ftyp':
            brand = header[8:12]
            if brand == b'crx ':
                return 'cr3'
            elif brand in (b'heic', b'heix', b'mif1', b'hevc'):
                return 'heic'
            return 'heic'  # treat other ftyp as HEIC

        return 'unknown'
    except (IOError, OSError):
        return 'unknown'


def _get_raw_archive_path(file_path):
    """
    Get the archive path for a raw file.
    E.g., /root/Si.10/file.jpg -> /root/_Raw/Si.10/file.jpg
    """
    folder = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    subfolder_name = os.path.basename(folder)
    root_folder = os.path.dirname(folder)

    archive_dir = os.path.join(root_folder, RAW_ARCHIVE_FOLDER, subfolder_name)
    return os.path.join(archive_dir, filename)


def _preserve_raw(file_path):
    """
    Copy the original raw file to _Raw/ archive before conversion.
    Returns True if preserved (or already archived), False on error.
    """
    archive_path = _get_raw_archive_path(file_path)

    # Skip if already archived
    if os.path.exists(archive_path):
        return True

    try:
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        shutil.copy2(file_path, archive_path)
        return True
    except OSError as e:
        print(f"  Warning: Could not archive raw file {os.path.basename(file_path)}: {e}")
        return False


def convert_cr3_to_jpeg(file_path, preserve_raw=True):
    """Convert a CR3 raw file to JPEG, optionally preserving the original."""
    try:
        import rawpy
        from PIL import Image

        if preserve_raw:
            _preserve_raw(file_path)

        raw = rawpy.imread(file_path)
        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False)
        raw.close()

        img = Image.fromarray(rgb)
        img.save(file_path, 'JPEG', quality=95, subsampling=0)
        return True
    except ImportError:
        print("  Warning: rawpy not installed. Cannot convert CR3 files.")
        return False
    except Exception as e:
        print(f"  Error converting CR3 {os.path.basename(file_path)}: {e}")
        return False


def convert_heic_to_jpeg(file_path, preserve_raw=True):
    """Convert a HEIC file to JPEG, optionally preserving the original."""
    try:
        from pillow_heif import register_heif_opener
        from PIL import Image

        if preserve_raw:
            _preserve_raw(file_path)

        register_heif_opener()

        img = Image.open(file_path)
        exif_data = img.info.get('exif', None)

        if img.mode != 'RGB':
            img = img.convert('RGB')

        save_kwargs = {'quality': 95, 'subsampling': 0}
        if exif_data:
            save_kwargs['exif'] = exif_data

        img.save(file_path, 'JPEG', **save_kwargs)
        return True
    except ImportError:
        print("  Warning: pillow-heif not installed. Cannot convert HEIC files.")
        return False
    except Exception as e:
        print(f"  Error converting HEIC {os.path.basename(file_path)}: {e}")
        return False


def convert_mislabeled_images_in_folder(folder_path):
    """
    Scan a folder for mislabeled image files and convert them to JPEG.
    Preserves originals in _Raw/ archive.
    Returns the number of files converted.
    """
    converted = 0
    jpg_extensions = ('.jpg', '.jpeg')

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(jpg_extensions):
            continue

        file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(file_path):
            continue

        true_format = detect_true_format(file_path)

        if true_format == 'cr3':
            print(f"   Converting CR3->JPEG: {filename}")
            if convert_cr3_to_jpeg(file_path):
                converted += 1
        elif true_format == 'heic':
            print(f"   Converting HEIC->JPEG: {filename}")
            if convert_heic_to_jpeg(file_path):
                converted += 1

    return converted


def convert_heic_files_recursive(base_folder):
    """
    Scan all subfolders for mislabeled image files and convert them.
    Preserves originals in _Raw/ archive. Skips _Raw/ and other _ prefixed folders.
    Returns total number of files converted.
    """
    total_converted = 0

    for root, dirs, files in os.walk(base_folder):
        # Skip _ prefixed directories
        dirs[:] = [d for d in dirs if not d.startswith('_')]

        count = convert_mislabeled_images_in_folder(root)
        if count > 0:
            folder_name = os.path.basename(root)
            print(f"   Converted {count} file(s) to JPEG in {folder_name}")
            total_converted += count

    if total_converted > 0:
        raw_path = os.path.join(base_folder, RAW_ARCHIVE_FOLDER)
        print(f"   Raw originals preserved in: {raw_path}")

    return total_converted
