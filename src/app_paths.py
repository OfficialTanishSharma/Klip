"""
Klip — shared path resolution
Works both from source (python Klip.bat) and as a frozen PyInstaller EXE.
klip_data/ always sits next to the project root (source) or next to the EXE.
"""

import sys
from pathlib import Path


def app_root() -> Path:
    """Project root when running from source, EXE folder when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent  # Klip.exe location
    return Path(__file__).parent.parent
