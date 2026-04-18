"""
Functions for processing and manipulating images in the stitching process.
"""
import cv2
import numpy as np

try:
    from image_utils import resize_image_maintain_aspect, convert_to_bgr_if_needed
except ImportError as e:
    print(f"FATAL ERROR: stitch_image_processing.py cannot import: {e}")
    def resize_image_maintain_aspect(
        *args): raise ImportError("resize_image_maintain_aspect missing")

    def convert_to_bgr_if_needed(img): return img


def resize_tablet_views_for_layout(loaded_images_dictionary):
    """
    Resize all tablet views. If obverse is present, other main views are resized relative to it.
    Handles single images and lists of images (sequences).

    Args:
        loaded_images_dictionary: Dictionary of loaded images

    Returns:
        Dictionary of resized images
    """
    obverse_image_data = loaded_images_dictionary.get("obverse")

    obv_h, obv_w = 0, 0
    if isinstance(obverse_image_data, np.ndarray) and obverse_image_data.size > 0:
        obv_h, obv_w = obverse_image_data.shape[:2]
    elif isinstance(obverse_image_data, list) and obverse_image_data and isinstance(obverse_image_data[0], np.ndarray):

        obv_h, obv_w = obverse_image_data[0].shape[:2]
        print("      Resize: 'obverse' is a list, using first image for reference dimensions.")

    if obv_h == 0 or obv_w == 0:

        print("      Warn: Obverse image not valid for relative resizing. Skipping relative resize of other views.")

        processed_dict = {}
        for view_key, image_data_item in loaded_images_dictionary.items():
            if isinstance(image_data_item, list):
                processed_list = [img for img in image_data_item if isinstance(
                    img, np.ndarray) and img.size > 0]
                processed_dict[view_key] = processed_list if processed_list else None
            elif isinstance(image_data_item, np.ndarray) and image_data_item.size > 0:
                processed_dict[view_key] = image_data_item
            else:
                processed_dict[view_key] = None
        return processed_dict

    resize_config = {

        "left": {"axis": 0, "match_dim": obv_h},
        "right": {"axis": 0, "match_dim": obv_h},
        "top": {"axis": 1, "match_dim": obv_w},
        "bottom": {"axis": 1, "match_dim": obv_w},
        "reverse": {"axis": 1, "match_dim": obv_w}

    }

    output_resized_images = {}
    for view_key, image_data in loaded_images_dictionary.items():
        if view_key == "obverse":
            output_resized_images[view_key] = obverse_image_data
            continue

        params = None

        for r_key, r_params in resize_config.items():
            if r_key in view_key:
                params = r_params
                break

        if not params and "ruler" not in view_key:
            print(
                f"      Resize: No specific resize rule for '{view_key}'. Keeping original.")
            output_resized_images[view_key] = image_data
            continue
        elif "ruler" in view_key:
            output_resized_images[view_key] = image_data
            continue

        if isinstance(image_data, np.ndarray) and image_data.size > 0:
            output_resized_images[view_key] = resize_image_maintain_aspect(
                image_data, params["match_dim"], params["axis"]
            )
        elif isinstance(image_data, list):
            resized_sequence = []
            for img_in_seq in image_data:
                if isinstance(img_in_seq, np.ndarray) and img_in_seq.size > 0:
                    resized_img = resize_image_maintain_aspect(
                        img_in_seq, params["match_dim"], params["axis"]
                    )
                    resized_sequence.append(resized_img)
                else:
                    resized_sequence.append(None)
            output_resized_images[view_key] = [rs for rs in resized_sequence if rs is not None] if any(
                rs is not None for rs in resized_sequence) else None
        elif image_data is not None:
            output_resized_images[view_key] = None
            print(
                f"      Warn: Resize - Unexpected data type for {view_key}: {type(image_data)}")
        else:
            output_resized_images[view_key] = None

    return output_resized_images


def create_rotated_images(images_dict):
    """
    Create rotated versions of left and right side images for the reverse row.

    Args:
        images_dict: Dictionary of images

    Returns:
        Dictionary with additional rotated images
    """
    modified_images_dict = dict(images_dict)

    if images_dict.get("left") is not None:
        left_img_data = images_dict["left"]
        if isinstance(left_img_data, np.ndarray) and left_img_data.size > 0:
            modified_images_dict["left_rotated"] = cv2.rotate(
                left_img_data, cv2.ROTATE_180)
        elif isinstance(left_img_data, list) and left_img_data:
            print("      Warn: 'left' is a list, rotation for 'left_rotated' might be unexpected.")

    if images_dict.get("right") is not None:
        right_img_data = images_dict["right"]
        if isinstance(right_img_data, np.ndarray) and right_img_data.size > 0:
            modified_images_dict["right_rotated"] = cv2.rotate(
                right_img_data, cv2.ROTATE_180)
        elif isinstance(right_img_data, list) and right_img_data:
            print("      Warn: 'right' is a list, rotation for 'right_rotated' might be unexpected.")

    return modified_images_dict
