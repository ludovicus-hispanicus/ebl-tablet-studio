import cv2
import numpy as np

try:
    from stitch_layout_utils import get_image_dimension, get_layout_bounding_box
    from stitch_image_processing import resize_tablet_views_for_layout, create_rotated_images
    from stitch_intermediates_manager import group_intermediate_images, calculate_row_widths
    from stitch_layout_calculation import calculate_stitching_layout
except ImportError as e:
    print(
        f"FATAL ERROR: stitch_layout_manager.py cannot import modular components: {e}")
    from stitch_config import (
        STITCH_VIEW_GAP_PX,
        STITCH_RULER_PADDING_PX,
        get_extended_intermediate_suffixes
    )
    from blending_mask_applier import generate_position_patterns
    from image_utils import resize_image_maintain_aspect, convert_to_bgr_if_needed

__all__ = [
    "calculate_stitching_layout",
    "resize_tablet_views_for_layout",
    "get_layout_bounding_box"
]
