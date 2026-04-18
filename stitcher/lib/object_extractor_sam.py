"""
Tablet object extractor using MobileSAM via onnxruntime.

*** Not currently used. ***

Experimental module written during Phase B.5 as a candidate replacement
for object_extractor_rembg.py. It produced worse results than rembg on
thin-edge tablet views (top/bottom edge shots where the tablet is a
narrow horizontal strip and a vertical foam support dominates the box).
Root cause: SAM is a promptable segmentation model — you give it a
point/box, it returns *that specific object*. rembg/U2NET is a salient
object detection model — trained to emit *all foreground* in one pass.
Different tools for different tasks.

The stitcher's automatic extraction path stays on rembg/U2NET. SAM is
used for interactive click-to-segment in the Electron UI (see the
renamer's src/main/sam-onnx.js), where the user explicitly points at
the tablet — the case SAM is actually trained for.

This file is kept as-is for potential future work on SAM-based auto
extraction (e.g. using SAM's output only to refine an initial U2NET
mask, or training a tablet-specific SAM adapter).

API (unused):
  extract_and_save_center_object(input_filepath, ...) -> (output_path, dummy_contour)

Runtime deps if re-enabled: onnxruntime, Pillow, opencv, numpy. No torch.
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


def _run_sam_box(image_bgr, box_margin=0.1):
    """
    Prompt SAM with a large central box covering (1 - 2*box_margin) of the
    image in each dimension (default 80%). SAM interprets a box prompt as
    "find the main object inside this rectangle" — much more robust than a
    single center point for off-center tablets.

    Why not a point prompt:
      - A point at (W/2, H/2) returns whatever SAM sees at that pixel.
        When the tablet is leaning against a foam support, the center
        often lands on foam; SAM returns foam.
    Why not an "everything-mode" grid:
      - Accumulating multiple prompt masks into a combined-foreground blob
        tends to fill the frame because SAM's individual per-point masks
        overlap unpredictably. Even with per-mask coverage filtering, the
        OR of 16 masks quickly approaches "whole image."
    Box prompt:
      - Single decoder call, deterministic output, tight around the main
        object. Returns the 3 multimask candidates; we pick highest IoU.

    Returns: binary mask (uint8, HxW, 0 or 255) at original image resolution.
    """
    encoder, decoder = _get_sessions()

    h, w = image_bgr.shape[:2]
    tensor, (orig_h, orig_w), scale = _preprocess(image_bgr)
    embeddings = encoder.run(None, {"images": tensor})[0]

    # Box corners in original image coords, scaled to 1024 input space.
    x1 = box_margin * w
    y1 = box_margin * h
    x2 = (1.0 - box_margin) * w
    y2 = (1.0 - box_margin) * h

    # SAM box prompt = two points with labels 2 (top-left) and 3 (bottom-right).
    coords = np.array(
        [[[x1 * scale, y1 * scale], [x2 * scale, y2 * scale]]], dtype=np.float32
    )
    labels = np.array([[2.0, 3.0]], dtype=np.float32)

    feeds = {
        "image_embeddings": embeddings,
        "point_coords": coords,
        "point_labels": labels,
        "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
        "has_mask_input": np.array([0.0], dtype=np.float32),
        "orig_im_size": np.array([orig_h, orig_w], dtype=np.float32),
    }
    outputs = decoder.run(None, feeds)
    masks = outputs[0]  # (1, N, H, W)
    ious = outputs[1]   # (1, N)

    best = int(np.argmax(ious[0]))
    print(f"    SAM box prompt → IoU {float(ious[0, best]):.3f}")
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

    # Box prompt covering 80% of the image, centered. Tells SAM "find the
    # main object inside this rectangle" — robust to off-center tablets
    # (the box still contains them) and avoids the foam-at-center failure
    # mode of single-point prompts.
    binary_mask = _run_sam_box(img_bgr)

    # Light morphological close: bridge 1-pixel gaps between adjacent masks
    # from neighboring grid points so the tablet stays a single component.
    kernel = np.ones((5, 5), np.uint8)
    binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)

    # Connected-component analysis across the combined foreground mask.
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary_mask, connectivity=8
    )

    h, w = binary_mask.shape[:2]
    if num_labels <= 1:
        print("    Warning: SAM coverage mask was empty!")
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
        print(f"    SAM coverage → {num_labels - 1} connected component(s)")

        # Heuristic (improved over rembg's):
        #   - Prefer the larger object.
        #   - Use distance-to-center only as a tiebreaker when the second-
        #     largest is within 30% of the largest's area.
        # Rationale: rembg's "closer of top-two" picked the foam on off-
        # center tablets because foam was smaller but more centered. Tablets
        # are almost always the dominant object by area; weighting size
        # over position picks the tablet even when foam is near center.
        if len(obj_data) == 1:
            selected_label = obj_data[0][0]
            print("    Only one component found — using it")
        else:
            largest, second = obj_data[0], obj_data[1]
            area_ratio = second[1] / largest[1] if largest[1] else 0
            if area_ratio < 0.7:
                # Largest clearly dominates → pick it.
                selected_label = largest[0]
                print(
                    f"    Largest ({largest[1]} px) dominates over second "
                    f"({second[1]} px, {area_ratio:.0%}) — picking largest"
                )
            elif largest[2] <= second[2]:
                # Close sizes; largest is closer to center.
                selected_label = largest[0]
                print("    Similar sizes — picking closer to center (largest)")
            else:
                # Close sizes; second is closer to center.
                selected_label = second[0]
                print("    Similar sizes — picking closer to center (second)")

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
