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
