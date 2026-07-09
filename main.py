"""
MecchaGomoku — 五子棋
========================
Entry point. Launches the game window and starts the main loop.

Run:
    python main.py
"""

import sys
import os

# Ensure the project root is on sys.path so all imports work regardless of
# how the script is invoked.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.game_manager import GameManager
from ui.renderer import Renderer


def main() -> None:
    gm = GameManager()
    renderer = Renderer(gm)
    renderer.run()


if __name__ == "__main__":
    main()
