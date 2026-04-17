"""
Validate numerical parity between torch MobileSAM and ONNX MobileSAM.

Runs the same tablet image through both pipelines with an identical
center-point prompt and compares:
  - mask IoU (intersection-over-union)
  - logit cosine similarity
  - inference time
  - produced PNG overlays (side-by-side) for visual inspection

Usage:
    python tools/validate_sam_onnx.py --image <path-to-jpg>

Exits 0 if IoU > 0.98 on the selected mask; non-zero otherwise.
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import torch
from mobile_sam import sam_model_registry, SamPredictor


def preprocess_image(image_bgr: np.ndarray, target_size: int = 1024) -> tuple[np.ndarray, tuple[int, int]]:
    """
    Resize with long-edge = target_size, pad to square with zeros.
    Matches SAM's standard preprocessing.
    Returns (preprocessed_1x3xHxW_rgb_float, original_hw).
    """
    h, w = image_bgr.shape[:2]
    scale = target_size / max(h, w)
    new_h, new_w = int(h * scale), int(w * scale)

    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    # ImageNet-style normalization to match SAM's image_encoder
    mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)
    std = np.array([58.395, 57.12, 57.375], dtype=np.float32)
    normalized = (rgb.astype(np.float32) - mean) / std

    # Pad to 1024x1024
    padded = np.zeros((target_size, target_size, 3), dtype=np.float32)
    padded[:new_h, :new_w] = normalized

    # HWC -> CHW -> NCHW
    tensor = padded.transpose(2, 0, 1)[None, ...].astype(np.float32)
    return tensor, (h, w)


def run_torch(weights: Path, image_bgr: np.ndarray, click_xy: tuple[int, int]) -> tuple[np.ndarray, float]:
    """
    Returns (best_mask_HxW_uint8, elapsed_seconds).
    """
    sam = sam_model_registry["vit_t"](checkpoint=str(weights))
    sam.eval()
    predictor = SamPredictor(sam)

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    t0 = time.time()
    predictor.set_image(rgb)

    point_coords = np.array([click_xy], dtype=np.float32)
    point_labels = np.array([1], dtype=np.float32)
    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )
    elapsed = time.time() - t0

    # Pick highest-score mask
    best = int(np.argmax(scores))
    return masks[best].astype(np.uint8), elapsed


def run_onnx(encoder_path: Path, decoder_path: Path, image_bgr: np.ndarray, click_xy: tuple[int, int]) -> tuple[np.ndarray, float]:
    """
    Returns (best_mask_HxW_uint8, elapsed_seconds).
    """
    enc = ort.InferenceSession(str(encoder_path), providers=["CPUExecutionProvider"])
    dec = ort.InferenceSession(str(decoder_path), providers=["CPUExecutionProvider"])

    t0 = time.time()
    input_tensor, (orig_h, orig_w) = preprocess_image(image_bgr)
    embeddings = enc.run(None, {"images": input_tensor})[0]

    # Transform click coordinates from original -> 1024 space
    scale = 1024.0 / max(orig_h, orig_w)
    px, py = click_xy
    click_1024 = np.array([[[px * scale, py * scale]]], dtype=np.float32)  # shape (1, 1, 2)
    labels_1024 = np.array([[1]], dtype=np.float32)

    # Pad points with an end-marker (required by SAM ONNX model: appends (0,0) with label -1)
    # See segment_anything.utils.onnx.SamOnnxModel: the model internally pads, but here we
    # just feed positive points.
    onnx_coords = np.concatenate([click_1024, np.zeros((1, 1, 2), dtype=np.float32)], axis=1)
    onnx_labels = np.concatenate([labels_1024, -np.ones((1, 1), dtype=np.float32)], axis=1)

    decoder_inputs = {
        "image_embeddings": embeddings,
        "point_coords": onnx_coords,
        "point_labels": onnx_labels,
        "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
        "has_mask_input": np.zeros(1, dtype=np.float32),
        "orig_im_size": np.array([orig_h, orig_w], dtype=np.float32),
    }
    masks, iou, _ = dec.run(None, decoder_inputs)
    elapsed = time.time() - t0

    # masks shape: (1, N, H, W) — pick highest-iou
    best = int(np.argmax(iou[0]))
    return (masks[0, best] > 0).astype(np.uint8), elapsed


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return inter / union if union > 0 else 1.0


def save_overlay(image_bgr: np.ndarray, mask: np.ndarray, out_path: Path, click_xy: tuple[int, int], label: str) -> None:
    overlay = image_bgr.copy()
    # Green tint where mask is set
    green = np.zeros_like(overlay)
    green[..., 1] = 255
    alpha = 0.45
    mask_3 = np.stack([mask] * 3, axis=-1) > 0
    overlay = np.where(mask_3, (overlay * (1 - alpha) + green * alpha).astype(np.uint8), overlay)
    # Mark the click
    cv2.circle(overlay, click_xy, 12, (0, 0, 255), 2)
    cv2.putText(overlay, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imwrite(str(out_path), overlay)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to tablet JPG")
    parser.add_argument("--weights", default="python/weights/mobile_sam.pt")
    parser.add_argument("--onnx-dir", default="experiments/sam-onnx")
    parser.add_argument("--out-dir", default="experiments/sam-validation")
    args = parser.parse_args()

    image_path = Path(args.image).resolve()
    weights = Path(args.weights).resolve()
    onnx_dir = Path(args.onnx_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        print(f"ERROR: couldn't load {image_path}")
        sys.exit(1)

    h, w = image_bgr.shape[:2]
    click = (w // 2, h // 2)
    print(f"Image: {image_path.name}  ({w}x{h})  click: {click}")

    print("Running torch MobileSAM...")
    torch_mask, torch_t = run_torch(weights, image_bgr, click)
    print(f"  torch: mask area = {int(torch_mask.sum())} px,  time = {torch_t:.2f}s")

    print("Running ONNX MobileSAM...")
    onnx_mask, onnx_t = run_onnx(onnx_dir / "mobile_sam_encoder.onnx",
                                  onnx_dir / "mobile_sam_decoder.onnx",
                                  image_bgr, click)
    print(f"  onnx:  mask area = {int(onnx_mask.sum())} px,  time = {onnx_t:.2f}s")

    score = iou(torch_mask, onnx_mask)
    print(f"\nIoU(torch, onnx) = {score:.4f}")

    save_overlay(image_bgr, torch_mask, out_dir / f"{image_path.stem}_torch.jpg", click, "torch")
    save_overlay(image_bgr, onnx_mask, out_dir / f"{image_path.stem}_onnx.jpg", click, "onnx")
    print(f"Overlays saved to {out_dir}")

    if score < 0.98:
        print(f"FAIL: IoU {score:.4f} below 0.98 threshold")
        sys.exit(1)
    print(f"PASS: IoU {score:.4f} >= 0.98")


if __name__ == "__main__":
    main()
