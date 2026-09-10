# -*- mode: python ; coding: utf-8 -*-
"""Portable PyInstaller configuration for a single-file Windows executable."""

from PyInstaller.utils.hooks import collect_all


av_datas, av_binaries, av_hiddenimports = collect_all('av')

a = Analysis(
    ['wildcam_sorter.py'],
    pathex=[],
    binaries=av_binaries,
    datas=av_datas,
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

# Passing binaries and datas directly to EXE creates one self-contained file.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WildCamSorter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
