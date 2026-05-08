"""
styles.py - Reusable QSS strings.

Tab files keep small, locally-specific styles inline. These are the
strings repeated 3+ times across the codebase.
"""

# ─── Backgrounds & cards ───────────────────────────────────────────────
CARD_DARK = (
    "QFrame { background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 4px; }"
)

# ─── Inputs ────────────────────────────────────────────────────────────
INPUT_DARK = (
    "background: #1a1a1a; color: #fff; border: 1px solid #333; "
    "padding: 4px 8px; min-width: 60px; font-family: Consolas; font-size: 14px;"
)

LINE_EDIT_DARK = (
    "background: #111; color: #ccc; border: 1px dashed #333; "
    "padding: 6px; font-family: Consolas; font-size: 14px;"
)

# ─── Buttons ───────────────────────────────────────────────────────────
BUTTON_GHOST = (
    "color: #88ccff; background: transparent; border: 1px solid #444; "
    "padding: 5px 10px; font-size: 14px; font-family: Consolas;"
)

BUTTON_PRIMARY_GREEN = (
    "background: #1a3a1a; color: #44ff88; border: none; "
    "padding: 6px 16px; font-family: Consolas; font-size: 14px;"
)

BUTTON_DANGER = (
    "background: #2a1a1a; color: #ff4444; border: 1px solid #3a2a2a; "
    "padding: 4px 10px; font-family: Consolas; font-size: 14px;"
)

BUTTON_NEUTRAL = (
    "background: #1a1a1a; color: #ccc; border: 1px solid #333; "
    "padding: 4px 10px; font-family: Consolas; font-size: 14px;"
)

# Bottom-bar Launch / Stop button — toggles green ↔ red on bot start/stop.
BUTTON_LAUNCH_GREEN = (
    "background: #1a4a1a; color: #44ff88; border: none; "
    "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
)

BUTTON_LAUNCH_RED = (
    "background: #4a1a1a; color: #ff4444; border: none; "
    "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
)

# ─── Labels ────────────────────────────────────────────────────────────
LABEL_HINT    = "color: #888; font-size: 14px;"
LABEL_SECTION = "color: #ccc; font-size: 14px; font-family: Consolas;"
LABEL_DIM     = "color: #888; font-size: 14px; font-family: Consolas;"

# ─── Slider ────────────────────────────────────────────────────────────
SLIDER_GOLD = (
    "QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }"
    "QSlider::sub-page:horizontal { background: #ffd700; border-radius: 3px; }"
    "QSlider::handle:horizontal { background: #fff; border: 2px solid #ffd700; "
    "width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
)

# ─── Checkbox ──────────────────────────────────────────────────────────
CHECKBOX_GOLD = (
    "QCheckBox { color: #ccc; font-size: 14px; font-family: Consolas; "
    "border: none; background: transparent; }"
    "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #555; "
    "border-radius: 3px; background: #111; }"
    "QCheckBox::indicator:checked { background: #ffd700; border-color: #ffd700; }"
    "QCheckBox::indicator:hover { border-color: #ffd700; }"
)

# Cue-row checkbox — slightly smaller indicator, with disabled variants
# applied when the master "Enable audio cues" toggle is off.
CHECKBOX_CUE_GOLD = (
    "QCheckBox { color: #ccc; font-size: 14px; font-family: Consolas; border: none; background: transparent; }"
    "QCheckBox:disabled { color: #444; }"
    "QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #555; border-radius: 3px; background: #111; }"
    "QCheckBox::indicator:checked { background: #ffd700; border-color: #ffd700; }"
    "QCheckBox::indicator:hover { border-color: #ffd700; }"
    "QCheckBox::indicator:disabled { background: #111; border-color: #333; }"
    "QCheckBox::indicator:checked:disabled { background: #2a2a2a; border-color: #3a3a3a; }"
)

# ─── Radio buttons (audio voice picker) ───────────────────────────────
RADIO_GOLD = (
    "QRadioButton { color: #ccc; font-size: 14px; font-family: Consolas; }"
    "QRadioButton:disabled { color: #444; }"
    "QRadioButton::indicator { width: 14px; height: 14px; }"
    "QRadioButton::indicator:checked { background: #ffd700; border: 2px solid #ffd700; border-radius: 7px; }"
    "QRadioButton::indicator:unchecked { background: #111; border: 1px solid #555; border-radius: 7px; }"
    "QRadioButton::indicator:checked:disabled { background: #2a2a2a; border: 2px solid #3a3a3a; border-radius: 7px; }"
    "QRadioButton::indicator:unchecked:disabled { background: #111; border: 1px solid #333; border-radius: 7px; }"
)
