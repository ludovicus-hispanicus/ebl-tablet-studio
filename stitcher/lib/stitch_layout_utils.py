import numpy as np


def get_image_dimension(image_or_list, axis_index, blend_overlap_px=0):
    """
    Get height or width dimension of an image or a list of images (calculating post-blend dimension for lists).

    Args:
        image_or_list: A single image array or a list of image arrays
        axis_index: 0 for height, 1 for width
        blend_overlap_px: Amount of overlap in pixels when blending images

    Returns:
        The dimension value, or 0 if the image is invalid
    """
    if isinstance(image_or_list, np.ndarray) and image_or_list.ndim >= 2 and image_or_list.size > 0:
        return image_or_list.shape[axis_index]
    elif isinstance(image_or_list, list) and image_or_list:
        if not image_or_list:
            return 0
        if axis_index == 0:
            total_height = 0
            min_common_width = float('inf')
            for i, img in enumerate(image_or_list):
                if not isinstance(img, np.ndarray) or img.size == 0:
                    continue
                total_height += img.shape[0]
                min_common_width = min(min_common_width, img.shape[1])
                if i > 0:
                    total_height -= blend_overlap_px
            return total_height
        else:
            total_width = 0
            min_common_height = float('inf')
            for i, img in enumerate(image_or_list):
                if not isinstance(img, np.ndarray) or img.size == 0:
                    continue
                total_width += img.shape[1]
                min_common_height = min(min_common_height, img.shape[0])
                if i > 0:
                    total_width -= blend_overlap_px
            return total_width
    return 0


def get_layout_bounding_box(images_dict, layout_coords):
    """
    Calculate the bounding box that contains all placed images.

    Args:
        images_dict: Dictionary of image arrays
        layout_coords: Dictionary of (x, y) coordinates for each image

    Returns:
        (min_x, min_y, max_x, max_y) if there are valid elements, None otherwise
    """
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    found_any_placed_element = False

    for key, (x_coord, y_coord) in layout_coords.items():
        image_array = images_dict.get(key)
        if isinstance(image_array, np.ndarray) and image_array.size > 0:
            found_any_placed_element = True
            h_img, w_img = image_array.shape[:2]
            min_x = min(min_x, x_coord)
            min_y = min(min_y, y_coord)
            max_x = max(max_x, x_coord + w_img)
            max_y = max(max_y, y_coord + h_img)

    return (min_x, min_y, max_x, max_y) if found_any_placed_element else None
