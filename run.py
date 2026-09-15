"""Entry point for the packaged build. `python -m choad` is the normal way
to run from source; this file exists only so PyInstaller has a plain,
non-package script to point at (running choad/__main__.py directly hits
Python's 'attempted relative import with no known parent package')."""
from choad.main import main

if __name__ == "__main__":
    main()
