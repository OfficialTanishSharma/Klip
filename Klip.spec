# -*- mode: python ; coding: utf-8 -*-
# Klip EXE build spec — single windowed .exe, no console
# Build:  python -m PyInstaller Klip.spec --noconfirm --clean

a = Analysis(
    ['src\\klip_panel.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pyperclip',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'klip_history',
        'klip_ai',
        'klip_settings',
        'app_paths',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', 'unittest', 'pydoc_data', 'tkinter.test',
        'test', 'setuptools', 'distutils',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Klip',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed — no black console box
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # optional: 'klip.ico' once we make one
)
