const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');

const CONFIG_FILE = 'stitcher-config.json';

// Bundled stitcher artifact name (from GitHub release v2.0-rc.16)
const BUNDLED_EXE_WIN = 'eBL.Photo.Stitcher.exe';
const BUNDLED_APP_MAC = 'eBL Photo Stitcher.app';

/**
 * Resolve the path to the bundled stitcher binary.
 *
 * - Dev (unpackaged): resources/stitcher/ at repo root.
 * - Packaged: process.resourcesPath/stitcher/ (populated via extraResources).
 *
 * Returns the path even if the file doesn't exist — caller should verify.
 */
function isPackaged() {
  try {
    return require('electron').app.isPackaged;
  } catch (e) {
    // Not inside Electron main process (e.g. bare node test) — treat as dev.
    return false;
  }
}

function resolveStitcherPath() {
  const baseDir = isPackaged()
    ? path.join(process.resourcesPath, 'stitcher')
    : path.join(__dirname, '..', '..', 'resources', 'stitcher');

  if (process.platform === 'win32') {
    return path.join(baseDir, BUNDLED_EXE_WIN);
  }
  if (process.platform === 'darwin') {
    // The .app bundle's actual binary is inside Contents/MacOS/
    return path.join(baseDir, BUNDLED_APP_MAC, 'Contents', 'MacOS', 'eBL Photo Stitcher');
  }
  // Linux: no stitcher bundle today. Caller should gate by platform.
  return path.join(baseDir, 'eBL Photo Stitcher');
}

function getConfigPath() {
  const userData = process.env.APPDATA || path.join(os.homedir(), '.config');
  const dir = path.join(userData, 'tablet-image-renamer');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, CONFIG_FILE);
}

function loadStitcherConfig() {
  const configPath = getConfigPath();
  let config = { stitcherExe: '' };
  if (fs.existsSync(configPath)) {
    try {
      config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      if (!config.stitcherExe) {
        config.stitcherExe = config.scriptPath || '';
      }
    } catch (err) {
      console.error('Error loading stitcher config:', err.message);
    }
  }
  // Always prefer the bundled path when it exists. User-configured paths from
  // older versions of the app are ignored (left in the file for rollback).
  const bundled = resolveStitcherPath();
  if (fs.existsSync(bundled)) {
    if (config.stitcherExe && config.stitcherExe !== bundled) {
      console.log(`Ignoring user-configured stitcherExe (${config.stitcherExe}); using bundled binary.`);
    }
    config.stitcherExe = bundled;
  }
  return config;
}

function saveStitcherConfig(config) {
  const configPath = getConfigPath();
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    return true;
  } catch (err) {
    console.error('Error saving stitcher config:', err.message);
    return false;
  }
}

/**
 * Verify the stitcher exe exists. Accepts an explicit path or falls back to
 * the bundled path.
 */
function verifyStitcherExe(exePath) {
  const p = exePath || resolveStitcherPath();
  if (!p) return { valid: false, reason: 'Stitcher path not set' };
  if (!fs.existsSync(p)) return { valid: false, reason: `Bundled stitcher not found at ${p}` };
  return { valid: true, path: p };
}

/**
 * Auto-detect kept for backward compatibility with the existing settings UI.
 * Post-merge, this always returns the bundled path (if it exists).
 */
function autoDetectStitcherExe() {
  const bundled = resolveStitcherPath();
  if (fs.existsSync(bundled)) return bundled;
  return null;
}

/**
 * Run the stitcher exe in headless mode.
 * The exe is called with: --headless --root <folder> --json-progress [--tablets <name1> <name2> ...]
 * onProgress receives log events: { type, message }
 * Returns a promise: { success, exitCode, error? }
 *
 * If exePath is empty or invalid, falls back to the bundled binary.
 */
function runStitcherHeadless(exePath, rootFolder, tablets, onProgress) {
  return new Promise((resolve) => {
    // Resolve path: explicit arg → bundled fallback
    let resolved = exePath;
    if (!resolved || !fs.existsSync(resolved)) {
      resolved = resolveStitcherPath();
    }

    const verification = verifyStitcherExe(resolved);
    if (!verification.valid) {
      resolve({ success: false, error: verification.reason });
      return;
    }

    const args = ['--headless', '--root', rootFolder, '--json-progress'];

    if (tablets && tablets.length > 0) {
      args.push('--tablets', ...tablets);
    }

    console.log(`Running stitcher: "${resolved}" ${args.join(' ')}`);

    const proc = spawn(resolved, args, {
      cwd: path.dirname(resolved),
      env: { ...process.env },
    });

    let stdoutBuffer = '';

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdoutBuffer += text;

      const lines = stdoutBuffer.split('\n');
      stdoutBuffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('{')) {
          try {
            const event = JSON.parse(trimmed);
            if (onProgress) onProgress(event);
            continue;
          } catch (e) { /* not JSON */ }
        }

        if (onProgress) onProgress({ type: 'log', message: trimmed });
      }
    });

    proc.stderr.on('data', (data) => {
      if (onProgress) onProgress({ type: 'stderr', message: data.toString() });
    });

    proc.on('error', (err) => {
      console.error('Stitcher process error:', err.message);
      resolve({ success: false, error: err.message });
    });

    proc.on('exit', (code) => {
      console.log(`Stitcher exited with code ${code}`);
      if (onProgress) onProgress({ type: 'exit', code });
      resolve({ success: code === 0, exitCode: code });
    });
  });
}

module.exports = {
  resolveStitcherPath,
  loadStitcherConfig,
  saveStitcherConfig,
  verifyStitcherExe,
  autoDetectStitcherExe,
  runStitcherHeadless,
};
