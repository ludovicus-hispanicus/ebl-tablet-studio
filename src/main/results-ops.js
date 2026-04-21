const fs = require('fs');
const path = require('path');
const exifr = require('exifr');
const sharp = require('sharp');

const FINAL_JPG_FOLDER = '_Final_JPG';
const FINAL_TIFF_FOLDER = '_Final_TIFF';
const FINAL_JPG_PRINT_FOLDER = '_Final_JPG_Print';
const FINAL_TIFF_PRINT_FOLDER = '_Final_TIFF_Print';
const REVIEW_STATUS_FILE = 'review_status.json';
const PROJECT_NOTES_FILE = 'project_notes.json';

// Scan one variant's JPG folder and attach TIFF pairs.
function collectVariantEntries(jpgDir, tiffDir, variant) {
  if (!fs.existsSync(jpgDir)) return [];
  const jpgFiles = fs.readdirSync(jpgDir).filter(f => /\.(jpg|jpeg)$/i.test(f));
  jpgFiles.sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
  );

  const tiffList = fs.existsSync(tiffDir) ? fs.readdirSync(tiffDir) : [];

  return jpgFiles.map(file => {
    const baseName = path.parse(file).name;
    const jpgPath = path.join(jpgDir, file);
    const tiffFile = tiffList.find(f =>
      path.parse(f).name === baseName && /\.(tif|tiff)$/i.test(f)
    );
    return {
      name: baseName,
      jpgPath,
      tiffPath: tiffFile ? path.join(tiffDir, tiffFile) : null,
      variant,
    };
  });
}

/**
 * Scan for stitched results in _Final_JPG (digital) and _Final_JPG_Print (print).
 * Returns { hasResults, results: [{ name, jpgPath, tiffPath, variant }] }.
 * Digital entries come first, then print — both keyed by tablet name so the
 * renderer can share review status across variants.
 */
function scanResults(rootFolder) {
  const jpgFolder = path.join(rootFolder, FINAL_JPG_FOLDER);
  const tiffFolder = path.join(rootFolder, FINAL_TIFF_FOLDER);
  const jpgPrintFolder = path.join(rootFolder, FINAL_JPG_PRINT_FOLDER);
  const tiffPrintFolder = path.join(rootFolder, FINAL_TIFF_PRINT_FOLDER);

  const digital = collectVariantEntries(jpgFolder, tiffFolder, 'digital');
  const print = collectVariantEntries(jpgPrintFolder, tiffPrintFolder, 'print');

  const results = [...digital, ...print];

  return {
    hasResults: results.length > 0,
    results,
    jpgFolder,
    tiffFolder,
    jpgPrintFolder,
    tiffPrintFolder,
  };
}

/**
 * Load review status. Checks root folder first, then legacy _Final_JPG/ location.
 * Returns { tabletName: { status, notes, reviewedBy, reviewedAt } }
 */
function loadReviewStatus(rootFolder) {
  // Primary: root-level file
  const rootFile = path.join(rootFolder, REVIEW_STATUS_FILE);
  if (fs.existsSync(rootFile)) {
    try {
      return JSON.parse(fs.readFileSync(rootFile, 'utf8'));
    } catch (err) {
      console.error('Error loading review status:', err.message);
    }
  }

  // Legacy: _Final_JPG/review_status.json
  const legacyFile = path.join(rootFolder, FINAL_JPG_FOLDER, REVIEW_STATUS_FILE);
  if (fs.existsSync(legacyFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(legacyFile, 'utf8'));
      // Migrate: save to root level
      saveReviewStatus(rootFolder, data);
      return data;
    } catch (err) {
      console.error('Error loading legacy review status:', err.message);
    }
  }

  return {};
}

/**
 * Save review status to root folder (review_status.json).
 */
function saveReviewStatus(rootFolder, status) {
  const statusFile = path.join(rootFolder, REVIEW_STATUS_FILE);

  try {
    fs.writeFileSync(statusFile, JSON.stringify(status, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Error saving review status:', err.message);
    return false;
  }
}

// Unwrap XMP AltLang objects ({lang, value}) and arrays into plain strings.
// Returns null for empty/missing values so the caller can drop them.
function normalizeExifValue(v) {
  if (v === undefined || v === null || v === '') return null;
  if (v instanceof Date) return v.toISOString();
  if (Array.isArray(v)) {
    const parts = v.map(normalizeExifValue).filter(x => x !== null && x !== '');
    return parts.length ? parts.join(', ') : null;
  }
  if (typeof v === 'object') {
    if ('value' in v) return normalizeExifValue(v.value);
    return null;
  }
  return v;
}

// Classify a tag name into its originating metadata container.
// exifr returns everything flat with tag-name aliases, so we decide by name.
const EXIF_FIELDS = new Set([
  'Make', 'Model', 'Software', 'Artist', 'Copyright', 'ImageDescription',
  'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
  'XResolution', 'YResolution', 'ResolutionUnit',
  'Orientation', 'YCbCrPositioning', 'ColorSpace',
  'ExifImageWidth', 'ExifImageHeight', 'PixelXDimension', 'PixelYDimension',
  'ExposureTime', 'FNumber', 'ISO', 'FocalLength', 'LensModel',
]);
const IPTC_FIELDS = new Set([
  'ObjectName', 'Headline', 'Caption', 'CaptionAbstract', 'Byline',
  'BylineTitle', 'Credit', 'Source', 'CopyrightNotice', 'Keywords',
  'DateCreated', 'TimeCreated', 'City', 'Country', 'ProvinceState',
  'SpecialInstructions', 'Category', 'SupplementalCategories', 'Writer',
]);
function classifyField(name) {
  if (EXIF_FIELDS.has(name)) return 'EXIF';
  if (IPTC_FIELDS.has(name)) return 'IPTC';
  return 'XMP';
}

/**
 * Read file stats + dimensions + EXIF/XMP for a stitched result JPG.
 * Returns a flat object suitable for display; missing fields are omitted.
 */
async function getResultMetadata(imagePath) {
  const out = { filePath: imagePath };

  try {
    const stats = fs.statSync(imagePath);
    out.sizeBytes = stats.size;
    out.modifiedAt = stats.mtime.toISOString();
  } catch (e) { /* file may not exist */ }

  try {
    const meta = await sharp(imagePath, { limitInputPixels: false }).metadata();
    out.width = meta.width;
    out.height = meta.height;
    out.format = meta.format;
  } catch (e) { /* unreadable */ }

  // Parse all segments; try a few option shapes because different files
  // respond differently (some have EXIF but no XMP, some the reverse, etc.).
  try {
    let flat = null;
    const attempts = [
      { tiff: true, xmp: true, iptc: true, icc: false },                 // EXIF+XMP+IPTC
      { tiff: true, exif: true, xmp: true, iptc: true, icc: false },     // explicit ExifIFD
      true,                                                               // "parse everything"
    ];
    for (const opts of attempts) {
      try {
        const r = await exifr.parse(imagePath, opts);
        if (r && Object.keys(r).length > 0) { flat = r; break; }
      } catch (_) { /* try next shape */ }
    }

    if (flat) {
      const sections = { EXIF: {}, XMP: {}, IPTC: {} };
      for (const [k, v] of Object.entries(flat)) {
        if (k.startsWith('_')) continue;
        const n = normalizeExifValue(v);
        if (n === null || n === '') continue;
        const bucket = classifyField(k);
        sections[bucket][k] = n;
      }
      const kept = {};
      for (const name of ['EXIF', 'XMP', 'IPTC']) {
        if (Object.keys(sections[name]).length > 0) kept[name] = sections[name];
      }
      if (Object.keys(kept).length > 0) out.sections = kept;
      out._rawKeys = Object.keys(flat);
    }
  } catch (e) {
    out._exifrError = e.message;
  }

  return out;
}

/**
 * Load batch-level ("dashboard") notes scoped to this results folder.
 * Returns { notes: '' } if the file doesn't exist yet.
 */
function loadProjectNotes(rootFolder) {
  const filePath = path.join(rootFolder, PROJECT_NOTES_FILE);
  if (!fs.existsSync(filePath)) return { notes: '' };
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return { notes: typeof data?.notes === 'string' ? data.notes : '' };
  } catch (err) {
    console.error('Error loading project notes:', err.message);
    return { notes: '' };
  }
}

/**
 * Save batch-level notes for this results folder. Empty string removes the
 * file so there's no empty-placeholder clutter in the folder.
 */
function saveProjectNotes(rootFolder, notes) {
  const filePath = path.join(rootFolder, PROJECT_NOTES_FILE);
  try {
    if (!notes || !notes.trim()) {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
      return true;
    }
    fs.writeFileSync(filePath, JSON.stringify({ notes }, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Error saving project notes:', err.message);
    return false;
  }
}

module.exports = {
  scanResults,
  loadReviewStatus,
  saveReviewStatus,
  getResultMetadata,
  loadProjectNotes,
  saveProjectNotes,
};
