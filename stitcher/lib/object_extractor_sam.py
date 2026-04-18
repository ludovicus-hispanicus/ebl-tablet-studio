"""
Tablet object extractor using MobileSAM via onnxruntime.

Drop-in replacement for object_extractor_rembg.py:
  - Same public function: extract_and_save_center_object(input_filepath, ...)
  - Same return type: (output_filepath, dummy_contour)
  - Same output convention: <input_base><output_filename_suffix>

Semantic difference vs rembg:
  - rembg produces a generic foreground mask, then stitcher picks the object
    closest to the image center among the two largest connected components.
    On off-center tablets (e.g. a tablet leaning against foam support), that
    heuristic can silently pick the foam instead of the tablet, and because
    the choice lives right at the ranking tiebreaker, tiny rembg/torch/onnx
    version drift flips the selection unpredictably.
  - SAM with a center-point prompt asks "what's the object touching this
    point?" and returns exactly that object. The selection is deterministic
    given the same inputs + same ONNX model. For off-center tablets the
    center point can still land on the foam (same failure) — but it's now
    predictable and a manual click in the Electron segmentation UI always
    gives a clean override.

Runtime deps:
  - onnxruntime (no torch, no rembg, no u2net at runtime)
  - Pillow, opencv, numpy (already in use elsewhere)

The ONNX models live under repo-level resources/models/sam/. In dev this
is resolved relative to this module's parent; under PyInstaller it's
expected at sys._MEIPASS/models/sam/ (see .spec datas). Env var
EBL_SAM_MODELS_DIR overrides both.
"""

import os
import sys
import time
import gc

import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    import onnxruntime as ort
except ImportError as e:
    raise ImportError(
        "onnxruntime is required for object_extractor_sam; "
        "install with `pip install onnxruntime`"
    ) from e

from object_extractor import DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE  # noqa: F401

# SAM preprocessing constants (ImageNet stats, 1024 input).
_MODEL_INPUT_SIZE = 1024
_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)

# Module-level ONNX session cache (load once, reuse across calls).
_sessions = {"encoder": None, "decoder": None}


def _resolve_models_dir():
    """
    Find the ONNX model directory.
    Priority: EBL_SAM_MODELS_DIR env var > PyInstaller bundle > repo dev layout.
    """
    override = os.environ.get("EBL_SAM_MODELS_DIR")
    if override:
        return override

    # PyInstaller: assets extracted under sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        packaged = os.path.join(meipass, "models", "sam")
        if os.path.exists(packaged):
            return packaged

    # Dev: <this file>/../../../resources/models/sam
    # lib/object_extractor_sam.py -> lib -> stitcher -> repo -> resources/...
    here = os.path.abspath(os.path.dirname(__file__))
    dev = os.path.abspath(os.path.join(here, "..", "..", "resources", "models", "sam"))
    if os.path.exists(dev):
        return dev

    raise FileNotFoundError(
        f"SAM ONNX models not found. Checked EBL_SAM_MODELS_DIR, "
        f"PyInstaller bundle ({meipass or 'n/a'}), and dev path ({dev})."
    )


def _get_sessions():
    """Lazy-load the encoder + decoder ONNX sessions."""
    if _sessions["encoder"] is None or _sessions["decoder"] is None:
        models_dir = _resolve_models_dir()
        enc_path = os.path.join(models_dir, "mobile_sam_encoder.onnx")
        dec_path = os.path.join(models_dir, "mobile_sam_decoder.onnx")

        # Prefer GPU if available, fall back to CPU.
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            chosen = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            print("  SAM: using CUDA for inference")
        else:
            chosen = ["CPUExecutionProvider"]
            print("  SAM: using CPU for inference")

        _sessions["encoder"] = ort.InferenceSession(enc_path, providers=chosen)
        _sessions["decoder"] = ort.InferenceSession(dec_path, providers=chosen)

    return _sessions["encoder"], _sessions["decoder"]


def _preprocess(image_bgr):
    """
    SAM preprocessing: resize longest edge to 1024, ImageNet-normalize,
    pad to 1024x1024, transpose HWC->CHW->NCHW.
    Returns (tensor, orig_hw, scale).
    """
    h, w = image_bgr.shape[:2]
    scale = _MODEL_INPUT_SIZE / max(h, w)
    new_h, new_w = int(round(h * scale)), int(round(w * scale))

    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    normalized = (rgb - _MEAN) / _STD

    padded = np.zeros((_MODEL_INPUT_SIZE, _MODEL_INPUT_SIZE, 3), dtype=np.float32)
    padded[:new_h, :new_w] = normalized

    tensor = padded.transpose(2, 0, 1)[None, ...].astype(np.float32)
    return tensor, (h, w), scale


def _run_sam_center_point(image_bgr):
    """
    Run SAM with a single positive point at the image center. Returns the
    highest-IoU binary mask at the original image size as a uint8 HxW array
    (0 or 255).
    """
    encoder, decoder = _get_sessions()

    h, w = image_bgr.shape[:2]
    tensor, (orig_h, orig_w), scale = _preprocess(image_bgr)
    embeddings = encoder.run(None, {"images": tensor})[0]

    # Center point, transformed into the 1024 input space.
    cx, cy = w / 2.0, h / 2.0
    coords = np.array([[[cx * scale, cy * scale], [0.0, 0.0]]], dtype=np.float32)
    labels = np.array([[1.0, -1.0]], dtype=np.float32)  # 1 = positive, -1 = sentinel

    feeds = {
        "image_embeddings": embeddings,
        "point_coords": coords,
        "point_labels": labels,
        "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
        "has_mask_input": np.array([0.0], dtype=np.float32),
        "orig_im_size": np.array([orig_h, orig_w], dtype=np.float32),
    }
    outputs = decoder.run(None, feeds)
    masks = outputs[0]  # (1, N, H, W) logits at original size
    ious = outputs[1]   # (1, N) predicted IoU per candidate

    best = int(np.argmax(ious[0]))
    return (masks[0, best] > 0).astype(np.uint8) * 255


def extract_and_save_center_object(
    input_image_filepath,
    source_background_detection_mode="auto",
    output_image_background_color=(0, 0, 0),
    feather_radius_px=10,
    output_filename_suffix="_object.tif",
    min_object_area_as_image_fraction=0.01,
    object_contour_smoothing_kernel_size=3,
    museum_selection=None,
):
    """
    Extract the object closest to the image center using SAM.

    Signature and semantics preserved from object_extractor_rembg so the
    rest of the workflow doesn't need to change. Several keyword arguments
    are accepted for compatibility but not used by this implementation
    (feather_radius_px, object_contour_smoothing_kernel_size,
    min_object_area_as_image_fraction, source_background_detection_mode,
    museum_selection).
    """
    print(
        f"  Extracting center object from: {os.path.basename(input_image_filepath)} using SAM"
    )
    start_time = time.time()

    if not isinstance(output_image_background_color, (tuple, list)):
        print(
            f"    Warning: output_image_background_color is not a tuple/list: "
            f"{type(output_image_background_color)}, using default (0,0,0)"
        )
        output_image_background_color = (0, 0, 0)

    # Load the image, respecting EXIF orientation. The test corpus contains
    # JPEGs with Orientation=8 (rotate 90 CW for display) — the stored pixel
    # buffer is landscape but the intended image is portrait. rembg's old path
    # applied the rotation implicitly; the SAM path needs to do it explicitly
    # so the produced mask + crop match the tablet's visual orientation.
    # For TIFFs coming out of RAW conversion, orientation is almost always 1;
    # exif_transpose is a no-op there.
    try:
        input_img = Image.open(input_image_filepath)
        input_img = ImageOps.exif_transpose(input_img).convert("RGB")
        img_rgb = np.array(input_img)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise FileNotFoundError(
            f"Could not load image for object extraction: {input_image_filepath} - {e}"
        )

    # Run SAM → binary mask at original image size.
    binary_mask = _run_sam_center_point(img_bgr)

    # Light morphological clean: bridge 1-pixel gaps so the largest CC
    # doesn't get artificially split.
    kernel = np.ones((3, 3), np.uint8)
    binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)

    # Connected-component analysis, same shape as rembg module.
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary_mask, connectivity=8
    )

    h, w = binary_mask.shape[:2]
    if num_labels <= 1:
        print("    Warning: SAM mask was empty!")
        selected_object_mask = binary_mask
        bbox = (0, 0, w, h)
    else:
        center_x = w / 2.0
        center_y = h / 2.0

        obj_data = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            cx, cy = centroids[i]
            distance_to_center = float(np.sqrt((cx - center_x) ** 2 + (cy - center_y) ** 2))
            obj_data.append((i, int(area), distance_to_center))

        obj_data.sort(key=lambda x: x[1], reverse=True)
        largest_objects = obj_data[: min(2, len(obj_data))]
        print(f"    SAM produced {num_labels - 1} connected component(s)")

        if len(largest_objects) == 1:
            selected_label = largest_objects[0][0]
            print("    Only one component found - using it")
        elif largest_objects[0][2] <= largest_objects[1][2]:
            selected_label = largest_objects[0][0]
            print("    Two largest components found - selecting the one closer to center")
        else:
            selected_label = largest_objects[1][0]
            print("    Two largest components found - selecting the one closer to center")

        selected_object_mask = np.zeros_like(binary_mask)
        selected_object_mask[labels == selected_label] = 255

        y_indices, x_indices = np.where(selected_object_mask > 0)
        if len(y_indices) == 0:
            print("    Warning: No valid components found!")
            bbox = (0, 0, w, h)
        else:
            x_min, x_max = int(np.min(x_indices)), int(np.max(x_indices))
            y_min, y_max = int(np.min(y_indices)), int(np.max(y_indices))

            padding = 10
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(w, x_max + padding)
            y_max = min(h, y_max + padding)

            bbox = (x_min, y_min, x_max, y_max)

    # Compose the RGBA output with the original pixels visible only through
    # the mask; same approach as the rembg module.
    rgba = np.dstack([np.array(input_img), selected_object_mask])  # H x W x 4 (RGBA)
    rgba_pil = Image.fromarray(rgba, mode="RGBA")

    cropped_img = rgba_pil.crop(bbox)

    if not isinstance(output_image_background_color, (tuple, list)) or len(output_image_background_color) != 3:
        output_image_background_color = (0, 0, 0)

    # output_image_background_color comes in BGR (OpenCV convention); PIL
    # expects RGB, so swap to match rembg's behavior.
    bg_color_rgb = (
        int(output_image_background_color[2]),
        int(output_image_background_color[1]),
        int(output_image_background_color[0]),
    )
    bg_img = Image.new("RGB", cropped_img.size, bg_color_rgb)
    bg_img.paste(cropped_img, (0, 0), cropped_img)

    base_filepath, _ = os.path.splitext(input_image_filepath)
    output_image_filepath = f"{base_filepath}{output_filename_suffix}"

    try:
        file_ext = os.path.splitext(output_image_filepath)[1].lower()
        if file_ext in [".tif", ".tiff"]:
            bg_img.save(output_image_filepath, format="TIFF")
        elif file_ext in [".jpg", ".jpeg"]:
            bg_img.save(output_image_filepath, format="JPEG")
        elif file_ext == ".png":
            bg_img.save(output_image_filepath, format="PNG")
        else:
            bg_img.save(output_image_filepath)

        elapsed = time.time() - start_time
        print(
            f"    Successfully saved extracted artifact: {output_image_filepath} "
            f"(took {elapsed:.2f}s)"
        )

        # Free large arrays (big tablet photos push memory hard during batch runs).
        del rgba, rgba_pil, binary_mask, selected_object_mask
        gc.collect()

        dummy_contour = np.array(
            [[[0, 0]], [[0, 1]], [[1, 1]], [[1, 0]]], dtype=np.int32
        )
        return output_image_filepath, dummy_contour
    except Exception as e:
        raise IOError(
            f"Error saving extracted artifact to {output_image_filepath}: {e}"
        )
