const path = require('path');
const fs = require('fs');
const os = require('os');

/**
 * Electron-managed user-data directory. Derives from productName in
 * package.json, which we set to "eBL Tablet Studio".
 *   Windows: %APPDATA%/eBL Tablet Studio/
 *   macOS:   ~/Library/Application Support/eBL Tablet Studio/
 *   Linux:   ~/.config/eBL Tablet Studio/
 *
 * Only callable after `app.ready` has fired. Functions that might run earlier
 * (during module import) should not call this at top level.
 */
function getUserDataDir() {
  const { app } = require('electron');
  const dir = app.getPath('userData');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Pre-merge directory layout. Used as the source for the one-time migration
 * below. Left in place after migration so users can roll back to the old
 * tablet-image-renamer if needed.
 */
function getLegacyUserDataDir() {
  const base = process.env.APPDATA
    || (process.platform === 'darwin'
      ? path.join(os.homedir(), 'Library', 'Application Support')
      : path.join(os.homedir(), '.config'));
  return path.join(base, 'tablet-image-renamer');
}

/**
 * Copy known config files from the legacy dir to the new one, once.
 * Idempotent: only copies if the destination file doesn't already exist.
 * Logs what it did; doesn't throw on individual file failures.
 */
function migrateLegacyUserData() {
  const legacy = getLegacyUserDataDir();
  if (!fs.existsSync(legacy)) return { migrated: 0, legacy, reason: 'no legacy dir' };

  const current = getUserDataDir();
  const filesToMigrate = ['user.json', 'saved-histories.json', 'stitcher-config.json'];
  const dirsToMigrate = ['seg-weights'];
  let migrated = 0;

  for (const f of filesToMigrate) {
    const src = path.join(legacy, f);
    const dst = path.join(current, f);
    if (fs.existsSync(src) && !fs.existsSync(dst)) {
      try {
        fs.copyFileSync(src, dst);
        console.log(`[migrate] copied ${src} -> ${dst}`);
        migrated++;
      } catch (e) {
        console.error(`[migrate] failed to copy ${src}: ${e.message}`);
      }
    }
  }

  for (const d of dirsToMigrate) {
    const src = path.join(legacy, d);
    const dst = path.join(current, d);
    if (fs.existsSync(src) && !fs.existsSync(dst)) {
      try {
        fs.cpSync(src, dst, { recursive: true });
        console.log(`[migrate] copied dir ${src} -> ${dst}`);
        migrated++;
      } catch (e) {
        console.error(`[migrate] failed to copy dir ${src}: ${e.message}`);
      }
    }
  }

  if (migrated > 0) {
    console.log(`[migrate] done: ${migrated} item(s) from ${legacy} to ${current}`);
  }
  return { migrated, legacy, current };
}

module.exports = { getUserDataDir, getLegacyUserDataDir, migrateLegacyUserData };
