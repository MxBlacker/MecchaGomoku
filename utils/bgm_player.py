"""
BGM playlist player — loops through all .mp3 files in assets/bgm/.
Extensible: just drop more .mp3 files into the folder.
"""

from __future__ import annotations

import os
import glob
import pygame

from config import BGM_DIR


# Custom event type for end-of-track (fired by pygame.mixer.music)
BGM_TRACK_END = pygame.USEREVENT + 1


class BGMPlayer:
    """
    Plays all .mp3 files in BGM_DIR sequentially, looping forever.

    Usage:
        bgm = BGMPlayer()
        bgm.start()

        # In your event loop:
        bgm.handle_event(event)
    """

    def __init__(self, bgm_dir: str = BGM_DIR):
        self._dir = bgm_dir
        self._playlist: list[str] = []
        self._index = 0
        self._paused = False
        self._rescan()

        # Register the end-of-track event
        pygame.mixer.music.set_endevent(BGM_TRACK_END)

    # ── Public API ───────────────────────────────────────

    def start(self) -> None:
        """Begin playing the first track."""
        self._rescan()
        self._paused = False
        if self._playlist:
            self._play_current()

    def stop(self) -> None:
        """Stop playback and fade out."""
        pygame.mixer.music.fadeout(500)
        self._paused = False

    def pause(self) -> None:
        """Pause the current track."""
        if self._playlist and not self._paused:
            pygame.mixer.music.pause()
            self._paused = True

    def resume(self) -> None:
        """Resume the paused track."""
        if self._paused:
            pygame.mixer.music.unpause()
            self._paused = False

    def toggle_pause(self) -> None:
        """Toggle between pause / resume."""
        if self._paused:
            self.resume()
        else:
            self.pause()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_playing(self) -> bool:
        return bool(self._playlist) and not self._paused and pygame.mixer.music.get_busy()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Call this in your event loop to advance to the next track."""
        if event.type == BGM_TRACK_END and not self._paused:
            self._next()

    def next_track(self) -> None:
        """Skip to the next track."""
        self._paused = False
        self._next()

    def prev_track(self) -> None:
        """Go back to the previous track."""
        self._paused = False
        if not self._playlist:
            return
        self._index = (self._index - 1) % len(self._playlist)
        self._play_current()

    def set_track(self, index: int) -> None:
        """Jump to a specific track index."""
        if 0 <= index < len(self._playlist):
            self._index = index
            self._paused = False
            self._play_current()

    def set_volume(self, vol: float) -> None:
        """Set volume 0.0–1.0."""
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))

    def rescan(self) -> None:
        """Re-scan the BGM folder (e.g. after adding/removing files)."""
        self._rescan()

    # ── Track info ───────────────────────────────────────

    @property
    def current_track(self) -> str | None:
        if self._playlist and 0 <= self._index < len(self._playlist):
            return os.path.basename(self._playlist[self._index])
        return None

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def playlist_size(self) -> int:
        return len(self._playlist)

    @property
    def playlist(self) -> list[str]:
        """Return list of basenames in the playlist."""
        return [os.path.basename(p) for p in self._playlist]

    # ── Internals ────────────────────────────────────────

    def _rescan(self) -> None:
        """Discover all .mp3 files in the BGM directory (sorted by name)."""
        os.makedirs(self._dir, exist_ok=True)
        self._playlist = sorted(glob.glob(os.path.join(self._dir, "*.mp3")))
        # Clamp index in case files were removed
        if self._index >= len(self._playlist):
            self._index = 0

    def _play_current(self) -> None:
        """Load and play the track at the current index."""
        if not self._playlist:
            return
        path = self._playlist[self._index]
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except pygame.error:
            # Skip unplayable files
            self._next()

    def _next(self) -> None:
        """Advance to the next track and play it."""
        if not self._playlist:
            return
        self._index = (self._index + 1) % len(self._playlist)
        self._play_current()
