# PyInstaller spec for CHOAD. Build with:  pyinstaller choad.spec
# Produces a single-file, no-console executable with the app icon baked in.
# Must be run on each target OS - PyInstaller does not cross-compile.
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# pystray picks its backend (win32/darwin/xorg/appindicator) at runtime
# based on sys.platform, which PyInstaller's static analysis doesn't
# always resolve as a hidden import on its own - pull in every pystray
# submodule explicitly so the right backend is always bundled regardless
# of which OS this is built on. tkinter needs the same treatment - its
# import lives inside native_dialog.py's module body (not nested in a
# function, specifically so this works), but PyInstaller's tkinter hook
# still needs an explicit nudge on some platforms to bundle Tcl/Tk's
# actual shared libraries alongside the bytecode.
hidden = collect_submodules("pystray") + collect_submodules("tkinter")

icon = None
if sys.platform == "win32":
    icon = "assets/icon.ico"
elif sys.platform == "darwin":
    icon = "assets/icon.icns"
# Linux .desktop launchers reference assets/icon.png directly; PyInstaller
# has no embedded-icon concept for plain ELF binaries.

datas = [("choad/templates", "choad/templates")]
# Bundle the user's custom icon (if they dropped one in) so the *running*
# tray icon uses it too, not just the file/app icon set at build time -
# see choad/branding.py's get_icon_image().
if os.path.isfile("assets/icon_source.png"):
    datas.append(("assets/icon_source.png", "assets"))

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CHOAD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="CHOAD.app",
        icon=icon,
        bundle_identifier="com.stephen.choad",
        info_plist={
            "LSUIElement": True,  # no Dock icon/menu bar - this is a tray-only app
            "CFBundleShortVersionString": "1.0.0",
        },
    )
