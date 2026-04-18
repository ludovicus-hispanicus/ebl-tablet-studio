"""
Professional post-processing for stitched images.
Replicates the Photoshop action used by the cuneiform documentation team:
  1. Levels adjustment (input black 46, gamma 0.6, input white 255)
  2. High Pass sharpening (radius 1.5 px, overlay blend with original)

Values are baked in from the 'cuneiform_documentation_bm.atn' Photoshop action
tuned by a professional for cuneiform tablet photography.
"""

import cv2
import numpy as np

# Photoshop action defaults
LEVELS_BLACK_IN = 46       # input black point
LEVELS_WHITE_IN = 255      # input white point
LEVELS_GAMMA = 0.6         # gamma (midtone brightening)
HIGH_PASS_RADIUS = 1.5     # blur sigma for the high-pass filter
SHARPEN_STRENGTH = 1.0     # how much high-pass detail to add (1.0 = overlay strength)


def apply_levels(image_bgr, black_in=LEVELS_BLACK_IN, white_in=LEVELS_WHITE_IN, gamma=LEVELS_GAMMA):
    """
    Photoshop-style Levels adjustment: remap [black_in, white_in] → [0, 255]
    with gamma correction for midtone brightening.
    """
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr

    # Build a 256-entry LUT applied uniformly to all three channels
    lut = np.arange(256, dtype=np.float32)
    denom = max(white_in - black_in, 1)
    lut = np.clip((lut - black_in) / denom, 0.0, 1.0)
    lut = np.power(lut, gamma) * 255.0
    lut = np.clip(lut, 0.0, 255.0).astype(np.uint8)

    return cv2.LUT(image_bgr, lut)


def apply_high_pass_sharpen(image_bgr, radius=HIGH_PASS_RADIUS, strength=SHARPEN_STRENGTH):
    """
    High Pass sharpening: high_pass = image - blur(image); result = image + high_pass * strength.
    This emphasises fine surface detail (cuneiform wedges) without heavy haloing.
    """
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr

    img_f = image_bgr.astype(np.float32)
    # Kernel size must be odd and at least 3; relate to radius
    ksize = max(3, int(radius * 6) | 1)
    blurred = cv2.GaussianBlur(img_f, (ksize, ksize), sigmaX=radius, sigmaY=radius)
    high_pass = img_f - blurred
    sharpened = img_f + high_pass * strength
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def apply_professional_processing(image_bgr):
    """
    Full post-processing pipeline: Levels + High Pass sharpening.
    Applies only to non-background pixels to preserve the clean bg.
    """
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr

    print("    Post-processing: Levels + High Pass sharpening")

    processed = apply_high_pass_sharpen(image_bgr)
    processed = apply_levels(processed)
    return processed
