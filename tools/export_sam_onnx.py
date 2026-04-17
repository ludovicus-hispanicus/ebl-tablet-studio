"""
Export MobileSAM to ONNX (image encoder + prompt decoder as two files).

Dev-time tool, not shipped in the bundled app. Run once per model update
to regenerate ONNX artifacts. The shipped runtime uses onnxruntime only;
torch is a dev dependency exclusively for this export.

Usage:
    python tools/export_sam_onnx.py [--weights PATH] [--out DIR]

Defaults:
    --weights  python/weights/mobile_sam.pt   (already present in repo)
    --out      experiments/sam-onnx/           (gitignored)

Outputs:
    <out>/mobile_sam_encoder.onnx   (~40 MB)  image embedding
    <out>/mobile_sam_decoder.onnx   (~16 MB)  prompt -> mask
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import torch
from mobile_sam import sam_model_registry
from mobile_sam.utils.onnx import SamOnnxModel


def export_encoder(sam, out_path: Path) -> None:
    """
    Image encoder: (1, 3, 1024, 1024) -> (1, 256, 64, 64) image embedding.
    Input is a preprocessed image (resized+padded to 1024, normalized).
    """
    image_encoder = sam.image_encoder
    image_encoder.eval()

    dummy = torch.zeros(1, 3, sam.image_encoder.img_size, sam.image_encoder.img_size)

    torch.onnx.export(
        image_encoder,
        dummy,
        str(out_path),
        input_names=["images"],
        output_names=["image_embeddings"],
        opset_version=17,
        do_constant_folding=True,
        # Static shapes — matches SAM's preprocess convention of always
        # feeding 1024x1024.
    )
    print(f"  encoder: {out_path}  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")


def export_decoder(sam, out_path: Path) -> None:
    """
    Prompt decoder: (image_embeddings, points, labels, mask_input, has_mask, orig_size)
    -> (masks, iou_predictions, low_res_masks)
    """
    onnx_model = SamOnnxModel(
        model=sam,
        return_single_mask=False,          # return 3 mask candidates
        use_stability_score=False,
        return_extra_metrics=False,
    )
    onnx_model.eval()

    embed_dim = sam.prompt_encoder.embed_dim
    embed_size = sam.prompt_encoder.image_embedding_size
    mask_input_size = [4 * x for x in embed_size]

    dummy_inputs = {
        "image_embeddings": torch.randn(1, embed_dim, *embed_size, dtype=torch.float),
        "point_coords": torch.randint(low=0, high=1024, size=(1, 5, 2), dtype=torch.float),
        "point_labels": torch.randint(low=0, high=4, size=(1, 5), dtype=torch.float),
        "mask_input": torch.randn(1, 1, *mask_input_size, dtype=torch.float),
        "has_mask_input": torch.tensor([1], dtype=torch.float),
        "orig_im_size": torch.tensor([1500, 2250], dtype=torch.float),
    }
    output_names = ["masks", "iou_predictions", "low_res_masks"]

    # Dynamic axes so point_coords/point_labels and orig_im_size can vary per call.
    dynamic_axes = {
        "point_coords": {1: "num_points"},
        "point_labels": {1: "num_points"},
    }

    with torch.no_grad():
        torch.onnx.export(
            onnx_model,
            tuple(dummy_inputs.values()),
            str(out_path),
            input_names=list(dummy_inputs.keys()),
            output_names=output_names,
            opset_version=17,
            do_constant_folding=True,
            dynamic_axes=dynamic_axes,
        )
    print(f"  decoder: {out_path}  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weights", default="python/weights/mobile_sam.pt",
                        help="Path to mobile_sam.pt")
    parser.add_argument("--out", default="experiments/sam-onnx",
                        help="Output directory for ONNX files")
    args = parser.parse_args()

    weights_path = Path(args.weights).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not weights_path.exists():
        print(f"ERROR: weights not found at {weights_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading MobileSAM from {weights_path}")
    sam = sam_model_registry["vit_t"](checkpoint=str(weights_path))
    sam.eval()

    print(f"Exporting to {out_dir}")
    export_encoder(sam, out_dir / "mobile_sam_encoder.onnx")
    export_decoder(sam, out_dir / "mobile_sam_decoder.onnx")
    print("Done.")


if __name__ == "__main__":
    main()
