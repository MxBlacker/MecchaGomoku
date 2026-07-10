"""
AI Analyzer — calls DeepSeek API to analyze the current board position during replay.
Runs API calls in a background thread to avoid blocking the UI.
"""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from typing import Optional, Callable

from config import DEEPSEEK_API_TOKEN
from core.board import Board, row_to_label, col_to_label, pos_to_label
from core.stone import StoneColor

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def _board_to_grid_string(board: Board) -> str:
    """Convert the board to a readable ASCII grid string for the AI.
    Uses display coordinates: columns A-O (left→right), rows 1-15 (bottom→top)."""
    size = board.size
    lines = []
    # Column header: A B C ... O
    lines.append("   " + " ".join(f"{col_to_label(c)}" for c in range(size)))
    # Rows from top (15) to bottom (1) — matching screen layout
    for r in range(size):
        row_label = row_to_label(r, size)  # 15 at top, 1 at bottom
        row_chars = []
        for c in range(size):
            stone = board.get_color(r, c)
            if stone is None:
                row_chars.append(" .")
            elif stone == StoneColor.BLACK:
                row_chars.append(" ●")
            else:
                row_chars.append(" ○")
        lines.append(f"{row_label:>2} " + "".join(row_chars))
    return "\n".join(lines)


def _build_analysis_prompt(board: Board, move_index: int, total_moves: int,
                           last_move_info: str, game_result: Optional[str]) -> str:
    """Build the prompt sent to the AI for analysis."""
    grid = _board_to_grid_string(board)

    prompt = f"""你是一位五子棋（Gomoku）职业棋手。请用中文对当前棋盘局面进行客观分析。

【坐标说明】
棋盘坐标采用"字母+数字"格式，左下角为原点：
- 横坐标：A~O（从左到右，共{board.size}列）
- 纵坐标：1~{board.size}（从下到上，共{board.size}行）
- 左下角=A1，左上角=A{board.size}，右下角=O1，右上角=O{board.size}
- 棋盘上方显示的坐标标注即为该格式

【对局信息】
- 当前手数：第 {move_index} 手 / 共 {total_moves} 手
- 棋盘大小：{board.size}×{board.size}
- 上一步：{last_move_info}
- 对局结果：{game_result or "对局进行中"}

【当前棋盘】（上方标注列坐标A~O，左侧标注行坐标1~{board.size}，1在底部）
{grid}

请简洁分析（控制在120字以内，语气冷静专业）：
1. 当前局面的形势判断（谁占优、均衡还是劣势）
2. 双方棋型与连接情况
3. 关键位置或潜在威胁（请用A1格式坐标标注）
"""
    return prompt


class AIAnalyzer:
    """
    Manages AI analysis requests during replay.
    Runs API calls on a background thread so the UI stays responsive.
    Results are cached per move_index.
    """

    def __init__(self, token: str = ""):
        self._token = token or DEEPSEEK_API_TOKEN
        self._cache: dict[int, str] = {}          # move_index → analysis text
        self._pending: set[int] = set()            # moves currently being fetched
        self._on_result: Optional[Callable[[int, str], None]] = None
        self._lock = threading.Lock()

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, value: str) -> None:
        self._token = value
        # Clear cache when token changes
        with self._lock:
            self._cache.clear()
            self._pending.clear()

    def set_on_result(self, callback: Callable[[int, str], None]) -> None:
        """Register a callback(move_index, analysis_text) for when results arrive."""
        self._on_result = callback

    def get_cached(self, move_index: int) -> Optional[str]:
        """Return cached analysis for a move, or None."""
        with self._lock:
            return self._cache.get(move_index)

    def is_pending(self, move_index: int) -> bool:
        """Check if an analysis request is in-flight for this move."""
        with self._lock:
            return move_index in self._pending

    def request_analysis(self, board: Board, move_index: int, total_moves: int,
                         last_move_info: str, game_result: Optional[str] = None) -> None:
        """
        Request AI analysis for the current board position.
        If already cached, calls on_result immediately.
        Otherwise, spawns a background thread for the API call.
        """
        if not self._token:
            return

        # Check cache
        with self._lock:
            if move_index in self._cache:
                # Already have it — deliver immediately
                if self._on_result:
                    self._on_result(move_index, self._cache[move_index])
                return
            if move_index in self._pending:
                return  # already requested
            self._pending.add(move_index)

        prompt = _build_analysis_prompt(board, move_index, total_moves,
                                        last_move_info, game_result)

        thread = threading.Thread(
            target=self._do_api_call,
            args=(move_index, prompt),
            daemon=True,
        )
        thread.start()

    def _do_api_call(self, move_index: int, prompt: str) -> None:
        """Perform the actual API call (runs on a background thread)."""
        result_text = ""
        try:
            payload = json.dumps({
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "你是一位冷静专业的五子棋分析师，用语简洁客观，不浮夸。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.8,
            }).encode("utf-8")

            req = urllib.request.Request(
                DEEPSEEK_API_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result_text = body["choices"][0]["message"]["content"].strip()

        except urllib.error.HTTPError as e:
            if e.code == 401:
                result_text = "⚠️ API Token 无效，请在设置中检查。"
            elif e.code == 402:
                result_text = "⚠️ API 余额不足，请充值后重试。"
            elif e.code == 429:
                result_text = "⚠️ API 请求过于频繁，请稍后重试。"
            else:
                result_text = f"⚠️ API 请求失败 (HTTP {e.code})"
        except Exception as e:
            result_text = f"⚠️ 分析请求失败：{str(e)[:80]}"

        # Cache and notify
        with self._lock:
            self._cache[move_index] = result_text
            self._pending.discard(move_index)

        if self._on_result:
            self._on_result(move_index, result_text)

    def clear_cache(self) -> None:
        """Clear all cached analyses."""
        with self._lock:
            self._cache.clear()
            self._pending.clear()
