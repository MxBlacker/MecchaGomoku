"""
Skill Gomoku game mode — integrates the skill system with the core game loop.

Handles:
  - One skill per turn (optional, before placing a stone)
  - 抽卡游戏 (Gacha): two stones in one turn, first is random colour
  - 扭转乾坤 (Reverse): swap all stone colours (first 5 rounds, once per game)
  - 死区 (Dead Zone): 3×3 locked area for 2 rounds after placing
  - 防御 (Defence): nullifies opponent's next skill
  - Round tracking for cooldown ticks
"""

from __future__ import annotations

from typing import Optional

import pygame

from core.game_manager import GameManager, GameState
from core.stone import StoneColor, Stone
from core.rules import check_win, check_forbidden, is_board_full
from core.skill_system import (
    SkillManager, SkillID, PlayerSkillState, SkillResult,
    SKILL_NAMES, SKILL_DESCS,
)
from modes.base_mode import BaseMode
from ui.board_view import BoardView
from ui.skill_widget import SkillPanel
from ui.skill_effects import SkillEffects
from config import SKILL_GACHA_IMG, SKILL_REVERSE_IMG, SKILL_DEADZONE_IMG, SKILL_DEFENSE_IMG


class SkillMode(BaseMode):
    """
    Game mode for 技能五子棋.

    Each turn the current player may optionally activate one skill,
    then must place a stone (or two, if 抽卡 is active).
    """

    def __init__(
        self,
        game_manager: GameManager,
        board_view: BoardView,
        skill_manager: SkillManager,
        panel_left: SkillPanel,
        panel_right: SkillPanel,
        effects: SkillEffects,
        on_play_sfx=None,  # callback to play a sound effect
    ):
        super().__init__(game_manager)
        self.board_view = board_view
        self.skill_mgr = skill_manager
        self.panel_left = panel_left
        self.panel_right = panel_right
        self.effects = effects
        self._play_sfx = on_play_sfx

        self.hover_pos: Optional[tuple[int, int]] = None

        # Per-turn state
        self._skill_used_this_turn: bool = False
        self._moves_this_round: int = 0         # 0–2, round ends at 2
        self._gacha_first_done: bool = False     # first (random) stone placed?

        # Cached avatar rects (set by renderer before draw)
        self._black_avatar_rect: Optional[pygame.Rect] = None
        self._white_avatar_rect: Optional[pygame.Rect] = None

    # ── Lifecycle ──────────────────────────────────────────

    def on_enter(self) -> None:
        self.skill_mgr.reset()
        self.gm.new_game()
        self.hover_pos = None
        self._skill_used_this_turn = False
        self._moves_this_round = 0
        self._gacha_first_done = False
        self.effects.set_dead_zones([])
        self.effects.set_gacha_hover(None)
        self.effects.set_defense_glow(StoneColor.BLACK, False)
        self.effects.set_defense_glow(StoneColor.WHITE, False)

    def on_exit(self) -> None:
        self.hover_pos = None
        self.effects.set_gacha_hover(None)

    # ── Event handling ─────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a pygame event.  Returns True if a stone was placed."""
        if self.gm.state != GameState.PLAYING:
            return False

        # ── 1. Skill panel clicks ──────────────────────────
        avail_map = self._build_available_map(self.gm.current_turn)
        current_panel = self.panel_left if self.gm.current_turn == StoneColor.BLACK else self.panel_right

        if current_panel.handle_event(event, avail_map):
            return False  # skill click — no stone placed

        # Also check hover on the other panel (for tooltip display)
        other_color = self.gm.current_turn.opponent()
        other_avail = self._build_available_map(other_color)
        other_panel = self.panel_right if self.gm.current_turn == StoneColor.BLACK else self.panel_left
        other_panel.handle_event(event, other_avail)

        # ── 2. Board mouse-move → hover preview ────────────
        if event.type == pygame.MOUSEMOTION:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                r, c = pos
                # Only show hover if the cell is playable
                if self._is_cell_playable(r, c):
                    self.hover_pos = pos
                    self.effects.set_gacha_hover(
                        pos if self._is_gacha_first() else None
                    )
                    return False
            self.hover_pos = None
            self.effects.set_gacha_hover(None)
            return False

        # ── 3. Board click → place stone ───────────────────
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is None:
                return False
            row, col = pos
            if not self._is_cell_playable(row, col):
                return False

            return self._handle_stone_placement(row, col)

        return False

    # ── Stone placement ────────────────────────────────────

    def _handle_stone_placement(self, row: int, col: int) -> bool:
        """
        Place a stone at (row, col) for the current player.
        Handles gacha two-step flow and dead-zone trigger.
        Returns True if a stone was placed.
        """
        color = self.gm.current_turn

        # ── Gacha first stone (random colour) ──────────────
        if self._is_gacha_first():
            return self._place_gacha_first(row, col)

        # ── Normal placement (or gacha second stone) ───────
        success = self.gm.place_stone(row, col)
        if not success:
            return False

        self.hover_pos = None
        self.effects.set_gacha_hover(None)

        # ── Dead-zone trigger ──────────────────────────────
        state = self.skill_mgr.get_state(color)
        if state.deadzone_pending:
            state.deadzone_pending = False
            self.skill_mgr.add_dead_zone(row, col)
            self.effects.set_dead_zones(self.skill_mgr.get_dead_zone_positions())

        # ── Post-placement checks ──────────────────────────
        if self.gm.state == GameState.GAME_OVER:
            return True  # win detected

        # ── Gacha second stone just placed → clean up ──────
        was_gacha = state.gacha_active and self._gacha_first_done
        if was_gacha:
            state.gacha_active = False
            self._gacha_first_done = False

        # ── Turn transition ────────────────────────────────
        self._finish_turn()
        return True

    def _place_gacha_first(self, row: int, col: int) -> bool:
        """
        Place the first (random) stone of the 抽卡游戏 skill.
        1/3 chance: own colour; 2/3 chance: opponent colour.
        """
        color = self.gm.current_turn
        is_own = self.skill_mgr.gacha_is_own(color)
        stone_color = color if is_own else color.opponent()

        # Place directly on the board (bypass GameManager turn logic)
        if not self.gm.board.place_stone(row, col, stone_color):
            return False

        # Record the move
        if self.gm.recorder:
            self.gm.recorder.add_move(row, col, stone_color)

        # Check win
        if check_win(self.gm.board, row, col):
            self.gm.winner = stone_color
            self.gm.win_reason = "五连"
            self.gm.state = GameState.GAME_OVER
            if self.gm.recorder:
                self.gm.recorder.finish(winner=self.gm.winner, win_reason=self.gm.win_reason)
            self.gm._notify("win")
            return True

        # Check forbidden (only for Black)
        if stone_color == StoneColor.BLACK:
            is_forbidden, reason = check_forbidden(self.gm.board, row, col)
            if is_forbidden:
                self.gm.winner = StoneColor.WHITE
                self.gm.win_reason = reason
                self.gm.state = GameState.GAME_OVER
                if self.gm.recorder:
                    self.gm.recorder.finish(winner=self.gm.winner, win_reason=self.gm.win_reason)
                self.gm._notify("win")
                return True

        # Check draw
        if is_board_full(self.gm.board):
            self.gm.winner = None
            self.gm.win_reason = "平局"
            self.gm.state = GameState.GAME_OVER
            if self.gm.recorder:
                self.gm.recorder.finish(winner=None, win_reason=self.gm.win_reason)
            self.gm._notify("draw")
            return True

        self._gacha_first_done = True
        self.hover_pos = None
        self.effects.set_gacha_hover(None)
        return True

    # ── Turn / round management ────────────────────────────

    def _finish_turn(self) -> None:
        """Called after the current player has placed their stone(s)."""
        self._skill_used_this_turn = False
        self._moves_this_round += 1

        if self._moves_this_round >= 2:
            self._moves_this_round = 0
            self.skill_mgr.on_round_end()
            self.effects.set_dead_zones(self.skill_mgr.get_dead_zone_positions())

    # ── Skill activation (callback from SkillPanel) ────────

    def _on_use_skill(self, color: StoneColor, skill_id: SkillID) -> None:
        """
        Called when a player clicks a skill icon.
        Must be the current player's turn and no skill used yet this turn.
        """
        if color != self.gm.current_turn:
            return
        if self._skill_used_this_turn:
            return
        if self.gm.state != GameState.PLAYING:
            return

        # Attempt to use the skill
        result = self.skill_mgr.use_skill(color, skill_id)

        if self._play_sfx:
            self._play_sfx()

        if result == SkillResult.NULLIFIED:
            self._skill_used_this_turn = True  # nullified still consumes the turn's skill
            self.effects.show_nullified("技能被防御抵消!")
            self.effects.set_defense_glow(color.opponent(), False)
            return

        if result == SkillResult.UNAVAILABLE:
            return  # shouldn't happen (icon would be greyed out), but guard

        # result == SkillResult.SUCCESS
        self._skill_used_this_turn = True

        # ── Immediate effects ──────────────────────────────
        if skill_id == SkillID.REVERSE:
            self.skill_mgr.swap_all_stones(self.gm.board)
            self.effects.start_reverse_animation()

        elif skill_id == SkillID.DEFENSE:
            self.effects.set_defense_glow(color, True)

    # ── Helpers ────────────────────────────────────────────

    def _is_cell_playable(self, row: int, col: int) -> bool:
        """Return True if a stone can be placed at (row, col)."""
        if not self.gm.board.is_empty(row, col):
            return False
        if self.skill_mgr.is_dead_zone(row, col):
            return False
        return True

    def _is_gacha_first(self) -> bool:
        """Return True if we are waiting for the first (random) gacha stone."""
        state = self.skill_mgr.get_state(self.gm.current_turn)
        return state.gacha_active and not self._gacha_first_done

    def _build_available_map(self, color: StoneColor) -> dict[SkillID, bool]:
        """
        Build a map of SkillID → available? for *color*.
        Skills only light up when it is that player's turn AND the skill
        is off cooldown AND no skill has been used yet this turn.
        """
        state = self.skill_mgr.get_state(color)
        avail = {}
        is_current = (color == self.gm.current_turn)
        for sid in SkillID:
            if not is_current:
                # Opponent's skills always appear greyed out
                avail[sid] = False
            elif self._skill_used_this_turn:
                avail[sid] = False
            else:
                avail[sid] = state.can_use(sid, self.skill_mgr.round_count)
        return avail

    def get_cooldown_map(self, color: StoneColor) -> dict[SkillID, int]:
        """Build a map of SkillID → remaining cooldown rounds."""
        state = self.skill_mgr.get_state(color)
        return {sid: state.cooldown_for(sid) for sid in SkillID}

    # ── Per-frame update ───────────────────────────────────

    def update(self) -> None:
        """Called once per frame; delegates to effects."""
        pass  # effects.update() is called by renderer
