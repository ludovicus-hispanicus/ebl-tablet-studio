# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for eBL Photo Stitcher.
This builds a single executable with all required dependencies.
"""

# Define pyexiv2 data and hidden imports
# These will be populated when PyInstaller runs
pyexiv2_datas = []
pyexiv2_hiddenimports = []

# Try to collect pyexiv2 data if PyInstaller is running
try:
    from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
    pyexiv2_datas = collect_data_files('pyexiv2')
    pyexiv2_hiddenimports = collect_submodules('pyexiv2')
except (ImportError, ModuleNotFoundError):
    # PyInstaller not available or running outside of PyInstaller context
    copy_metadata = lambda *a: []
    pass

# Collect package metadata that PyInstaller misses
extra_metadata = []
for pkg in ['imageio', 'rawpy', 'rembg', 'pymatting', 'pillow_heif', 'onnxruntime', 'scipy', 'numpy', 'opencv-python', 'Pillow']:
    try:
        md = copy_metadata(pkg)
        extra_metadata += md
        print(f"  Collected metadata for {pkg}: {len(md)} entries")
    except Exception as e:
        print(f"  Warning: Could not collect metadata for {pkg}: {e}")
        # Fallback: try collect_data_files for the dist-info
        try:
            md = collect_data_files(pkg)
            extra_metadata += md
            print(f"  Fallback collect_data_files for {pkg}: {len(md)} entries")
        except Exception:
            pass

block_cipher = None

a = Analysis(
    ['process_tablets.py'],
    pathex=['./lib'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('lib', 'lib'),
    ] + pyexiv2_datas + extra_metadata,
    hiddenimports=[
        'cv2', 
        'numpy',
        'imageio',
        'rawpy',
        'piexif',
        'pyexiv2',
        'cairosvg',
        'cairosvg.surface',
        'cairosvg.parser',
        'cairosvg.css',
        'cairosvg.features',
        'cairosvg.helpers',
        'cairosvg.url',
        'cairocffi',
        'cairocffi.pixbuf',
        'cairocffi.constants',
        'cairocffi.ffi',
        'cffi',
        'tinycss2',
        'cssselect2',
        'defusedxml',
        'webencodings',
        'rembg',
        'onnxruntime',
    ] + pyexiv2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'torch._C', 'torch.cuda',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

excluded_binaries = [
    'opengl32sw.dll',
    # VCRUNTIME140.dll and MSVCP140.dll are bundled so users don't need VC++ Redistributable
    'api-ms-win-core*.dll',
    'api-ms-win-crt*.dll',
    'opencv_videoio_ffmpeg*.dll',
    'libopenblas*.dll',
]

a.binaries = TOC([x for x in a.binaries if not any(
    excluded in x[0] for excluded in excluded_binaries)])

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='eBL Photo Stitcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../assets/icons/icon.ico',
)
