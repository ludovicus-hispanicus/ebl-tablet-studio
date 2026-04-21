#!/usr/bin/env node
// Rebuild the bundled stitcher .exe from the vendored Python source.
//
// Prereqs (one-time):
//   - Python 3.10–3.12 on PATH (or activate a venv first)
//   - pip install -r stitcher/requirements.txt pyinstaller
//
// Usage:
//   npm run build-stitcher
//
// Writes the result to resources/stitcher/eBL.Photo.Stitcher.exe on Windows,
// or the .app bundle on macOS. Does NOT publish or release — this is a local
// build you run when you're ready to ship a new stitcher version.

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const stitcherDir = path.join(repoRoot, 'stitcher');
const resourcesDir = path.join(repoRoot, 'resources', 'stitcher');
const isWin = process.platform === 'win32';
const isMac = process.platform === 'darwin';
const specFile = isMac ? 'eBL_Photo_Stitcher_MacOS.spec' : 'eBL_Photo_Stitcher.spec';

if (!fs.existsSync(path.join(stitcherDir, specFile))) {
  console.error(`Spec not found: stitcher/${specFile}`);
  process.exit(1);
}

console.log(`> Building stitcher from stitcher/${specFile}`);
console.log(`  (cwd: ${stitcherDir})`);

// Prefer the venv python if it exists, fall back to PATH.
function pickPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venv = path.join(stitcherDir, '.venv', isWin ? 'Scripts/python.exe' : 'bin/python');
  if (fs.existsSync(venv)) return venv;
  return isWin ? 'python' : 'python3';
}
const python = pickPython();
console.log(`  python: ${python}`);
const build = spawnSync(python, ['-m', 'PyInstaller', '--noconfirm', specFile], {
  cwd: stitcherDir,
  stdio: 'inherit',
});

if (build.status !== 0) {
  console.error('\nPyInstaller failed. If PyInstaller is not installed:');
  console.error('  pip install -r stitcher/requirements.txt pyinstaller');
  process.exit(build.status || 1);
}

// Locate the built artifact and copy it into resources/stitcher/.
// Each platform has a different layout:
//   Windows: dist/eBL Photo Stitcher.exe       (single file)
//   Linux:   dist/eBL Photo Stitcher           (single file)
//   macOS:   dist/eBL Photo Stitcher.app/      (directory bundle; runtime
//            bridge expects the .app laid out intact under resources/stitcher/)
const distDir = path.join(stitcherDir, 'dist');
fs.mkdirSync(resourcesDir, { recursive: true });

let target;
if (isMac) {
  const distApp = path.join(distDir, 'eBL Photo Stitcher.app');
  if (!fs.existsSync(distApp)) {
    console.error(`\nBuild succeeded but expected .app not found: ${distApp}`);
    process.exit(1);
  }
  target = path.join(resourcesDir, 'eBL Photo Stitcher.app');
  // cpSync preserves symlinks & permissions inside the .app bundle —
  // copyFileSync only handles regular files.
  fs.rmSync(target, { recursive: true, force: true });
  fs.cpSync(distApp, target, { recursive: true, dereference: false });
} else {
  const distExe = path.join(distDir, isWin ? 'eBL Photo Stitcher.exe' : 'eBL Photo Stitcher');
  if (!fs.existsSync(distExe)) {
    console.error(`\nBuild succeeded but expected output not found: ${distExe}`);
    process.exit(1);
  }
  target = path.join(resourcesDir, isWin ? 'eBL.Photo.Stitcher.exe' : 'eBL.Photo.Stitcher');
  fs.copyFileSync(distExe, target);
}

console.log(`\n✓ Wrote ${path.relative(repoRoot, target)}`);
console.log('  Next: relaunch the app and reprocess a tablet to pick up the new binary.');
