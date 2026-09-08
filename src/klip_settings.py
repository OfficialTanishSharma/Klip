"""
Klip — settings management
Reads/writes klip_data/settings.json. All options user-controllable from the GUI.
"""

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "klip_data" / "settings.json"

DEFAULTS = {
    "ai_actions": {
        "Summarize": True,
        "Translate": True,
        "Explain": True,
        "Fix Code": True,
    },
    "history_limit": 500,       # max clips kept (0 = unlimited)
    "pause_listening": False,   # True = stop saving new copies
    "start_with_windows": False,
    "translate_language": "Hindi",  # target language for the Translate action
    "show_hotkeys": True,       # hotkey hints in the panel status bar
}


def load_settings() -> dict:
    """Load settings, filling missing keys with defaults."""
    settings = json.loads(json.dumps(DEFAULTS))  # deep copy
    if SETTINGS_PATH.exists():
        try:
            stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            for section, value in stored.items():
                if isinstance(value, dict) and isinstance(settings.get(section), dict):
                    settings[section].update(value)
                else:
                    settings[section] = value
        except (json.JSONDecodeError, OSError):
            pass  # corrupted file -> keep defaults
    return settings


def save_settings(settings: dict):
    """Write settings to disk (creates folder if needed)."""
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )
