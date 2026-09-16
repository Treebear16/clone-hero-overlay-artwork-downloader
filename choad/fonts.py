"""Manages the small library of font files the person has added via the
control panel's font picker. Rather than trying to enumerate every font
already installed on the OS (fragile - different platforms need different
approaches, and it doesn't reliably surface every install location), CHOAD
keeps its own copy of each font the person adds, in its appdata folder.
Once added, a font shows up in the dropdown from then on and the original
file's location no longer matters - CHOAD has its own copy."""
import os
import shutil

from .config import get_fonts_dir

ALLOWED_EXTENSIONS = (".ttf", ".otf", ".woff", ".woff2")


def list_fonts():
    """Filenames of every font currently in the library, sorted."""
    d = get_fonts_dir()
    try:
        names = [f for f in os.listdir(d) if f.lower().endswith(ALLOWED_EXTENSIONS)]
    except OSError:
        return []
    return sorted(names, key=str.casefold)


def add_font(source_path: str) -> str:
    """Copies source_path into the font library and returns the filename it
    was saved under. Raises ValueError for a bad path/extension, OSError if
    the copy itself fails (disk full, permissions, etc.) - callers should
    catch and log both rather than letting either crash the request."""
    if not source_path or not os.path.isfile(source_path):
        raise ValueError("That file doesn't exist.")

    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"'{ext}' isn't a supported font type - use .ttf, .otf, .woff, or .woff2.")

    dest_dir = get_fonts_dir()
    base_name = os.path.basename(source_path)
    dest_name = base_name
    stem, suffix = os.path.splitext(base_name)
    counter = 1
    # Don't silently overwrite a same-named font already in the library -
    # e.g. adding a different font that happens to share a filename.
    while os.path.exists(dest_dir / dest_name):
        counter += 1
        dest_name = f"{stem} ({counter}){suffix}"

    shutil.copyfile(source_path, dest_dir / dest_name)
    return dest_name


def font_path(filename: str):
    """Resolves a stored filename to its full path, or None if it isn't
    actually in the library - guards against a filename smuggling a path
    (e.g. '../../something') and against a font that was deleted from disk
    out from under a saved setting."""
    if not filename or os.path.basename(filename) != filename:
        return None
    path = get_fonts_dir() / filename
    return str(path) if path.is_file() else None
