"""
Persistent settings manager — loads/saves user preferences as JSON.
Tracks volume, board skin, and background selections.
"""

from __future__ import annotations

import json
import os
from config import SETTINGS_FILE


_DEFAULTS = {
    "bgm_volume": 0.5,
    "sfx_volume": 0.8,
    "current_board_skin": "board_default.png",
    "current_background": "bg_default.png",
    "show_starfield": True,
}


class SettingsManager:
    """Thin wrapper around a JSON-backed settings dict with auto-save."""

    def __init__(self, path: str = SETTINGS_FILE):
        self._path = path
        self._data: dict = dict(_DEFAULTS)
        self._load()

    # ── Persistence ──────────────────────────────────────

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self._data.update(loaded)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ── Accessors ────────────────────────────────────────

    @property
    def bgm_volume(self) -> float:
        return self._data["bgm_volume"]

    @bgm_volume.setter
    def bgm_volume(self, value: float) -> None:
        self._data["bgm_volume"] = round(max(0.0, min(1.0, value)), 2)
        self.save()

    @property
    def sfx_volume(self) -> float:
        return self._data["sfx_volume"]

    @sfx_volume.setter
    def sfx_volume(self, value: float) -> None:
        self._data["sfx_volume"] = round(max(0.0, min(1.0, value)), 2)
        self.save()

    @property
    def current_board_skin(self) -> str:
        return self._data["current_board_skin"]

    @current_board_skin.setter
    def current_board_skin(self, filename: str) -> None:
        self._data["current_board_skin"] = filename
        self.save()

    @property
    def current_background(self) -> str:
        return self._data["current_background"]

    @current_background.setter
    def current_background(self, filename: str) -> None:
        self._data["current_background"] = filename
        self.save()

    @property
    def show_starfield(self) -> bool:
        return self._data.get("show_starfield", True)

    @show_starfield.setter
    def show_starfield(self, value: bool) -> None:
        self._data["show_starfield"] = value
        self.save()
