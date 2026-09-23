# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.example.yaml', '.'),
        ('rosters/example.yaml', 'rosters'),
        ('assets/icon.ico', 'assets'),
        ('assets/sounds/dark_confirmed.mp3', 'assets/sounds'),
        ('assets/templates/dark_grenade.png', 'assets/templates'),
        ('assets/templates/splendid_dark_grenade.png', 'assets/templates'),
    ],
    hiddenimports=['edge_tts', 'aiohttp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# DLLs no code path loads: OpenCV's FFmpeg video plugin (the app never opens
# video), Qt's software OpenGL and the WebGL platform plugin with its Qt Quick
# chain (this is a QtWidgets app). Dropping them shrinks the onefile exe and
# what it unpacks to %TEMP% on every launch.
_UNUSED = ('opencv_videoio_ffmpeg', 'opengl32sw.dll', 'qwebgl.dll', 'Qt5Quick.dll',
           'Qt5Qml.dll', 'Qt5QmlModels.dll', 'Qt5WebSockets.dll')
a.binaries = [b for b in a.binaries if not any(u in b[0] for u in _UNUSED)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Dark Rotation Manager',
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
    icon=['assets\\icon.ico'],
)
