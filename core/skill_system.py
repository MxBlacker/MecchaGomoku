"""
Skill system for 技能五子棋 (Skill Gomoku) mode.

Defines the four skills, per-player skill state, and a SkillManager
that coordinates cooldowns, dead zones, and inter-skill interactions.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.stone import StoneColor
from config import (
    SKILL_GACHA_COOLDOWN,
    SKILL_DEADZONE_COOLDOWN,
    SKILL_DEFENSE_COOLDOWN,
    SKILL_REVERSE_MAX_ROUND,
    SKILL_DEADZONE_DURATION,
    BOARD_SIZE,
)


class SkillResult:
    """Outcome of a skill-use attempt."""
    SUCCESS     = "success"
    UNAVAILABLE = "unavailable"
    NULLIFIED   = "nullified"


class SkillID(Enum):
    """The four skills in Skill Gomoku."""
    GACHA   = 0   # 抽卡游戏
    REVERSE = 1   # 扭转乾坤
    DEADZONE = 2  # 死区
    DEFENSE = 3   # 防御


# ── Skill metadata ──────────────────────────────────────────

SKILL_DEFS = {
    SkillID.GACHA: {
        "name": "抽卡游戏",
        "desc": "选择一个位置，有1/3概率下我方棋子，2/3概率下对方棋子。该回合可下两步棋。",
        "cooldown": SKILL_GACHA_COOLDOWN,
    },
    SkillID.REVERSE: {
        "name": "扭转乾坤",
        "desc": "交换对弈双方所有棋子颜色。仅前5回合可用，每局限一次。",
        "cooldown": 0,  # once per game — not a numeric cooldown
    },
    SkillID.DEADZONE: {
        "name": "死区",
        "desc": "下子后，以该棋子为中心的3x3范围在接下来2回合双方都无法下棋。",
        "cooldown": SKILL_DEADZONE_COOLDOWN,
    },
    SkillID.DEFENSE: {
        "name": "防御",
        "desc": "使用后对方下一个技能被无效化，效果持续直到触发，不可叠加。",
        "cooldown": SKILL_DEFENSE_COOLDOWN,
    },
}

# Names for UI display
SKILL_NAMES = {sid: d["name"] for sid, d in SKILL_DEFS.items()}
SKILL_DESCS = {sid: d["desc"] for sid, d in SKILL_DEFS.items()}
SKILL_COOLDOWNS = {sid: d["cooldown"] for sid, d in SKILL_DEFS.items()}


# ── Per-player skill state ──────────────────────────────────

@dataclass
class PlayerSkillState:
    """Tracks one player's skill cooldowns and active effects."""

    cooldowns: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    defense_active: bool = False
    reverse_used: bool = False
    gacha_active: bool = False
    deadzone_pending: bool = False

    def can_use(self, skill_id: SkillID, round_count: int) -> bool:
        """Check whether *skill_id* can be activated right now."""
        if skill_id == SkillID.REVERSE:
            if self.reverse_used:
                return False
            if round_count >= SKILL_REVERSE_MAX_ROUND:
                return False
            return True

        # Generic cooldown check
        return self.cooldowns[skill_id.value] == 0

    def mark_used(self, skill_id: SkillID) -> None:
        """Apply the skill's cost / cooldown."""
        if skill_id == SkillID.REVERSE:
            self.reverse_used = True
        elif skill_id == SkillID.DEFENSE:
            self.defense_active = True
            self.cooldowns[skill_id.value] = SKILL_DEFS[skill_id]["cooldown"]
        elif skill_id == SkillID.GACHA:
            self.gacha_active = True
            self.cooldowns[skill_id.value] = SKILL_DEFS[skill_id]["cooldown"]
        elif skill_id == SkillID.DEADZONE:
            self.deadzone_pending = True
            self.cooldowns[skill_id.value] = SKILL_DEFS[skill_id]["cooldown"]

    def tick_cooldowns(self) -> None:
        """Decrement all cooldowns by one (called at round end)."""
        for i in range(len(self.cooldowns)):
            if self.cooldowns[i] > 0:
                self.cooldowns[i] -= 1

    def cooldown_for(self, skill_id: SkillID) -> int:
        """Return remaining cooldown for a skill."""
        return self.cooldowns[skill_id.value]


# ── Skill Manager ───────────────────────────────────────────

class SkillManager:
    """
    Owns skill state for both players and coordinates the global effects
    (dead zones on the board, defense nullification, reverse stone swap).
    """

    def __init__(self):
        self.black = PlayerSkillState()
        self.white = PlayerSkillState()
        self.round_count: int = 0
        self.dead_zones: dict[tuple[int, int], int] = {}          # (row,col) → remaining rounds
        self.dead_zone_centers: dict[tuple[int, int], int] = {}   # centre (row,col) → remaining rounds

    # ── State lookup ─────────────────────────────────────

    def get_state(self, color: StoneColor) -> PlayerSkillState:
        """Return the PlayerSkillState for *color*."""
        return self.black if color == StoneColor.BLACK else self.white

    # ── Skill usage ──────────────────────────────────────

    def can_use(self, color: StoneColor, skill_id: SkillID) -> bool:
        """Check whether *color* can activate *skill_id*."""
        return self.get_state(color).can_use(skill_id, self.round_count)

    def use_skill(self, color: StoneColor, skill_id: SkillID) -> str:
        """
        Attempt to use *skill_id* for *color*.

        Returns:
          SkillResult.SUCCESS     — skill activated
          SkillResult.UNAVAILABLE — cooldown not ready / reverse already used / >5 rounds
          SkillResult.NULLIFIED   — opponent's defence blocked it
        """
        if not self.can_use(color, skill_id):
            return SkillResult.UNAVAILABLE

        # Check opponent's defence — nullifies incoming skills (not self-defence)
        opponent_state = self.get_state(color.opponent())
        if opponent_state.defense_active:
            opponent_state.defense_active = False  # consume the shield
            return SkillResult.NULLIFIED

        state = self.get_state(color)
        state.mark_used(skill_id)
        return SkillResult.SUCCESS

    # ── Round tracking ───────────────────────────────────

    def on_round_end(self) -> None:
        """Called when both players have completed their turns."""
        self.round_count += 1

        self.black.tick_cooldowns()
        self.white.tick_cooldowns()

        # Tick dead-zone timers — remove expired ones
        expired = [pos for pos, remain in self.dead_zones.items() if remain <= 1]
        for pos in expired:
            del self.dead_zones[pos]
        for pos in list(self.dead_zones.keys()):
            self.dead_zones[pos] -= 1

        # Tick centre timers (for rendering one overlay per dead zone)
        expired_c = [pos for pos, remain in self.dead_zone_centers.items() if remain <= 1]
        for pos in expired_c:
            del self.dead_zone_centers[pos]
        for pos in list(self.dead_zone_centers.keys()):
            self.dead_zone_centers[pos] -= 1

    # ── Dead zones ───────────────────────────────────────

    def is_dead_zone(self, row: int, col: int) -> bool:
        """Return True if (row, col) is currently in a dead zone."""
        return (row, col) in self.dead_zones

    def add_dead_zone(self, row: int, col: int) -> None:
        """
        Create a 3×3 dead zone centred at (row, col).
        Affected intersections cannot be played for SKILL_DEADZONE_DURATION rounds.
        """
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                r, c = row + dr, col + dc
                if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                    self.dead_zones[(r, c)] = SKILL_DEADZONE_DURATION
        # Track the centre separately so the renderer draws one overlay per zone
        self.dead_zone_centers[(row, col)] = SKILL_DEADZONE_DURATION

    def get_dead_zone_positions(self) -> list[tuple[int, int]]:
        """Return the centre positions of all active dead zones (for rendering)."""
        return list(self.dead_zone_centers.keys())

    # ── Gacha helper ─────────────────────────────────────

    @staticmethod
    def gacha_is_own(color: StoneColor) -> bool:
        """Randomly determine if the first gacha stone belongs to the user (1/3)."""
        return random.random() < 1.0 / 3.0

    # ── Reverse helper ───────────────────────────────────

    def swap_all_stones(self, board) -> None:
        """
        Swap every stone on *board*: BLACK ↔ WHITE.
        Also swaps the history entries.
        """
        from core.stone import StoneColor as SC

        grid = board._grid
        for r in range(board.size):
            for c in range(board.size):
                if grid[r][c] == SC.BLACK:
                    grid[r][c] = SC.WHITE
                elif grid[r][c] == SC.WHITE:
                    grid[r][c] = SC.BLACK

        # Swap history stone colors
        for stone in board._history:
            if stone.color == SC.BLACK:
                stone.color = SC.WHITE
            elif stone.color == SC.WHITE:
                stone.color = SC.BLACK

    # ── Reset ────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all skill state for a new game."""
        self.black = PlayerSkillState()
        self.white = PlayerSkillState()
        self.round_count = 0
        self.dead_zones.clear()
        self.dead_zone_centers.clear()
