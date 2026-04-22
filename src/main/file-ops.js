const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const exifr = require('exifr');

const IMAGE_EXTENSIONS = new Set([
  '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.heic', '.heif',
  // RAW formats: Sharp can't decode them, but exifr extracts the embedded
  // JPEG preview for thumbnails (see getSharpInput → extractRawPreview).
  '.cr2', '.cr3', '.nef', '.arw', '.raf', '.rw2',
]);

const RAW_ARCHIVE_FOLDER = '_Raw';
const RAW_EXTENSIONS = new Set(['.cr2', '.cr3', '.nef', '.arw', '.raf', '.rw2', '.heic', '.heif']);

/**
 * Detect true format of a file by reading its header.
 * Returns 'jpeg', 'cr3', 'heic', or 'unknown'.
 */
function detectTrueFormat(filePath) {
  try {
    const fd = fs.openSync(filePath, 'r');
    const buf = Buffer.alloc(12);
    fs.readSync(fd, buf, 0, 12, 0);
    fs.closeSync(fd);

    if (buf[0] === 0xff && buf[1] === 0xd8) return 'jpeg';
    if (buf.slice(4, 8).toString() === 'ftyp') {
      const brand = buf.slice(8, 12).toString();
      if (brand === 'crx ') return 'cr3';
      return 'heic';
    }
    return 'unknown';
  } catch (e) {
    return 'unknown';
  }
}

/**
 * Preserve a raw file in the _Raw/ archive folder before conversion.
 */
function preserveRaw(filePath) {
  const folder = path.dirname(filePath);
  const filename = path.basename(filePath);
  const subfolderName = path.basename(folder);
  const rootFolder = path.dirname(folder);

  const archiveDir = path.join(rootFolder, RAW_ARCHIVE_FOLDER, subfolderName);
  const archivePath = path.join(archiveDir, filename);

  if (fs.existsSync(archivePath)) return true;

  try {
    fs.mkdirSync(archiveDir, { recursive: true });
    fs.copyFileSync(filePath, archivePath);
    return true;
  } catch (err) {
    console.error(`  Could not archive raw ${filename}: ${err.message}`);
    return false;
  }
}

/**
 * Scan a root folder for subfolders containing images.
 * Returns { subfolders: [{ path, name, imageCount }], totalImages, looseImages }.
 * looseImages lists any image files living directly at the root (no subfolder).
 * Used by the Picker to offer "Organize into tablet subfolders" when a user
 * opens a folder that's been renamed but not grouped yet.
 */
function scanFolder(folderPath) {
  const result = { subfolders: [], totalImages: 0, looseImages: [] };

  if (!fs.existsSync(folderPath)) return result;

  const entries = fs.readdirSync(folderPath, { withFileTypes: true });

  for (const entry of entries) {
    if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (IMAGE_EXTENSIONS.has(ext) && !/_mask\.(png|tif|tiff|jpg|jpeg)$/i.test(entry.name)) {
        result.looseImages.push({
          path: path.join(folderPath, entry.name),
          name: entry.name,
          ext,
        });
      }
      continue;
    }
    if (!entry.isDirectory() || entry.name.startsWith('_')) continue;

    const subPath = path.join(folderPath, entry.name);
    let images;
    try {
      images = getImagesInFolder(subPath);
    } catch (err) {
      console.warn(`Skipping ${entry.name}: ${err.message}`);
      continue;
    }

    if (images.length > 0) {
      result.subfolders.push({
        path: subPath,
        name: entry.name,
        imageCount: images.length,
        images: images,
      });
      result.totalImages += images.length;
    }
  }

  // Sort naturally (Si 1, Si 2, ... Si 10, Si 11)
  result.subfolders.sort((a, b) => {
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
  });

  return result;
}

/**
 * Get all image files in a folder.
 */
function getImagesInFolder(folderPath) {
  const files = fs.readdirSync(folderPath);
  const images = [];

  for (const file of files) {
    const ext = path.extname(file).toLowerCase();
    if (IMAGE_EXTENSIONS.has(ext)) {
      // Skip SAM mask files (support files, not photos to process)
      if (/_mask\.(png|tif|tiff|jpg|jpeg)$/i.test(file)) continue;
      const fullPath = path.join(folderPath, file);
      if (fs.statSync(fullPath).isFile()) {
        images.push({
          path: fullPath,
          name: file,
          ext: ext,
          detectedView: detectViewCode(file),
        });
      }
    }
  }

  return images.sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
  );
}

/**
 * Detect if a filename already has a view code suffix.
 * Returns the view code or null.
 */
function detectViewCode(filename) {
  const nameNoExt = path.parse(filename).name;
  const match = nameNoExt.match(/_(0[1-6]|[o][tblr]|[r][tblr])$/i);
  return match ? match[1].toLowerCase() : null;
}

/**
 * Extract the embedded JPEG preview from a raw file (CR3, HEIC, etc.).
 * Canon CR3 files always contain a JPEG thumbnail/preview.
 * Returns a Buffer of the JPEG, or null if extraction fails.
 */
async function extractRawPreview(imagePath) {
  try {
    // exifr.thumbnail() returns a Buffer of the embedded JPEG thumbnail
    const thumbBuf = await exifr.thumbnail(imagePath);
    if (thumbBuf && thumbBuf.length > 100) return thumbBuf;
    return null;
  } catch (err) {
    console.error(`Raw preview extraction error for ${path.basename(imagePath)}: ${err.message}`);
    return null;
  }
}

/**
 * Get a Sharp-readable input for a given image path.
 * For raw files (CR3, HEIC that Sharp can't read), extracts the embedded
 * JPEG preview first. Returns { input, isPreview } where input is either
 * the file path (for supported formats) or a Buffer (for raw previews).
 */
async function getSharpInput(imagePath) {
  const ext = path.extname(imagePath).toLowerCase();
  const isRaw = RAW_EXTENSIONS.has(ext);

  if (!isRaw) {
    return { input: imagePath, isPreview: false };
  }

  // Try Sharp first — it handles HEIC on some builds
  try {
    await sharp(imagePath, { limitInputPixels: false }).metadata();
    return { input: imagePath, isPreview: false };
  } catch (_) {
    // Sharp can't handle this format — extract embedded preview
  }

  const preview = await extractRawPreview(imagePath);
  if (preview) {
    return { input: preview, isPreview: true };
  }

  return { input: null, isPreview: false };
}

/**
 * Generate a thumbnail as base64 data URL.
 */
async function generateThumbnail(imagePath) {
  try {
    const { input } = await getSharpInput(imagePath);
    if (!input) {
      console.error(`Cannot read ${path.basename(imagePath)}: unsupported raw format`);
      return null;
    }

    const buffer = await sharp(input, { limitInputPixels: false })
      .rotate() // auto-apply EXIF orientation
      .resize(250, 250, { fit: 'inside', withoutEnlargement: true })
      .jpeg({ quality: 80 })
      .toBuffer();

    return `data:image/jpeg;base64,${buffer.toString('base64')}`;
  } catch (err) {
    console.error(`Thumbnail error for ${path.basename(imagePath)}: ${err.message}`);
    return null;
  }
}

/**
 * Get basic image info.
 */
async function getImageInfo(imagePath) {
  try {
    const { input } = await getSharpInput(imagePath);
    if (!input) {
      const stats = fs.statSync(imagePath);
      return { width: 0, height: 0, format: path.extname(imagePath).slice(1), size: stats.size };
    }
    const metadata = await sharp(input).metadata();
    const stats = fs.statSync(imagePath);
    return {
      width: metadata.width,
      height: metadata.height,
      format: metadata.format,
      size: stats.size,
    };
  } catch (err) {
    return { width: 0, height: 0, format: 'unknown', size: 0 };
  }
}

/**
 * Rename files based on assignments.
 * assignments: { imagePath: viewCode }
 * Uses two-pass rename (via temp names) to avoid collisions.
 * Only assigned files are renamed — unassigned files are left untouched.
 */
async function renameFiles(subfolderPath, assignments, tabletId, allImagePaths) {
  const results = [];

  console.log(`\n=== RENAME START: ${tabletId} ===`);
  console.log(`  Folder: ${subfolderPath}`);
  console.log(`  Assignments: ${Object.keys(assignments).length}`);

  // Normalize tablet ID: replace spaces with dots (e.g., "Si 10" -> "Si.10")
  const normalizedId = tabletId.replace(/(\w+)\s+(\d+)/g, '$1.$2');

  // Normalize folder name if needed
  if (normalizedId !== tabletId) {
    const parentDir = path.dirname(subfolderPath);
    const newSubfolderPath = path.join(parentDir, normalizedId);
    if (!fs.existsSync(newSubfolderPath)) {
      try {
        fs.renameSync(subfolderPath, newSubfolderPath);
        subfolderPath = newSubfolderPath;
        console.log(`  Normalized folder: "${tabletId}" -> "${normalizedId}"`);
      } catch (err) {
        console.error(`  ERROR normalizing folder: ${err.message}`);
      }
    }
  }

  // Update image paths if folder was renamed
  const updatedAssignments = {};
  for (const [imagePath, viewCode] of Object.entries(assignments)) {
    const fileName = path.basename(imagePath);
    const updatedPath = path.join(subfolderPath, fileName);
    updatedAssignments[updatedPath] = viewCode;
    console.log(`  Assignment: ${fileName} -> _${viewCode}`);
  }

  // Build the rename plan: check what exists, what will collide
  const renamePlan = [];

  for (const [imagePath, viewCode] of Object.entries(updatedAssignments)) {
    if (!fs.existsSync(imagePath)) {
      console.error(`  SKIP: file not found: ${path.basename(imagePath)}`);
      results.push({ oldName: path.basename(imagePath), newName: '?', status: 'error', error: 'File not found' });
      continue;
    }

    const ext = path.extname(imagePath).toLowerCase();
    const trueFormat = detectTrueFormat(imagePath);
    const isRawContent = (trueFormat === 'cr3' || trueFormat === 'heic');
    const isRawExt = RAW_EXTENSIONS.has(ext);
    const needsConversion = isRawExt || isRawContent;
    const outExt = needsConversion ? '.jpg' : ext;
    const finalName = `${normalizedId}_${viewCode}${outExt}`;
    const finalPath = path.join(subfolderPath, finalName);

    // Skip if already has the correct name
    if (path.normalize(imagePath) === path.normalize(finalPath)) {
      console.log(`  SKIP (already correct): ${finalName}`);
      results.push({ oldName: path.basename(imagePath), newName: finalName, status: 'skipped' });
      continue;
    }

    renamePlan.push({
      originalPath: imagePath,
      oldName: path.basename(imagePath),
      finalPath,
      finalName,
      tempPath: path.join(subfolderPath, `_tmp_rename_${viewCode}${ext}`),
      needsConversion,
      trueFormat,
    });
  }

  // Add unassigned files to the plan with "unassigned" suffix
  if (allImagePaths && allImagePaths.length > 0) {
    const assignedPaths = new Set(Object.keys(updatedAssignments));
    let unassignedCount = 0;

    for (const imgPath of allImagePaths) {
      const updatedPath = path.join(subfolderPath, path.basename(imgPath));
      if (assignedPaths.has(updatedPath)) continue;
      if (!fs.existsSync(updatedPath)) continue;

      unassignedCount++;
      const ext = path.extname(updatedPath).toLowerCase();
      const suffix = unassignedCount === 1 ? 'unassigned' : `unassigned_${String(unassignedCount).padStart(2, '0')}`;
      const finalName = `${normalizedId}_${suffix}${ext}`;
      const finalPath = path.join(subfolderPath, finalName);

      if (path.normalize(updatedPath) === path.normalize(finalPath)) {
        results.push({ oldName: path.basename(updatedPath), newName: finalName, status: 'skipped' });
        continue;
      }

      renamePlan.push({
        originalPath: updatedPath,
        oldName: path.basename(updatedPath),
        finalPath,
        finalName,
        tempPath: path.join(subfolderPath, `_tmp_rename_${suffix}${ext}`),
        needsConversion: false,
        trueFormat: 'jpeg',
      });

      console.log(`  Unassigned: ${path.basename(updatedPath)} -> ${finalName}`);
    }
  }

  if (renamePlan.length === 0) {
    console.log('  Nothing to rename.');
    return results;
  }

  // Pass 1: move all assigned files to temp names
  const movedToTemp = [];
  for (const item of renamePlan) {
    try {
      // Preserve raw before moving
      if (item.needsConversion) {
        preserveRaw(item.originalPath);
      }
      fs.renameSync(item.originalPath, item.tempPath);
      movedToTemp.push(item);
      console.log(`  TEMP: ${item.oldName} -> ${path.basename(item.tempPath)}`);
    } catch (err) {
      console.error(`  ERROR moving to temp: ${item.oldName}: ${err.message}`);
      results.push({ oldName: item.oldName, newName: item.finalName, status: 'error', error: err.message });
    }
  }

  // Pass 2: move temp files to final names (with conversion if needed)
  for (const item of movedToTemp) {
    try {
      if (item.needsConversion && item.trueFormat === 'heic') {
        // Convert HEIC to JPEG via sharp (async)
        const buffer = await sharp(item.tempPath).jpeg({ quality: 95 }).toBuffer();
        fs.writeFileSync(item.finalPath, buffer);
        fs.unlinkSync(item.tempPath);
      } else {
        fs.renameSync(item.tempPath, item.finalPath);
      }
      console.log(`  OK: ${item.oldName} -> ${item.finalName}`);
      results.push({ oldName: item.oldName, newName: item.finalName, status: 'ok' });
    } catch (err) {
      console.error(`  ERROR finalizing: ${item.oldName} -> ${item.finalName}: ${err.message}`);
      results.push({ oldName: item.oldName, newName: item.finalName, status: 'error', error: err.message });
      // Restore original name
      try {
        fs.renameSync(item.tempPath, item.originalPath);
        console.log(`  RESTORED: ${item.oldName}`);
      } catch (restoreErr) {
        console.error(`  CRITICAL: Could not restore ${item.oldName}: ${restoreErr.message}`);
      }
    }
  }

  console.log(`=== RENAME DONE: ${results.filter(r => r.status === 'ok').length} ok, ${results.filter(r => r.status === 'error').length} errors ===\n`);
  return results;
}

/**
 * Group loose photos at the root of `folderPath` into per-tablet subfolders.
 *
 * Files matching `<tabletId>_<view>.<ext>` (e.g. "Si.32_01.jpg", "Si.32_ob.cr2")
 * move into `folderPath/<tabletId>/`. The regex below mirrors the stitcher's
 * `generate_subfoldering_pattern()` in stitcher/lib/put_images_in_subfolders.py
 * so the Electron pre-step and the headless stitcher run stay in sync.
 *
 * Files whose stem is a camera-default prefix (IMG, DSC, DSCN, etc.) are
 * intentionally left at root — grouping `IMG_0001.cr2` + `IMG_0002.cr2` into
 * a folder literally named "IMG" would poison the downstream tablet-name
 * plumbing (export → stitcher → metadata all use folder name as tablet ID).
 * The user should group those explicitly with "Group selected into folder…".
 *
 * Non-matching files are left at root, reported in `skipped`. If the target
 * subfolder already exists, files are merged into it (no overwrites — if a
 * same-named file is there, the loose one is left alone and reported in
 * `collisions`).
 *
 * Returns { moved, skipped, collisions } — all arrays of filenames.
 */
function organizeLoosePhotos(folderPath) {
  const VIEW_PATTERN = /^(.+)_(\d+|ot|ob|ol|or|rt|rb|rl|rr|ot\d|ob\d|ol\d|or\d|rt\d|rb\d|rl\d|rr\d|\d{2,3})\.([A-Za-z0-9]+)$/;
  // Generic camera-default stems. Matched case-insensitive; stems equal to
  // one of these are NOT treated as tablet IDs.
  const CAMERA_DEFAULT_STEMS = new Set([
    'IMG', 'DSC', 'DSCN', 'DCIM', 'P', 'MG', 'GOPR', 'PICT', 'SAM',
    'PANA', 'PXL', 'FUJI', 'OLYM',
  ]);

  const result = { moved: [], skipped: [], collisions: [] };
  if (!fs.existsSync(folderPath)) return result;

  const entries = fs.readdirSync(folderPath, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const ext = path.extname(entry.name).toLowerCase();
    if (!IMAGE_EXTENSIONS.has(ext)) continue;
    if (/_mask\.(png|tif|tiff|jpg|jpeg)$/i.test(entry.name)) continue;

    const m = entry.name.match(VIEW_PATTERN);
    if (!m) {
      result.skipped.push(entry.name);
      continue;
    }
    const tabletId = m[1];
    // Reject camera-default stems (IMG, DSC, etc.) — they aren't meaningful
    // tablet IDs. Those files stay loose for manual grouping.
    if (CAMERA_DEFAULT_STEMS.has(tabletId.toUpperCase())) {
      result.skipped.push(entry.name);
      continue;
    }
    const targetDir = path.join(folderPath, tabletId);
    const sourcePath = path.join(folderPath, entry.name);
    const destPath = path.join(targetDir, entry.name);

    try {
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
      } else if (fs.existsSync(destPath)) {
        result.collisions.push(entry.name);
        continue;
      }
      fs.renameSync(sourcePath, destPath);
      result.moved.push(entry.name);
    } catch (err) {
      console.error(`organizeLoosePhotos: failed to move ${entry.name}: ${err.message}`);
      result.skipped.push(entry.name);
    }
  }
  return result;
}

module.exports = { scanFolder, generateThumbnail, renameFiles, getImageInfo, getSharpInput, organizeLoosePhotos };
