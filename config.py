"""
Game configuration constants for MecchaGomoku.
Centralizes all tunable parameters in one place.
"""

import sys
import os


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# ── Board ──────────────────────────────────────────────
BOARD_SIZE = 15          # 15x15 standard Gomoku board
STONE_RADIUS = 17        # radius of a placed stone

# board.png internal measurements at 1.0 scale (px)
_BOARD_IMG_CELL   = 60   # px per grid cell in the source image
_BOARD_IMG_MARGIN = 30   # px from image edge to first grid line

# Master scale knob — CELL_SIZE, MARGIN, and board-offsets all follow.
BOARD_IMG_SCALE = 0.70

# Derived from BOARD_IMG_SCALE (tune that instead)
CELL_SIZE = int(_BOARD_IMG_CELL * BOARD_IMG_SCALE)
MARGIN    = int(_BOARD_IMG_MARGIN * BOARD_IMG_SCALE)

# ── Colors (RGB tuples) ────────────────────────────────
COLOR_BOARD      = (220, 179, 92)   # wood color
COLOR_GRID_LINE  = (0, 0, 0)
COLOR_BLACK      = (0, 0, 0)
COLOR_WHITE      = (255, 255, 255)
COLOR_HIGHLIGHT  = (255, 0, 0)
COLOR_BG         = (50, 50, 50)     # background behind the board
COLOR_TEXT       = (255, 255, 255)
COLOR_BUTTON     = (70, 130, 180)
COLOR_BUTTON_HOVER = (100, 160, 210)

# ── Window (sized to match background.png) ──────────────
WINDOW_WIDTH  = 1440
WINDOW_HEIGHT = 810
FPS = 60
TITLE = "MecchaGomoku - 技能五子棋"

# Offset so grid intersections are centered in the window.

_GRID_SPAN = (BOARD_SIZE - 1) * CELL_SIZE
BOARD_OFFSET_X = WINDOW_WIDTH // 2 - MARGIN - _GRID_SPAN // 2
BOARD_OFFSET_Y = WINDOW_HEIGHT // 2 - MARGIN - _GRID_SPAN // 2

# ── Network ────────────────────────────────────────────
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
BUFFER_SIZE  = 4096

# ── Data ────────────────────────────────────────────────
DATA_DIR     = "data"
RECORDS_DIR  = f"{DATA_DIR}/records"

# ── DeepSeek AI ───────────────────────────────────────
# 在此填入你的 DeepSeek API Token，用于复盘时的 AI 分析
# 获取地址: https://platform.deepseek.com/api_keys
DEEPSEEK_API_TOKEN = ""   # <-- 在这里粘贴你的 API Token

# ── Assets paths ───────────────────────────────────────
ASSETS_DIR   = resource_path("assets")
IMG_DIR      = f"{ASSETS_DIR}/img"
SFX_DIR      = f"{ASSETS_DIR}/sfx"

BACKGROUND_IMG = f"{IMG_DIR}/background.png"
BOARD_IMG       = f"{IMG_DIR}/board.png"
BOARDS_DIR      = f"{IMG_DIR}/boards"
BACKGROUNDS_DIR = f"{IMG_DIR}/backgrounds"
SETTINGS_DIR    = f"{IMG_DIR}/settings"
BLACK_STONE_IMG = f"{IMG_DIR}/black_chess.png"
WHITE_STONE_IMG = f"{IMG_DIR}/white_chess.png"
BLACK_AVATAR_IMG = f"{IMG_DIR}/black_avatar.png"
WHITE_AVATAR_IMG = f"{IMG_DIR}/white_avatar.png"
AVATAR_SIZE = 160          # avatar display size (square, scaled from source)
PLACE_SOUND    = f"{SFX_DIR}/place_chess.mp3"
VICTORY_SOUND  = f"{SFX_DIR}/victory.mp3"

# ── Settings UI images ──────────────────────────────────
SETTINGS_BG_IMG     = f"{SETTINGS_DIR}/setting_background.png"
SLIDER_TRACK_IMG    = f"{SETTINGS_DIR}/slider_track.png"
SLIDER_THUMB_IMG    = f"{SETTINGS_DIR}/slider_thumb.png"
BTN_PREV_IMG        = f"{SETTINGS_DIR}/button_prev.png"
BTN_NEXT_IMG        = f"{SETTINGS_DIR}/button_next.png"
BTN_PLAYPAUSE_IMG   = f"{SETTINGS_DIR}/button_playpause.png"
CHECKBOX_ON_IMG     = f"{SETTINGS_DIR}/checkbox_on.png"
CHECKBOX_OFF_IMG    = f"{SETTINGS_DIR}/checkbox_off.png"

# ── Settings data ────────────────────────────────────────
SETTINGS_FILE   = f"{DATA_DIR}/settings.json"

# ── BGM ────────────────────────────────────────────────
BGM_DIR        = f"{ASSETS_DIR}/bgm"

# ── Skill Gomoku ─────────────────────────────────────────
SKILL_ICON_SIZE = 64
SKILL_GACHA_IMG    = f"{IMG_DIR}/skill_gacha.png"
SKILL_REVERSE_IMG  = f"{IMG_DIR}/skill_reverse.png"
SKILL_DEADZONE_IMG = f"{IMG_DIR}/skill_deadzone.png"
SKILL_DEFENSE_IMG  = f"{IMG_DIR}/skill_defense.png"
SKILL_YINYANG_IMG  = f"{IMG_DIR}/skill_yinyang.png"
SKILL_DEFENSE_GLOW_IMG = f"{IMG_DIR}/skill_defense_glow.png"
SKILL_USE_SOUND    = f"{SFX_DIR}/use_skill.mp3"

# Skill cooldowns (in rounds)
SKILL_GACHA_COOLDOWN   = 3
SKILL_DEADZONE_COOLDOWN = 6
SKILL_DEFENSE_COOLDOWN  = 5
SKILL_REVERSE_MAX_ROUND = 5   # 扭转乾坤 only usable in first 5 rounds
SKILL_DEADZONE_DURATION = 2   # dead zone lasts 2 rounds

# ── Fonts ───────────────────────────────────────────────
FONTS_DIR = f"{ASSETS_DIR}/fonts"
CJK_FONT  = f"{FONTS_DIR}/NotoSansSC-VF.ttf"

# ── Menu button images ──────────────────────────────────
MENU_BTN_SCALE = 0.70     # scale buttons to 40% of original 425×135

BTN_SINGLE_PLAYER   = f"{IMG_DIR}/single_player_button.png"
BTN_PLAYER_VS_AI    = f"{IMG_DIR}/player_vs_ai_button.png"
BTN_INTERNET_VS     = f"{IMG_DIR}/internet_vs_button.png"
BTN_SKILL_GOMOKU    = f"{IMG_DIR}/skill_gomoku_button.png"
BTN_HISTORY_REVIEW  = f"{IMG_DIR}/history_review_button.png"
BTN_SETTING         = f"{IMG_DIR}/setting_button.png"
TITLE_IMG           = f"{IMG_DIR}/title.png"
EXIT_BUTTON_IMG     = f"{IMG_DIR}/exit_button.png"
MINIMIZE_BUTTON_IMG = f"{IMG_DIR}/minimize_button.png"
DEEPSEEK_GIRL_IMG   = f"{IMG_DIR}/deepseek_girl.png"

# ── Menu bar ────────────────────────────────────────────
MENU_BAR_HEIGHT = 50       # reserved space at the top of the window
MENU_BAR_BTN_SCALE = 0.15  # 200×200 → 30×30

# ── Popup ───────────────────────────────────────────────
POPUP_WIDTH  = 360
POPUP_HEIGHT = 180
