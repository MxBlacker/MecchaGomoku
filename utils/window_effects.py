"""
Window transparency — makes the pygame frameless window transparent
where the background image has alpha=0, showing the desktop behind.
Windows-only.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

import pygame

# Color key — any pixel of this exact color becomes transparent.
# Magenta (255, 0, 255) is unlikely to appear in normal game assets.
KEY_COLOR = (255, 0, 255)  # magenta → transparent


def enable_transparency() -> bool:
    """
    Enable per-pixel transparency on the pygame window (Windows).

    After calling this, fill the screen with KEY_COLOR before drawing
    your RGBA content. Areas where KEY_COLOR shows through will be
    transparent to the desktop.

    Returns True on success.
    """
    try:
        hwnd = pygame.display.get_wm_info()["window"]

        # Constants
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        LWA_COLORKEY = 0x00000001

        user32 = ctypes.windll.user32

        # Add WS_EX_LAYERED to the window's extended style
        current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_LAYERED)

        # Set the color key — KEY_COLOR pixels become transparent
        color_ref = KEY_COLOR[2] << 16 | KEY_COLOR[1] << 8 | KEY_COLOR[0]  # BGR
        user32.SetLayeredWindowAttributes(hwnd, color_ref, 0, LWA_COLORKEY)

        return True
    except Exception:
        return False


def start_window_drag() -> None:
    """
    Begin a window-level drag operation so the user can move the
    frameless window by dragging the custom title / menu bar.

    Call this on MOUSEBUTTONDOWN while the cursor is over the bar area
    (and NOT over any interactive button on that bar).

    Windows-only; uses the ``WM_NCLBUTTONDOWN`` + ``HTCAPTION`` trick.
    """
    try:
        hwnd = pygame.display.get_wm_info()["window"]
        # Release the current mouse capture so Windows can take over.
        ctypes.windll.user32.ReleaseCapture()
        # Tell Windows the user clicked on the title bar → native drag.
        WM_NCLBUTTONDOWN = 0x00A1
        HTCAPTION = 2
        ctypes.windll.user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
    except Exception:
        pass
