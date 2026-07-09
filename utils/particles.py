"""
Lightweight particle system for visual effects — starfield, stone placement
bursts, and general-purpose sparkles.
"""

from __future__ import annotations

import math
import random
import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT


class Starfield:
    """Animated starfield background — slowly drifting white dots with twinkle."""

    def __init__(self, count: int = 180):
        self._stars: list[dict] = []
        for _ in range(count):
            self._stars.append({
                "x": random.random() * WINDOW_WIDTH,
                "y": random.random() * WINDOW_HEIGHT,
                "r": random.random() * 1.6 + 0.4,
                "speed": random.random() * 0.3 + 0.06,
                "phase": random.random() * math.pi * 2,
                "twinkle": random.random() * 0.018 + 0.004,
            })

    def update(self) -> None:
        for s in self._stars:
            s["phase"] += s["twinkle"]
            s["y"] -= s["speed"]
            s["x"] += math.sin(s["phase"]) * 0.1
            if s["y"] < -5:
                s["y"] = WINDOW_HEIGHT + 5
                s["x"] = random.random() * WINDOW_WIDTH

    def draw(self, surface: pygame.Surface) -> None:
        for s in self._stars:
            alpha = s["r"] / 2.0 * (0.55 + 0.45 * math.sin(s["phase"]))
            c = int(200 + 55 * math.sin(s["phase"]))
            color = (c, c, min(255, c + 40))
            # Tiny stars don't need per-pixel alpha — just use a small filled circle
            pygame.draw.circle(surface, color, (int(s["x"]), int(s["y"])), max(1, int(s["r"])))


class ParticleBurst:
    """One-shot particle burst (e.g. stone placement)."""

    def __init__(self, x: int, y: int, count: int = 14, color=(255, 215, 0)):
        self.particles: list[dict] = []
        self.alive = True
        for _ in range(count):
            angle = random.random() * math.pi * 2
            speed = random.random() * 2.5 + 1.0
            self.particles.append({
                "x": float(x), "y": float(y),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": 1.0,
                "decay": random.random() * 0.03 + 0.025,
                "color": color,
                "r": random.random() * 2.5 + 1.5,
            })

    def update(self) -> None:
        alive_count = 0
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.02  # slight gravity
            p["life"] -= p["decay"]
            if p["life"] > 0:
                alive_count += 1
        if alive_count == 0:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.particles:
            if p["life"] <= 0:
                continue
            alpha = int(p["life"] * 255)
            r, g, b = p["color"]
            c = (r, g, b, alpha)
            # Draw with per-pixel alpha
            sz = max(1, int(p["r"] * p["life"]))
            s = pygame.Surface((sz * 2 + 2, sz * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, c, (sz + 1, sz + 1), sz)
            surface.blit(s, (int(p["x"] - sz), int(p["y"] - sz)))


class EffectsManager:
    """Central manager for starfield + transient particle bursts."""

    def __init__(self):
        self.starfield = Starfield()
        self._bursts: list[ParticleBurst] = []

    def spawn_burst(self, x: int, y: int, color=(255, 215, 0)) -> None:
        self._bursts.append(ParticleBurst(x, y, color=color))

    def update(self) -> None:
        self.starfield.update()
        for b in self._bursts:
            b.update()
        self._bursts = [b for b in self._bursts if b.alive]

    def draw_starfield(self, surface: pygame.Surface) -> None:
        self.starfield.draw(surface)

    def draw_bursts(self, surface: pygame.Surface) -> None:
        for b in self._bursts:
            b.draw(surface)
