# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller configuration for native macOS application bundles."""

from PyInstaller.utils.hooks import collect_all


av_datas, av_binaries, av_hiddenimports = collect_all('av')

a = Analysis(
    ['wildcam_sorter.py'],
    pathex=[],
    binaries=av_binaries,
    datas=av_datas + [('README.md', '.')],
    hiddenimports=av_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'imageio', 'imageio_ffmpeg',
        'tkinter.test', 'tkinter.test.support',
        'unittest', 'pydoc', 'doctest', 'pickletester',
        'test', 'distutils', 'ensurepip',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WildCamSorter',
    debug=False,
    bootloader_ignore_signals=True,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='WildCamSorter',
)

app = BUNDLE(
    collection,
    name='WildCamSorter.app',
    icon=None,
    bundle_identifier='com.siyuanzhu.wildcamsorter',
    info_plist={
        'CFBundleDisplayName': 'WildCam Sorter',
        'CFBundleName': 'WildCam Sorter',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '13.0',
    },
)
