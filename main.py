"""The Shifting Mansion — launcher.

    python main.py            play
    python main.py --regen    rebuild the generated textures and sounds first
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
ASSET_DIR = os.path.join(ROOT, "assets", "generated")

DEFAULT_SETTINGS = {
    "width": 1600,
    "height": 900,
    "fullscreen": False,
    "vsync": True,
    "fov": 78,
    "mouse_sensitivity": 0.12,
    "invert_y": False,
    "volume": 0.8,
    "bloom": True,
    "shadows": True,
    "film_grain": True,
    "scanlines": False,
    "msaa": 4,
    "anisotropy": 8,
}


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                settings.update(json.load(f))
        except (OSError, ValueError) as exc:
            print(f"settings.json could not be read ({exc}); using defaults.")
    else:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)
    return settings


def configure_panda(s: dict):
    from panda3d.core import loadPrcFileData
    lines = [
        "window-title The Shifting Mansion",
        f"win-size {int(s['width'])} {int(s['height'])}",
        f"fullscreen {'#t' if s['fullscreen'] else '#f'}",
        f"sync-video {'#t' if s['vsync'] else '#f'}",
        "textures-power-2 none",
        "show-frame-rate-meter #f",
        "notify-level warning",
        "default-directnotify-level warning",
        "audio-library-name p3openal_audio",
        "framebuffer-srgb #f",
    ]
    # multisampling fights the bloom filter's off-screen buffer, so only use it without bloom
    if int(s.get("msaa", 0)) > 0 and not s.get("bloom", True):
        lines += ["framebuffer-multisample 1", f"multisamples {int(s['msaa'])}"]
    icon = os.path.join(ROOT, "assets", "icon.ico")
    if os.path.exists(icon):
        lines.append(f"icon-filename {icon}")
    loadPrcFileData("", "\n".join(lines))


def main():
    try:
        import panda3d  # noqa: F401
    except ImportError:
        print("Panda3D is not installed. Run:  python -m pip install -r requirements.txt")
        sys.exit(1)

    from game.assets_gen import ASSET_VERSION, generate_all

    force = "--regen" in sys.argv
    stamp = os.path.join(ASSET_DIR, "VERSION")
    first = force or not os.path.exists(stamp) or open(stamp).read().strip() != ASSET_VERSION
    if first:
        print("Building textures and sounds (first run only, about 10 seconds)...")

        def progress(p, msg):
            bar = "#" * int(p * 30)
            print(f"\r  [{bar:<30}] {msg:<16}", end="", flush=True)

        generate_all(ASSET_DIR, force=True, progress=progress)
        print("\n  done.")

    settings = load_settings()
    configure_panda(settings)
    from game.app import MansionApp
    app = MansionApp(settings, ASSET_DIR)
    app.run()


if __name__ == "__main__":
    main()
