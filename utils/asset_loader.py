"""
Asset loader — lazy-loads and caches images, sounds from the assets directory.
Also provides scanning for board skins and backgrounds.
"""

from __future__ import annotations

import os

import pygame

from config import BACKGROUND_IMG, BACKGROUNDS_DIR, BOARDS_DIR, PLACE_SOUND, VICTORY_SOUND


# ── Cached assets ───────────────────────────────────────

_place_sound = None
_victory_sound = None
_sfx_volume = 0.8  # global SFX volume, synced from settings


def get_place_sound() -> pygame.mixer.Sound | None:
    """Lazy-load and cache the stone-placement sound effect."""
    global _place_sound
    if _place_sound is None:
        try:
            _place_sound = pygame.mixer.Sound(PLACE_SOUND)
        except FileNotFoundError:
            _place_sound = False
    return _place_sound if _place_sound is not False else None


def get_victory_sound() -> pygame.mixer.Sound | None:
    """Lazy-load and cache the victory sound effect."""
    global _victory_sound
    if _victory_sound is None:
        try:
            _victory_sound = pygame.mixer.Sound(VICTORY_SOUND)
        except FileNotFoundError:
            _victory_sound = False
    return _victory_sound if _victory_sound is not False else None


def set_sfx_volume(vol: float) -> None:
    """Set global SFX volume (applied before each play)."""
    global _sfx_volume
    _sfx_volume = max(0.0, min(1.0, vol))


def play_sfx(sound: pygame.mixer.Sound | None) -> None:
    """Play a sound effect at the current global SFX volume."""
    if sound:
        sound.set_volume(_sfx_volume)
        sound.play()


# ── Background loading ──────────────────────────────────

_background_cache: dict[str, pygame.Surface] = {}


def load_background(path: str | None = None) -> pygame.Surface | None:
    """
    Load a background image, scaled to window size.
    Uses a cache keyed by path. Pass None for the default.
    """
    from config import WINDOW_WIDTH, WINDOW_HEIGHT

    key = path or BACKGROUND_IMG
    if key in _background_cache:
        return _background_cache[key]

    try:
        img = pygame.image.load(key).convert_alpha()
        if img.get_width() != WINDOW_WIDTH or img.get_height() != WINDOW_HEIGHT:
            img = pygame.transform.smoothscale(img, (WINDOW_WIDTH, WINDOW_HEIGHT))
        _background_cache[key] = img
        return img
    except FileNotFoundError:
        return None


# ── Asset discovery ─────────────────────────────────────

def get_available_backgrounds() -> list[str]:
    """Return sorted list of background filenames in the backgrounds directory."""
    files = _scan_dir(BACKGROUNDS_DIR, ".png")
    return files if files else ["bg_default.png"]


def get_available_boards() -> list[str]:
    """Return sorted list of board skin filenames in the boards directory."""
    files = _scan_dir(BOARDS_DIR, ".png")
    return files if files else ["board_default.png"]


def get_background_path(filename: str) -> str:
    """Full path for a background filename (checks backgrounds dir then fallback)."""
    path = os.path.join(BACKGROUNDS_DIR, filename)
    if os.path.isfile(path):
        return path
    # fallback to old location
    return BACKGROUND_IMG


def get_board_path(filename: str) -> str:
    """Full path for a board skin filename (checks boards dir then fallback)."""
    from config import BOARD_IMG
    path = os.path.join(BOARDS_DIR, filename)
    if os.path.isfile(path):
        return path
    return BOARD_IMG


def _scan_dir(directory: str, extension: str) -> list[str]:
    """Return sorted list of filenames (with extension) in a directory."""
    try:
        return sorted(
            f for f in os.listdir(directory)
            if f.lower().endswith(extension) and os.path.isfile(os.path.join(directory, f))
        )
    except FileNotFoundError:
        return []
