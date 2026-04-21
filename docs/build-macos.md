# Build eBL Tablet Studio for macOS — AI-pilot guide

This document is written so a non-technical user can hand it to an AI coding
assistant (e.g. Claude Code) and say:

> "Read `docs/build-macos.md` and follow it end-to-end to produce the macOS
> artifacts for the current release, then upload them to the GitHub release
> matching the current `package.json` version."

The AI should be able to execute the steps below without asking clarifying
questions. Every command is literal — copy it as-is.

If you are the AI reading this: work through the sections in order. Run
preflight checks before committing to the long-running build. Report a
single-paragraph summary at the end with the produced file paths and any
warnings that appeared during the build.

---

## 0. Scope and constraints

- Target: **Apple Silicon (arm64)** macOS 12 (Monterey) or newer.
- Output artifacts: a `.dmg` installer and the auto-update metadata
  (`latest-mac.yml`, `latest-mac.yml.blockmap`) expected by `electron-updater`.
- Code signing is intentionally **disabled** (`identity: null` in
  `package.json`'s `build.mac`). The resulting DMG will trigger Gatekeeper on
  first launch; users must right-click → Open. Do not enable signing without
  an explicit request.
- Intel Mac (x64) builds are NOT produced. If the user asks for one, stop and
  tell them this needs a separate `package.json` target configuration.

## 1. Preflight checks

Run each of these. If any fails, stop and report which one to the user.

```bash
# Must be on macOS
uname -s                              # expect: Darwin

# Must be Apple Silicon
uname -m                              # expect: arm64

# Node + npm available, Node 18+ ideal
node --version                        # expect: v18.x or newer
npm --version

# Python 3.10–3.12 available (PyInstaller + deps support this range best)
python3 --version                     # expect: Python 3.10.x / 3.11.x / 3.12.x
python3 -m pip --version

# git + gh CLI
git --version
gh --version
gh auth status                        # must show "Logged in to github.com"

# Current working directory must be the repo root
test -f package.json && test -d stitcher && test -d src/main \
  && echo "repo root OK" || echo "WRONG directory — cd to repo root"

# Must be on a clean working tree (no uncommitted changes)
test -z "$(git status --porcelain)" \
  && echo "clean tree OK" || { echo "UNCOMMITTED CHANGES — stop and report"; git status --short; }
```

## 2. Install dependencies

```bash
# Node dependencies (uses the exact versions from package-lock.json)
npm ci

# Python venv for the stitcher build (keeps system Python clean)
python3 -m venv stitcher/.venv
source stitcher/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r stitcher/requirements.txt pyinstaller
deactivate
```

Expected time: 3–8 minutes depending on network. Python installs will pull in
ONNX Runtime, rembg, OpenCV, Pillow, and their transitives — that is normal.

## 3. Build the bundled stitcher

The Electron app invokes the stitcher as an external process, so this step
must happen BEFORE `electron-builder` packages the app.

```bash
# Tell the build script to use the venv we just created
export PYTHON="$(pwd)/stitcher/.venv/bin/python"

# Build via the existing script (uses stitcher/eBL_Photo_Stitcher_MacOS.spec)
npm run build-stitcher
```

Expected output at the end:
```
✓ Wrote resources/stitcher/eBL.Photo.Stitcher
  Next: relaunch the app and reprocess a tablet to pick up the new binary.
```

Verify:
```bash
test -x "resources/stitcher/eBL.Photo.Stitcher" \
  && echo "stitcher binary OK" || echo "stitcher binary MISSING — stop and report"
```

Typical size: ~180 MB executable (non-signed Mach-O arm64).

## 4. Build the macOS DMG

```bash
npm run dist:mac
```

Expected time: 5–15 minutes. During the run you will see electron-builder
download the Electron 31.x runtime for darwin-arm64 on first build (cached
after), codesign with `null` identity (a no-op), package the `.app`, and
compress into a `.dmg`.

Artifacts will be written to `dist/`. Verify:

```bash
ls -la dist/*.dmg dist/latest-mac.yml* 2>&1
```

Expected files (names contain the version from `package.json`):
```
dist/eBL_Tablet_Studio-<version>-mac-arm64.dmg
dist/eBL_Tablet_Studio-<version>-mac-arm64.dmg.blockmap
dist/latest-mac.yml
```

Typical DMG size: 200–250 MB.

## 5. Smoke-check the DMG (recommended)

Before uploading:

```bash
# Mount and verify the .app launches
VOLUME_PATH=$(hdiutil attach dist/eBL_Tablet_Studio-*-mac-arm64.dmg -nobrowse -noautoopen 2>&1 | awk '/\/Volumes\//{print $NF}')
echo "Mounted at $VOLUME_PATH"

# List contents — expect a single .app bundle
ls "$VOLUME_PATH"

# Unmount
hdiutil detach "$VOLUME_PATH"
```

Optional: copy the `.app` to `/Applications`, right-click → Open, confirm the
splash screen appears. Quit, drag to trash.

## 6. Upload to the GitHub release

The release tag must already exist (created during the Windows build). Find
the version from `package.json` and upload:

```bash
VERSION=$(node -p "require('./package.json').version")
TAG="v${VERSION}"

# Confirm the release exists
gh release view "$TAG" >/dev/null || { echo "Release $TAG does not exist — stop and report"; exit 1; }

# Upload the three macOS files
gh release upload "$TAG" \
  "dist/eBL_Tablet_Studio-${VERSION}-mac-arm64.dmg" \
  "dist/eBL_Tablet_Studio-${VERSION}-mac-arm64.dmg.blockmap" \
  "dist/latest-mac.yml"

# Verify they appear in the release
gh release view "$TAG" --json assets --jq '.assets[] | [.name, .size] | @tsv'
```

After this, the release page should show both Windows and macOS assets.

## 7. Report back

Write a short summary to the user:

- ✅ stitcher binary size: `<size> MB`
- ✅ DMG path: `dist/eBL_Tablet_Studio-<version>-mac-arm64.dmg`
- ✅ Uploaded to: `https://github.com/ludovicus-hispanicus/ebl-tablet-studio/releases/tag/v<version>`
- ⚠️ Any `electron-builder` warnings about missing `identity` (ignore — signing is intentionally off)

Do NOT commit any files produced by this process. `dist/` and `stitcher/.venv/`
are already in `.gitignore`. No `git add` / `git commit` needed.

---

## Common issues and fixes

### "PyInstaller: command not found"
The venv wasn't activated. Re-export `PYTHON` (step 3) so the build script
picks up the correct interpreter. Or repeat `source stitcher/.venv/bin/activate`.

### "electron-builder: cannot create DMG — permission denied / hdiutil error"
Another mounted volume is holding the DMG drive. Run
`hdiutil info | grep image-path` to find and detach it with
`hdiutil detach <path>`, then retry `npm run dist:mac`.

### "spawn python3 ENOENT" during build
Python 3 not on PATH. Install via `brew install python@3.12` and retry from
step 2.

### ONNX Runtime import error in the packaged app
Rare — indicates the venv used a Python version ONNX doesn't ship a wheel for.
Delete `stitcher/.venv`, ensure `python3 --version` is 3.10, 3.11, or 3.12,
and repeat step 2.

### "The application is damaged and can't be opened"
This is Gatekeeper reacting to the unsigned app on a fresh download. To
verify the DMG itself is fine, run:
```bash
xattr -d com.apple.quarantine "/Applications/eBL Tablet Studio.app" 2>/dev/null || true
```
End users encountering this should right-click → Open once (reported in the
release notes).

---

## Appendix: what gets built, what gets skipped

Built (active code paths):
- Electron main + preload + renderer.
- Vendored Python stitcher with rembg / U2NET / onnxruntime.
- SAM ONNX segmentation running in `onnxruntime-node`.
- Built-in project JSONs in `stitcher/assets/projects/`.

NOT built by this flow (deliberate):
- Intel (x64) variant. Separate target in `package.json` needed.
- Windows artifacts. Build on a Windows machine — see the session that
  produced this release for the `npm run dist` flow.
- Linux AppImage. Build on Linux with `npm run dist:linux`.
- `lensfunpy` RAW-lens corrections. Optional dep, not bundled.
