"""Opens the OS's native file/folder picker. Runs tkinter in its own
subprocess rather than in-process, for two reasons:

1. On macOS, Cocoa requires all UI to run on a process's main thread - but
   the tray icon (pystray) already occupies this app's main thread with its
   own blocking event loop, so tkinter has no main thread available to use
   here. A fresh subprocess gets its own main thread, sidestepping that
   entirely, regardless of what the parent process's threads are doing.
2. It keeps a GUI toolkit (and its native libs) fully decoupled from the
   Flask/watcher/tray code - if tkinter/Tcl-Tk isn't available for some
   reason, only the browse feature degrades, nothing else does.

`import tkinter` is kept at module level (not inside a function) so
PyInstaller's static analysis reliably detects it and bundles Tcl/Tk -
the same lesson learned the hard way with pystray's import in tray.py.
"""
import json
import sys

DIALOG_TIMEOUT_SECONDS = 600  # generous - a person actually using the dialog can take a while


def run_dialog_and_print(mode: str, initial_dir: str):
    """Called when this program is re-invoked with --native-dialog (see
    main.py). Opens the picker, prints {"path": ...} as the last line of
    stdout, then exits. Never raises - always prints valid JSON."""
    import tkinter
    from tkinter import filedialog

    result = {"path": None}
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        kwargs = {"initialdir": initial_dir} if initial_dir else {}
        if mode == "dir":
            path = filedialog.askdirectory(**kwargs)
        else:
            path = filedialog.askopenfilename(**kwargs)
        root.destroy()
        result["path"] = path or None
    except Exception as exc:  # tkinter/Tcl missing, no display, user closed abruptly, etc.
        result["error"] = str(exc)

    print(json.dumps(result))


def _self_invocation_command(mode: str, initial_dir: str):
    """The command to re-launch this same program in dialog-only mode -
    works whether running from source or as a frozen PyInstaller build."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--native-dialog", mode, "--initial-dir", initial_dir or ""]
    return [sys.executable, "-m", "choad", "--native-dialog", mode, "--initial-dir", initial_dir or ""]


def pick_path(mode="file", initial_dir=None):
    """mode: 'file' or 'dir'. Returns the chosen absolute path, or None if
    the user cancelled, or if the dialog couldn't be shown at all (missing
    Tk, no display on a headless Linux box, etc.) - callers should fall
    back to letting the person type the path by hand in that case."""
    import subprocess

    try:
        result = subprocess.run(
            _self_invocation_command(mode, initial_dir),
            capture_output=True,
            text=True,
            timeout=DIALOG_TIMEOUT_SECONDS,
        )
        if not result.stdout.strip():
            return None
        data = json.loads(result.stdout.strip().splitlines()[-1])
        return data.get("path")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, IndexError):
        return None
