/**
 * MobileSAM via onnxruntime-node — in-process SAM inference, no Python.
 *
 * Replaces the old segmentation_server.py subprocess with a pure-Node
 * implementation. Models live at resources/models/sam/ (dev: repo-local).
 *
 * Public API (matches the old Python server shape so segmentation-bridge.js
 * can swap over without API changes):
 *   init()            → {success: true} | {success: false, error}
 *   encode(path)      → {status: 'ready', width, height}
 *   predict({box, positivePoints, negativePoints})
 *                     → {mask: base64-png, score}
 *   dispose()
 *   isReady()
 */

const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const ort = require('onnxruntime-node');

const MODEL_INPUT_SIZE = 1024;
// ImageNet statistics — SAM's standard preprocessing.
const MEAN = [123.675, 116.28, 103.53];
const STD = [58.395, 57.12, 57.375];

let encoderSession = null;
let decoderSession = null;

// Per-image encoding cache (mirrors SamPredictor.set_image).
let currentImage = null; // { path, origH, origW, scale, embedding }

function isPackaged() {
  try {
    return require('electron').app.isPackaged;
  } catch (e) {
    return false;
  }
}

function resolveModelPath(filename) {
  // Dev: repo's resources/models/sam/  Packaged: process.resourcesPath/models/sam/
  const base = isPackaged()
    ? path.join(process.resourcesPath, 'models', 'sam')
    : path.join(__dirname, '..', '..', 'resources', 'models', 'sam');
  return path.join(base, filename);
}

async function init() {
  if (encoderSession && decoderSession) return { success: true };

  const encoderPath = resolveModelPath('mobile_sam_encoder.onnx');
  const decoderPath = resolveModelPath('mobile_sam_decoder.onnx');
  if (!fs.existsSync(encoderPath) || !fs.existsSync(decoderPath)) {
    return {
      success: false,
      error: `SAM ONNX models not found at ${encoderPath}`,
    };
  }

  try {
    const opts = { executionProviders: ['cpu'] };
    encoderSession = await ort.InferenceSession.create(encoderPath, opts);
    decoderSession = await ort.InferenceSession.create(decoderPath, opts);
    return { success: true };
  } catch (err) {
    encoderSession = null;
    decoderSession = null;
    return { success: false, error: `Failed to load SAM ONNX sessions: ${err.message}` };
  }
}

function isReady() {
  return !!(encoderSession && decoderSession);
}

function dispose() {
  // onnxruntime-node sessions don't require explicit release, but we clear refs.
  encoderSession = null;
  decoderSession = null;
  currentImage = null;
}

/**
 * Preprocess: read image, resize longest edge to 1024, ImageNet-normalize,
 * pad to 1024x1024 with zeros, transpose HWC→CHW. Returns a Float32Array
 * of shape (1, 3, 1024, 1024) plus the scale/original-size metadata needed
 * to remap point prompts.
 */
async function preprocess(imagePath) {
  const img = sharp(imagePath).rotate(); // honor EXIF orientation
  const meta = await img.metadata();
  const origW = meta.width;
  const origH = meta.height;
  if (!origW || !origH) throw new Error('Could not read image dimensions');

  const scale = MODEL_INPUT_SIZE / Math.max(origW, origH);
  const newW = Math.round(origW * scale);
  const newH = Math.round(origH * scale);

  const { data } = await img
    .resize(newW, newH, { kernel: sharp.kernel.lanczos3, fit: 'fill' })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  // Build the 1024x1024x3 normalized + padded tensor in CHW layout.
  const tensor = new Float32Array(3 * MODEL_INPUT_SIZE * MODEL_INPUT_SIZE);
  const plane = MODEL_INPUT_SIZE * MODEL_INPUT_SIZE;
  for (let y = 0; y < newH; y++) {
    for (let x = 0; x < newW; x++) {
      const src = (y * newW + x) * 3;
      const dst = y * MODEL_INPUT_SIZE + x;
      tensor[0 * plane + dst] = (data[src + 0] - MEAN[0]) / STD[0];
      tensor[1 * plane + dst] = (data[src + 1] - MEAN[1]) / STD[1];
      tensor[2 * plane + dst] = (data[src + 2] - MEAN[2]) / STD[2];
    }
  }
  // Remaining pixels default to 0.0, which is what SAM expects for padding.

  return { tensor, origH, origW, scale };
}

async function encode(imagePath) {
  if (!isReady()) {
    const r = await init();
    if (!r.success) return { status: 'error', error: r.error };
  }
  const { tensor, origH, origW, scale } = await preprocess(imagePath);

  const inputTensor = new ort.Tensor('float32', tensor, [1, 3, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE]);
  const output = await encoderSession.run({ images: inputTensor });
  const embedding = output.image_embeddings;

  currentImage = { path: imagePath, origH, origW, scale, embedding };
  return { status: 'ready', width: origW, height: origH };
}

/**
 * Build SAM's prompt tensors. Points are remapped from original image
 * coordinates to the 1024-input space. A box is encoded as two points
 * with labels (2=top-left, 3=bottom-right). If no points are provided,
 * SAM requires an "empty" sentinel point (0,0) with label -1.
 */
function buildPromptTensors(positivePoints, negativePoints, box, scale) {
  const coords = [];
  const labels = [];

  for (const p of positivePoints || []) {
    coords.push([p.x * scale, p.y * scale]);
    labels.push(1);
  }
  for (const p of negativePoints || []) {
    coords.push([p.x * scale, p.y * scale]);
    labels.push(0);
  }
  if (box) {
    coords.push([box.x1 * scale, box.y1 * scale]);
    labels.push(2);
    coords.push([box.x2 * scale, box.y2 * scale]);
    labels.push(3);
  } else {
    // SAM ONNX model requires at least one more point when no box; append
    // the "empty" sentinel it expects (0,0) with label -1.
    coords.push([0, 0]);
    labels.push(-1);
  }

  const n = labels.length;
  const coordsFlat = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    coordsFlat[i * 2] = coords[i][0];
    coordsFlat[i * 2 + 1] = coords[i][1];
  }
  const labelsFlat = new Float32Array(labels);

  return {
    point_coords: new ort.Tensor('float32', coordsFlat, [1, n, 2]),
    point_labels: new ort.Tensor('float32', labelsFlat, [1, n]),
  };
}

async function maskToPngBase64(maskLogits, h, w) {
  // maskLogits: Float32Array of length h*w (one plane). Threshold at 0 for binary.
  const binary = new Uint8Array(h * w);
  for (let i = 0; i < binary.length; i++) {
    binary[i] = maskLogits[i] > 0 ? 255 : 0;
  }
  const buf = await sharp(binary, { raw: { width: w, height: h, channels: 1 } })
    .png()
    .toBuffer();
  return buf.toString('base64');
}

async function predict({ box, positivePoints, negativePoints }) {
  if (!currentImage) {
    return { status: 'error', error: 'No image encoded' };
  }
  const { origH, origW, scale, embedding } = currentImage;

  const prompts = buildPromptTensors(positivePoints, negativePoints, box, scale);
  const emptyMask = new Float32Array(1 * 1 * 256 * 256);

  const feeds = {
    image_embeddings: embedding,
    point_coords: prompts.point_coords,
    point_labels: prompts.point_labels,
    mask_input: new ort.Tensor('float32', emptyMask, [1, 1, 256, 256]),
    has_mask_input: new ort.Tensor('float32', new Float32Array([0]), [1]),
    orig_im_size: new ort.Tensor('float32', new Float32Array([origH, origW]), [2]),
  };

  const output = await decoderSession.run(feeds);
  const masks = output.masks;    // shape: (1, N, H, W)
  const ious = output.iou_predictions; // shape: (1, N)
  const [_, numMasks, h, w] = masks.dims;

  // Pick highest-IoU mask
  const iouData = ious.data;
  let bestIdx = 0;
  for (let i = 1; i < numMasks; i++) {
    if (iouData[i] > iouData[bestIdx]) bestIdx = i;
  }
  const planeSize = h * w;
  const maskData = masks.data;
  const bestPlane = new Float32Array(planeSize);
  for (let i = 0; i < planeSize; i++) {
    bestPlane[i] = maskData[bestIdx * planeSize + i];
  }

  const maskBase64 = await maskToPngBase64(bestPlane, h, w);
  return { mask: maskBase64, score: iouData[bestIdx] };
}

module.exports = { init, encode, predict, dispose, isReady };
