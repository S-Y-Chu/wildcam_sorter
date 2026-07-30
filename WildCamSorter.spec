# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['wildcam_sorter.py'],
    pathex=[],
    binaries=[
        (r'F:\software\anaconda\envs\wildcam\Library\bin\tcl86t.dll', '.'),
        (r'F:\software\anaconda\envs\wildcam\Library\bin\tk86t.dll', '.'),
    ],
    datas=[
        (r'F:\software\anaconda\envs\wildcam\Library\lib\tcl8.6', 'tcl8\\8.6'),
        (r'F:\software\anaconda\envs\wildcam\Library\lib\tk8.6', 'tk8.6'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WildCamSorter',
)
