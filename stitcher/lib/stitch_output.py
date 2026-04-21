
import cv2
import numpy as np
import os
import imageio
import datetime
import time
import stitch_config
from stitch_config import FINAL_TIFF_SUBFOLDER_NAME, FINAL_JPG_SUBFOLDER_NAME, JPEG_SAVE_QUALITY
from hdr_processor import HDR_SUFFIX

try:
    from pure_metadata import apply_all_metadata, set_basic_exif_metadata
except ImportError as e:
    print(f"CRITICAL ERROR in stitch_output.py: Could not import metadata utils: {e}")
    raise

try:
    from stitch_post_process import apply_professional_processing
except ImportError as e:
    print(f"Warning: stitch_post_process not available ({e}); post-processing disabled")
    def apply_professional_processing(img):
        return img


def save_stitched_output(
    final_image,
    main_input_folder_path,
    output_base_name,
    photographer_name,
    output_dpi,
    object_width_cm=None,
    object_length_cm=None,
    pixels_per_cm=None,
    output_folder_suffix=""
):
    """Save stitched output in both TIFF and JPG formats with metadata.

    output_folder_suffix: appended to the default `_Final_TIFF` / `_Final_JPG`
    folder names so that print variants land alongside the digital outputs
    without overwriting them (e.g. suffix='_Print' → `_Final_TIFF_Print/`).
    """
    if not isinstance(final_image, np.ndarray) or final_image.size == 0:
        raise ValueError("Invalid image for saving")

    if HDR_SUFFIX in output_base_name:
        output_base_name = output_base_name.replace(HDR_SUFFIX, "")

    # Professional post-processing: Levels + High Pass sharpening
    # (replicates the 'cuneiform_documentation_bm.atn' Photoshop action)
    final_image = apply_professional_processing(final_image)

    final_tiff_output_dir = os.path.join(
        main_input_folder_path, FINAL_TIFF_SUBFOLDER_NAME + output_folder_suffix)
    final_jpg_output_dir = os.path.join(
        main_input_folder_path, FINAL_JPG_SUBFOLDER_NAME + output_folder_suffix)
    os.makedirs(final_tiff_output_dir, exist_ok=True)
    os.makedirs(final_jpg_output_dir, exist_ok=True)

    tiff_filepath = os.path.join(final_tiff_output_dir, f"{output_base_name}.tif")
    jpg_filepath = os.path.join(final_jpg_output_dir, f"{output_base_name}.jpg")

    print(f"    Attempting to save TIFF to: {tiff_filepath}")
    tiff_save_success = save_tiff_output(final_image, tiff_filepath)

    print(f"    Attempting to save JPG to: {jpg_filepath}")
    jpg_save_success = save_jpg_output(final_image, jpg_filepath)

    if tiff_save_success or jpg_save_success:
        print("    Brief pause before metadata application...")
        time.sleep(0.5)

    saved_files = []
    if tiff_save_success:
        saved_files.append(tiff_filepath)
    if jpg_save_success:
        saved_files.append(jpg_filepath)

    for file_path in saved_files:
        print(f"    Setting metadata for: {os.path.basename(file_path)}...")
        apply_all_metadata(
            file_path,
            image_title=output_base_name,
            institution_name=stitch_config.STITCH_INSTITUTION,
            photographer_name=f"{photographer_name} ({stitch_config.STITCH_INSTITUTION})",
            credit_line_text=stitch_config.STITCH_CREDIT_LINE,
            copyright_text=stitch_config.STITCH_CREDIT_LINE,
            usage_terms_text=stitch_config.STITCH_XMP_USAGE_TERMS,
            image_dpi=output_dpi,
            object_width_cm=object_width_cm,
            object_length_cm=object_length_cm,
            pixels_per_cm=pixels_per_cm
        )

    if not tiff_save_success:
        print(
            f"    Skipping metadata for TIFF as save failed: {os.path.basename(tiff_filepath)}")
    if not jpg_save_success:
        print(
            f"    Skipping metadata for JPG as save failed: {os.path.basename(jpg_filepath)}")

    return (tiff_filepath if tiff_save_success else None,
            jpg_filepath if jpg_save_success else None)


def save_tiff_output(image, output_path):
    """Save image as TIFF format using primary and fallback methods."""
    try:

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if image_rgb is None or image_rgb.size == 0:
            raise ValueError("Color conversion failed")

        imageio.imwrite(output_path, image_rgb, format='TIFF')
        print(
            f"      Successfully saved TIFF (image data): {os.path.basename(output_path)}")
        return True
    except Exception as e_imageio:
        print(f"ERROR saving stitched TIFF with imageio: {e_imageio}")

        try:
            print(f"      Attempting fallback cv2.imwrite for TIFF: {output_path}")
            if not cv2.imwrite(output_path, image):
                raise IOError("cv2.imwrite for TIFF fallback returned False.")
            print(f"      Saved TIFF via cv2 (fallback).")
            return True
        except Exception as e_cv2_tiff:
            print(f"      ERROR saving final TIFF with cv2 fallback: {e_cv2_tiff}")
            return False


def save_jpg_output(image, output_path):
    """Save image as JPEG format."""
    try:
        # JPEG only supports 8-bit images
        if image.dtype != np.uint8:
            print(f"      Converting image from {image.dtype} to uint8 for JPG")
            image = (image / image.max() * 255).astype(np.uint8) if image.max() > 0 else image.astype(np.uint8)

        print(f"      JPG save: shape={image.shape}, dtype={image.dtype}, path={output_path}")

        # JPEG has a max dimension limit of ~65535 pixels
        h, w = image.shape[:2]
        if h > 65500 or w > 65500:
            # Scale down to fit JPEG limits
            scale = min(65500 / h, 65500 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            print(f"      Image too large for JPEG ({w}x{h}), scaling to {new_w}x{new_h}")
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if not cv2.imwrite(output_path, image, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_SAVE_QUALITY]):
            # cv2 failed — try writing to a temp file in the same directory
            # (avoids path encoding issues in PyInstaller exe context)
            print(f"      cv2.imwrite failed, trying temp file workaround...")
            import tempfile
            output_dir = os.path.dirname(output_path)
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg', dir=output_dir)
                os.close(tmp_fd)
                if cv2.imwrite(tmp_path, image, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_SAVE_QUALITY]):
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(tmp_path, output_path)
                    print(f"      Successfully saved JPG via temp file: {os.path.basename(output_path)}")
                    return True
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception as tmp_err:
                print(f"      Temp file method failed: {tmp_err}")

            # Final fallback: Pillow
            print(f"      Trying Pillow fallback...")
            try:
                from PIL import Image as PILImage
                PILImage.MAX_IMAGE_PIXELS = None
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_img = PILImage.fromarray(rgb)
                tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg', dir=output_dir)
                os.close(tmp_fd)
                pil_img.save(tmp_path, 'JPEG', quality=JPEG_SAVE_QUALITY)
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(tmp_path, output_path)
                print(f"      Successfully saved JPG via Pillow: {os.path.basename(output_path)}")
                return True
            except Exception as pil_err:
                # Clean up temp file
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                raise IOError(f"All JPG save methods failed: {pil_err}")

        print(
            f"      Successfully saved JPG: {os.path.basename(output_path)} with quality {JPEG_SAVE_QUALITY}")
        return True
    except Exception as e_jpg:
        print(f"      ERROR saving final JPG: {e_jpg}")
        import traceback
        traceback.print_exc()
        return False
