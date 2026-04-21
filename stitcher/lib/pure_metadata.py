"""
Pure Python metadata handling module.
This module uses pyexiv2 or pyexiv2 to handle all types of metadata (EXIF, XMP, IPTC) when available.
"""

import os
import sys
import datetime
import piexif
import cv2
import shutil
import time

pyexiv2 = None
exiv2_module_name = None

try:
    import pyexiv2
    exiv2_module_name = "pyexiv2"
except ImportError:
    print("Warning: pyexiv2 not installed. Some metadata functionality will be limited.")
    print("To install: pip install pyexiv2")


def is_exiv2_available():
    """Check if any exiv2 module is available."""
    return pyexiv2 is not None


def set_basic_exif_metadata(image_path, image_title, photographer_name, institution_name, copyright_text, image_dpi):
    """
    Set basic EXIF metadata using piexif (fallback method).
    This is used when pyexiv2 is not available.
    Works with both TIFF and JPEG files.
    """
    try:

        if not os.path.exists(image_path):
            print(f"      Error: File not found: {image_path}")
            return False

        file_ext = os.path.splitext(image_path.lower())[1]
        if file_ext not in ['.tif', '.tiff', '.jpg', '.jpeg']:
            print(f"      Warning: Unsupported file format for piexif: {file_ext}")

        exif_dictionary = {"0th": {}, "Exif": {},
                           "GPS": {}, "1st": {}, "thumbnail": None}

        try:
            exif_dictionary["0th"][piexif.ImageIFD.Artist] = f"{photographer_name} ({institution_name})".encode(
                'utf-8')
            exif_dictionary["0th"][piexif.ImageIFD.Copyright] = copyright_text.encode(
                'utf-8')

            exif_dictionary["0th"][40095] = copyright_text.encode('utf-8')
            exif_dictionary["0th"][piexif.ImageIFD.ImageDescription] = copyright_text.encode(
                'utf-8')
            exif_dictionary["0th"][piexif.ImageIFD.Software] = "eBL Photo Stitcher".encode(
                'utf-8')
            exif_dictionary["0th"][piexif.ImageIFD.XResolution] = (image_dpi, 1)
            exif_dictionary["0th"][piexif.ImageIFD.YResolution] = (image_dpi, 1)
            exif_dictionary["0th"][piexif.ImageIFD.ResolutionUnit] = 2

            exif_dictionary["0th"][270] = image_title.encode('utf-8')

            exif_bytes = piexif.dump(exif_dictionary)

            try:
                piexif.insert(exif_bytes, image_path)
                print(
                    f"      EXIF metadata applied successfully to {os.path.basename(image_path)} via piexif.")
                return True
            except Exception as insert_err:

                if file_ext in ['.jpg', '.jpeg']:
                    print(f"      Alternative method for JPEG metadata...")

                    img = cv2.imread(image_path)
                    if img is not None:
                        temp_path = f"{image_path}.temp"
                        if cv2.imwrite(temp_path, img):
                            try:
                                piexif.insert(exif_bytes, temp_path)
                                os.remove(image_path)
                                os.rename(temp_path, image_path)
                                print(
                                    f"      EXIF metadata applied successfully via alternative method.")
                                return True
                            except Exception as alt_err:
                                print(f"      Error with alternative method: {alt_err}")
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                                return False
                raise insert_err

        except Exception as field_error:
            print(f"      Warn: Error setting specific EXIF field: {field_error}")
            return False
    except Exception as e:
        print(f"      Warn: piexif metadata error: {e}")
        return False


def apply_all_metadata(
    image_path,
    image_title,
    photographer_name,
    institution_name,
    credit_line_text,
    copyright_text,
    usage_terms_text=None,
    image_dpi=600,
    object_width_cm=None,
    object_length_cm=None,
    pixels_per_cm=None
):
    """
    Apply all metadata (EXIF, XMP, IPTC) using pyexiv2 when available.
    Falls back to piexif for basic EXIF if pyexiv2 is not available.
    Works with both TIFF and JPG files.

    Returns True if successful, False otherwise.
    """
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        return False

    file_ext = os.path.splitext(image_path.lower())[1]
    is_tiff = file_ext in ('.tif', '.tiff')
    is_jpeg = file_ext in ('.jpg', '.jpeg')

    if not (is_tiff or is_jpeg):
        print(
            f"Warning: Unsupported file format: {file_ext}. Only TIFF and JPEG are supported.")
        return False

    if pyexiv2:
        img = None
        backup_path = None
        try:

            try:
                backup_path = image_path + ".backup"
                shutil.copy2(image_path, backup_path)
            except Exception as e_backup:
                print(
                    f"      Warning: Could not create backup for {image_path}: {e_backup}")
                backup_path = None

            img = pyexiv2.Image(image_path)
            existing_exif = img.read_exif()
            existing_xmp = img.read_xmp()

            new_exif_data = {}
            new_xmp_data = {}
            new_iptc_data = {}

            # Shared timestamps used across EXIF / XMP.
            now = datetime.datetime.now()
            exif_dt = now.strftime('%Y:%m:%d %H:%M:%S')   # EXIF spec format
            iso_dt = now.isoformat()

            # ---- EXIF (Exif.Image.* + Exif.Photo.*) ----
            new_exif_data['Exif.Image.Artist'] = f"{photographer_name}"
            new_exif_data['Exif.Image.Copyright'] = copyright_text
            new_exif_data['Exif.Image.ImageDescription'] = image_title
            new_exif_data['Exif.Image.Software'] = "eBL Photo Stitcher"
            new_exif_data['Exif.Image.DateTime'] = exif_dt
            new_exif_data['Exif.Photo.DateTimeOriginal'] = exif_dt
            new_exif_data['Exif.Photo.DateTimeDigitized'] = exif_dt

            # Write resolution in metric (px/cm, ResolutionUnit=3) when we have
            # a measured scale; fall back to DPI (inches, ResolutionUnit=2)
            # when no per-object measurement is available.
            if pixels_per_cm and pixels_per_cm > 0:
                px_cm_int = int(round(pixels_per_cm))
                new_exif_data['Exif.Image.XResolution'] = f"{px_cm_int}/1"
                new_exif_data['Exif.Image.YResolution'] = f"{px_cm_int}/1"
                new_exif_data['Exif.Image.ResolutionUnit'] = '3'
            else:
                new_exif_data['Exif.Image.XResolution'] = f"{image_dpi}/1"
                new_exif_data['Exif.Image.YResolution'] = f"{image_dpi}/1"
                new_exif_data['Exif.Image.ResolutionUnit'] = '2'

            # ---- XMP (Dublin Core + xmp + xmpRights + photoshop + ebl) ----
            new_xmp_data['Xmp.dc.title'] = image_title
            new_xmp_data['Xmp.dc.creator'] = [photographer_name]
            new_xmp_data['Xmp.dc.rights'] = copyright_text
            new_xmp_data['Xmp.dc.description'] = image_title
            new_xmp_data['Xmp.dc.identifier'] = image_title
            new_xmp_data['Xmp.dc.publisher'] = [institution_name]
            new_xmp_data['Xmp.dc.date'] = [iso_dt]
            new_xmp_data['Xmp.dc.type'] = ['Image']

            # dc.subject is Dublin Core "keywords", not copyright.
            new_xmp_data['Xmp.dc.subject'] = [image_title]

            new_xmp_data['Xmp.xmp.CreatorTool'] = "eBL Photo Stitcher"
            new_xmp_data['Xmp.xmp.CreateDate'] = iso_dt
            new_xmp_data['Xmp.xmp.ModifyDate'] = iso_dt
            new_xmp_data['Xmp.xmp.MetadataDate'] = iso_dt

            new_xmp_data['Xmp.photoshop.Credit'] = credit_line_text
            new_xmp_data['Xmp.photoshop.Source'] = institution_name
            new_xmp_data['Xmp.photoshop.Headline'] = image_title

            new_xmp_data['Xmp.xmpRights.Marked'] = 'True'
            if usage_terms_text:
                # Plain string: pyexiv2 auto-wraps single-language XMP
                # AltLang tags as x-default. Writing a list-of-dict here
                # stores the Python repr literally instead of a proper
                # lang-alt, which readers then display as raw text.
                new_xmp_data['Xmp.xmpRights.UsageTerms'] = usage_terms_text

            # Physical object measurements (if available)
            if object_width_cm is not None and object_width_cm > 0:
                new_xmp_data['Xmp.dc.format'] = f"Tablet dimensions: {object_width_cm:.1f} x {object_length_cm:.1f} cm" if object_length_cm else f"Tablet width: {object_width_cm:.1f} cm"
                try:
                    pyexiv2.registerNs('http://ns.ebl.lmu.de/1.0/', 'ebl')
                except Exception:
                    pass
                new_xmp_data['Xmp.ebl.ObjectWidthCm'] = f"{object_width_cm:.2f}"
                if object_length_cm and object_length_cm > 0:
                    new_xmp_data['Xmp.ebl.ObjectLengthCm'] = f"{object_length_cm:.2f}"
                if pixels_per_cm and pixels_per_cm > 0:
                    new_xmp_data['Xmp.ebl.PixelsPerCm'] = f"{pixels_per_cm:.2f}"

            # ---- IPTC-IIM (legacy; older tools still rely on this) ----
            # Mirrors the XMP/EXIF content so readers that only understand the
            # older IPTC-IIM standard still see the same information.
            # Declare UTF-8 encoding via the ISO 2022 ESC % G escape so
            # readers don't default to Latin-1 and turn "á" into "Ã¡".
            new_iptc_data['Iptc.Envelope.CharacterSet'] = '\x1b%G'
            new_iptc_data['Iptc.Application2.ObjectName'] = image_title
            new_iptc_data['Iptc.Application2.Headline'] = image_title
            new_iptc_data['Iptc.Application2.Caption'] = image_title
            new_iptc_data['Iptc.Application2.Byline'] = [photographer_name]
            new_iptc_data['Iptc.Application2.Credit'] = credit_line_text
            new_iptc_data['Iptc.Application2.Source'] = institution_name
            new_iptc_data['Iptc.Application2.Copyright'] = copyright_text
            new_iptc_data['Iptc.Application2.Keywords'] = [image_title]
            new_iptc_data['Iptc.Application2.DateCreated'] = now.strftime('%Y-%m-%d')
            new_iptc_data['Iptc.Application2.TimeCreated'] = now.strftime('%H:%M:%S%z') or now.strftime('%H:%M:%S')

            img.modify_exif(new_exif_data)
            img.modify_xmp(new_xmp_data)
            try:
                img.modify_iptc(new_iptc_data)
            except Exception as e_iptc:
                # IPTC support is version-dependent in pyexiv2; EXIF+XMP is
                # sufficient on its own, so treat this as non-fatal.
                print(f"      Warn: IPTC-IIM write skipped ({e_iptc})")

            img.close()
            img = None

            print(
                f"      All metadata (EXIF, XMP) applied successfully via {exiv2_module_name}.")

            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception as e_rem_backup:
                    print(
                        f"      Warning: Could not remove backup file {backup_path}: {e_rem_backup}")

            return True

        except Exception as e:
            print(f"      Error applying metadata with {exiv2_module_name}: {e}")

            if backup_path and os.path.exists(backup_path):
                try:
                    print("      Restoring backup due to metadata error...")

                    if img is not None:
                        img.close()
                        img = None

                    if os.path.exists(image_path):
                        os.remove(image_path)
                    shutil.copy2(backup_path, image_path)
                    os.remove(backup_path)
                except Exception as e_restore:
                    print(f"      Error restoring backup for {image_path}: {e_restore}")

            print("      Falling back to piexif for basic EXIF...")
            return set_basic_exif_metadata(
                image_path, image_title, photographer_name,
                institution_name, copyright_text, image_dpi
            )
        finally:

            if img is not None:
                try:
                    img.close()
                except Exception as e_close_final:
                    print(
                        f"      Warning: Error closing pyexiv2.Image in finally block: {e_close_final}")

            if backup_path and os.path.exists(backup_path) and not os.path.exists(image_path):
                try:
                    print(
                        f"      Final cleanup: Restoring backup {backup_path} as original is missing.")
                    shutil.copy2(backup_path, image_path)
                    os.remove(backup_path)
                except Exception as e_final_restore:
                    print(f"      Error in final backup restoration: {e_final_restore}")
            elif backup_path and os.path.exists(backup_path) and os.path.exists(image_path):

                print(
                    f"      Final cleanup: Removing lingering backup file {backup_path}.")
                try:
                    os.remove(backup_path)
                except Exception as e_final_remove_backup:
                    print(
                        f"      Error in final backup removal: {e_final_remove_backup}")

    else:

        print("      No advanced metadata modules available, using piexif for basic EXIF.")
        return set_basic_exif_metadata(
            image_path, image_title, photographer_name,
            institution_name, copyright_text, image_dpi
        )
