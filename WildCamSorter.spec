# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（体积优化版）

a = Analysis(
    ['wildcam_sorter.py'],
    pathex=[],
    binaries=[
        (r'F:\software\anaconda\envs\wildcam\Library\bin\tcl86t.dll', '.'),
        (r'F:\software\anaconda\envs\wildcam\Library\bin\tk86t.dll', '.'),
    ],
    datas=[
        # 只带 tcl8.6（8.4/8.5 用不到，删掉省空间）
        (r'F:\software\anaconda\envs\wildcam\Library\lib\tcl8.6', 'tcl8\\8.6'),
        (r'F:\software\anaconda\envs\wildcam\Library\lib\tk8.6', 'tk8.6'),
    ],
    hiddenimports=['av'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除用不到的大模块（matplotlib 15MB / imageio_ffmpeg 84MB / imageio）
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
    bootloader_ignore_signals=False,
    strip=True,
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
    strip=True,
    upx=True,
    upx_exclude=[],
    name='WildCamSorter',
)
