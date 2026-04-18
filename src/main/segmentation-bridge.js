/**
 * Segmentation bridge — thin wrapper over the in-process SAM ONNX module.
 *
 * Replaces the previous Python-subprocess bridge. Users no longer need
 * Python installed for SAM segmentation; ONNX inference runs inside the
 * Electron main process via onnxruntime-node.
 *
 * Public API (unchanged from the Python-subprocess era so ipc handlers
 * and the renderer don't need to care):
 *   startServer(onProgress)   → {success, error?}
 *   stopServer()              → void
 *   isServerReady()           → boolean
 *   encodeImage(path)         → {status, width, height} | {status:'error', error}
 *   predictMask(box, pos, neg) → {mask: base64, score}  | {status:'error', error}
 */

const sam = require('./sam-onnx');

async function startServer(onProgress) {
  if (sam.isReady()) return { success: true };
  if (onProgress) onProgress({ type: 'status', message: 'Loading MobileSAM (ONNX)\u2026' });

  const t0 = Date.now();
  const result = await sam.init();
  const ms = Date.now() - t0;
  if (result.success) {
    console.log(`[seg-bridge] SAM ONNX sessions loaded in ${ms} ms`);
    if (onProgress) onProgress({ type: 'status', message: `SAM ready (${ms} ms)` });
  } else {
    console.error('[seg-bridge] SAM init failed:', result.error);
    if (onProgress) onProgress({ type: 'log', message: `SAM init failed: ${result.error}` });
  }
  return result;
}

function stopServer() {
  if (sam.isReady()) {
    sam.dispose();
    console.log('[seg-bridge] SAM sessions disposed');
  }
}

function isServerReady() {
  return sam.isReady();
}

async function encodeImage(imagePath) {
  try {
    return await sam.encode(imagePath);
  } catch (err) {
    console.error('[seg-bridge] encode error:', err.message);
    return { status: 'error', error: err.message };
  }
}

async function predictMask(box, positivePoints, negativePoints) {
  try {
    return await sam.predict({ box, positivePoints, negativePoints });
  } catch (err) {
    console.error('[seg-bridge] predict error:', err.message);
    return { status: 'error', error: err.message };
  }
}

module.exports = {
  startServer,
  stopServer,
  isServerReady,
  encodeImage,
  predictMask,
};
