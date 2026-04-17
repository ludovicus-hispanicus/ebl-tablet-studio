"""
Prototype tablet extractor using SAM via ONNX (no torch at runtime).

Pipeline:
  1. Preprocess image (SAM's resize+pad to 1024, ImageNet normalize)
  2. Run ONNX image encoder once
  3. Run ONNX prompt decoder with a center-point prompt
  4. Pick highest-IoU mask
  5. Post-process: largest connected component containing the click,
     morphological close to smooth edges
  6. Apply mask to original image, crop to bbox, save as _sam_object.tif
  7. Also save a visualization overlay next to the object

Usage:
    python tools/extract_with_sam.py --image PATH [--out DIR]
    python tools/extract_with_sam.py --batch FOLDER [--out DIR]
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

ENCODER_DEFAULT = "experiments/sam-onnx/mobile_sam_encoder.onnx"
DECODER_DEFAULT = "experiments/sam-onnx/mobile_sam_decoder.onnx"


class SamExtractor:
    def __init__(self, encoder_path: str, decoder_path: str):
        self.enc = ort.InferenceSession(encoder_path, providers=["CPUExecutionProvider"])
        self.dec = ort.InferenceSession(decoder_path, providers=["CPUExecutionProvider"])
        self.target = 1024

    def _preprocess(self, image_bgr: np.ndarray) -> tuple[np.ndarray, tuple[int, int], float]:
        h, w = image_bgr.shape[:2]
        scale = self.target / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)

        resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)
        std = np.array([58.395, 57.12, 57.375], dtype=np.float32)
        normalized = (rgb.astype(np.float32) - mean) / std

        padded = np.zeros((self.target, self.target, 3), dtype=np.float32)
        padded[:new_h, :new_w] = normalized
        tensor = padded.transpose(2, 0, 1)[None, ...].astype(np.float32)
        return tensor, (h, w), scale

    def predict(self, image_bgr: np.ndarray, click_xy: tuple[int, int]) -> tuple[np.ndarray, float]:
        """
        Returns (binary_mask_HxW_uint8, iou_score).
        """
        tensor, (h, w), scale = self._preprocess(image_bgr)
        embeddings = self.enc.run(None, {"images": tensor})[0]

        px, py = click_xy
        pt_1024 = np.array([[[px * scale, py * scale]]], dtype=np.float32)
        labels = np.array([[1]], dtype=np.float32)
        # Append SAM's "empty" sentinel (0,0) with label -1
        coords = np.concatenate([pt_1024, np.zeros((1, 1, 2), dtype=np.float32)], axis=1)
        labels = np.concatenate([labels, -np.ones((1, 1), dtype=np.float32)], axis=1)

        dec_inputs = {
            "image_embeddings": embeddings,
            "point_coords": coords,
            "point_labels": labels,
            "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
            "has_mask_input": np.zeros(1, dtype=np.float32),
            "orig_im_size": np.array([h, w], dtype=np.float32),
        }
        masks, iou, _ = self.dec.run(None, dec_inputs)
        best = int(np.argmax(iou[0]))
        mask = (masks[0, best] > 0).astype(np.uint8)
        return mask, float(iou[0, best])


def clean_mask(mask: np.ndarray, click_xy: tuple[int, int]) -> np.ndarray:
    """
    Keep only the connected component containing the click; smooth edges.
    """
    # Close small holes
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    num, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    if num <= 1:
        return closed

    px, py = click_xy
    click_label = labels[py, px] if 0 <= py < labels.shape[0] and 0 <= px < labels.shape[1] else 0
    if click_label == 0:
        # Click fell on background; pick the largest non-bg component
        areas = stats[1:, cv2.CC_STAT_AREA]
        click_label = int(np.argmax(areas)) + 1

    return (labels == click_label).astype(np.uint8)


def extract_and_save(extractor: SamExtractor, image_path: Path, out_dir: Path,
                     bg_color=(0, 0, 0), pad=20) -> dict:
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"SKIP (unreadable): {image_path}")
        return {}
    h, w = img.shape[:2]
    click = (w // 2, h // 2)

    t0 = time.time()
    raw_mask, iou = extractor.predict(img, click)
    cleaned = clean_mask(raw_mask, click)
    elapsed = time.time() - t0

    ys, xs = np.where(cleaned > 0)
    if len(xs) == 0:
        print(f"  FAIL: empty mask for {image_path.name}")
        return {"path": str(image_path), "ok": False}

    x_min, x_max = max(0, int(xs.min()) - pad), min(w, int(xs.max()) + pad)
    y_min, y_max = max(0, int(ys.min()) - pad), min(h, int(ys.max()) + pad)

    bg = np.full_like(img, bg_color, dtype=np.uint8)
    mask_3 = np.stack([cleaned] * 3, axis=-1)
    composited = np.where(mask_3 > 0, img, bg)
    cropped = composited[y_min:y_max, x_min:x_max]

    stem = image_path.stem
    out_obj = out_dir / f"{stem}_sam_object.jpg"
    out_overlay = out_dir / f"{stem}_sam_overlay.jpg"
    cv2.imwrite(str(out_obj), cropped, [cv2.IMWRITE_JPEG_QUALITY, 90])

    # Overlay: green tint on mask + red click circle, small version
    overlay = img.copy()
    green = np.zeros_like(overlay); green[..., 1] = 255
    alpha = 0.4
    overlay = np.where(mask_3 > 0,
                       (overlay * (1 - alpha) + green * alpha).astype(np.uint8),
                       overlay)
    cv2.circle(overlay, click, 18, (0, 0, 255), 3)
    # Resize for smaller file
    scale = 1000 / max(overlay.shape[:2])
    if scale < 1:
        overlay = cv2.resize(overlay, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out_overlay), overlay, [cv2.IMWRITE_JPEG_QUALITY, 82])

    mask_area = int(cleaned.sum())
    coverage = mask_area / (h * w)
    print(f"  {image_path.name}: iou={iou:.3f}  coverage={coverage:.1%}  {elapsed:.2f}s  -> {out_obj.name}")
    return {
        "path": str(image_path),
        "ok": True,
        "iou": iou,
        "coverage": coverage,
        "elapsed": elapsed,
        "bbox": (x_min, y_min, x_max, y_max),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Single image path")
    parser.add_argument("--batch", help="Folder of JPGs")
    parser.add_argument("--encoder", default=ENCODER_DEFAULT)
    parser.add_argument("--decoder", default=DECODER_DEFAULT)
    parser.add_argument("--out", default="experiments/sam-extraction")
    args = parser.parse_args()

    if not args.image and not args.batch:
        parser.error("Provide --image or --batch")

    extractor = SamExtractor(args.encoder, args.decoder)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.image:
        extract_and_save(extractor, Path(args.image).resolve(), out_dir)
    else:
        folder = Path(args.batch).resolve()
        # Dedupe since Windows FS is case-insensitive (*.JPG and *.jpg match same files)
        images = sorted({p.resolve() for p in list(folder.glob("*.JPG")) + list(folder.glob("*.jpg"))})
        print(f"Found {len(images)} image(s) in {folder}")
        for img in images:
            extract_and_save(extractor, img, out_dir)


if __name__ == "__main__":
    main()
