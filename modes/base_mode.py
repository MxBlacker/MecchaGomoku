"""
Abstract base class for all game modes.
Each mode receives events and drives the GameManager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pygame

from core.game_manager import GameManager


class BaseMode(ABC):
    """Interface that every game mode (PvP, AI, network) must implement."""

    def __init__(self, game_manager: GameManager):
        self.gm = game_manager

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """Process a pygame event."""
        ...

    @abstractmethod
    def update(self) -> None:
        """Called once per frame for mode-specific logic."""
        ...

    @abstractmethod
    def on_enter(self) -> None:
        """Called when this mode becomes active."""
        ...

    @abstractmethod
    def on_exit(self) -> None:
        """Called when switching away from this mode."""
        ...
