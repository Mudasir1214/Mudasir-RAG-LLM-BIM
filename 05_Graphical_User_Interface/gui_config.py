"""
GUI Configuration for BIM Safety Analysis System
Clean Pastel Theme - Simple and Elegant
"""

# ============================================================================
# WINDOW SETTINGS
# ============================================================================
WINDOW_TITLE = "RAG-LLM-BIM for Fall Safety"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 720
CHATBOT_WIDTH = 900
CHATBOT_HEIGHT = 850

# ============================================================================
# PATHS
# ============================================================================
OUTPUT_BASE_DIR = "outputs"
DEFAULT_IFC_DIR = "../Phase_1_Hazard_Detection"

# ============================================================================
# API CONFIGURATION
# ============================================================================
DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
# Using DeepSeek Chat - works with OpenRouter
DEFAULT_MODEL = "deepseek/deepseek-chat"  # DeepSeek Chat via OpenRouter

# API Key - Leave empty to force loading from file or environment
API_KEY = ""  # Will load from api_key.txt or LLM_API_KEY environment variable

# API Key Storage
API_KEY_FILE = "api_key.txt"

# ============================================================================
# CLEAN PASTEL COLOR SYSTEM - Simple & Elegant
# ============================================================================

# Base Colors - Soft Pastels (matching the reference image)
BG_COLOR = "#e8e8e8"              # Light gray outer background
BG_SECONDARY = "#f5f5f5"          # Slightly lighter gray
CARD_BG = "#ffffff"               # White for content areas
HEADER_BG = "#c5e1a5"             # Soft mint green accent bar
SURFACE_ELEVATED = "#f0f0f0"      # Light gray elevated

# Column Colors (the 3 main panels)
COLUMN_LEFT = "#b3d4e0"           # Soft sky blue (left panel)
COLUMN_CENTER = "#d4d4d4"         # Soft gray (center panel)
COLUMN_RIGHT = "#b8c5d9"          # Soft periwinkle blue (right panel)

# Primary Accent
PRIMARY_COLOR = "#5a9fd4"         # Soft blue
PRIMARY_HOVER = "#4a8fc4"         # Slightly darker blue
PRIMARY_MUTED = "#7ab8e0"         # Lighter blue

# Semantic Colors - Soft versions
SUCCESS_COLOR = "#81c784"         # Soft green
WARNING_COLOR = "#ffb74d"         # Soft orange
ERROR_COLOR = "#e57373"           # Soft red
INFO_COLOR = "#64b5f6"            # Soft blue

# Status Indicators
STATUS_IDLE = "#9e9e9e"           # Gray
STATUS_RUNNING = "#64b5f6"        # Soft blue
STATUS_COMPLETE = "#81c784"       # Soft green
STATUS_ERROR = "#e57373"          # Soft red

# Text Colors - White on colored backgrounds, dark on light
TEXT_PRIMARY = "#ffffff"          # White (for on colored panels)
TEXT_SECONDARY = "#f5f5f5"        # Off-white
TEXT_TERTIARY = "#e0e0e0"         # Light gray
TEXT_ON_PRIMARY = "#ffffff"       # White on colored backgrounds
TEXT_ON_DARK = "#ffffff"          # White
TEXT_DARK = "#424242"             # Dark gray for light backgrounds
TEXT_BLACK = "#000000"            # Pure black for headings

# Stat Colors (for results panel)
STAT_ORANGE = "#ff8c00"           # Orange for hazards
STAT_GREEN = "#4caf50"            # Green for guardrails

# UI Elements
DIVIDER_COLOR = "#bdbdbd"         # Gray dividers
BORDER_COLOR = "#9e9e9e"          # Gray borders
HOVER_BG = "#e3f2fd"              # Light blue hover
INPUT_BG = "#ffffff"              # White input fields
DISABLED_COLOR = "#bdbdbd"        # Gray disabled

# Chat Colors
CHAT_USER_BG = "#b3d4e0"          # Light blue (matches left column)
CHAT_ASSISTANT_BG = "#d4d4d4"     # Light gray (matches center)
CHAT_THINKING_COLOR = "#ffb74d"   # Soft orange

# ============================================================================
# SPACING SYSTEM (8px Grid)
# ============================================================================
SPACE_XS = 4    # 0.5 units
SPACE_SM = 8    # 1 unit
SPACE_MD = 16   # 2 units
SPACE_LG = 24   # 3 units
SPACE_XL = 32   # 4 units
SPACE_XXL = 48  # 6 units

# Component Spacing
HEADER_HEIGHT = 70
CARD_PADDING = 24
CARD_RADIUS = 8
BUTTON_HEIGHT = 44

# ============================================================================
# TYPOGRAPHY SYSTEM - Professional Sans-Serif
# ============================================================================

# Font Family
FONT_FAMILY = "Segoe UI"          # Windows native, clean
FONT_FAMILY_MONO = "Consolas"     # Monospace for logs/code

# Font Sizes (increased by 20% for better visibility)
FONT_SIZE_H1 = 24    # Large headers (was 20)
FONT_SIZE_H2 = 19    # Section headers (was 16)
FONT_SIZE_H3 = 17    # Subsection headers (was 14)
FONT_SIZE_BODY = 13  # Regular text (was 11)
FONT_SIZE_SMALL = 12 # Small text (was 10)
FONT_SIZE_TINY = 11  # Tiny labels (was 9)
FONT_SIZE_PHASE_DESC = 9  # Phase descriptions (smaller to fit)

# Icon Sizes (larger to match fonts)
ICON_SIZE_XL = 20    # Extra large icons for headings
ICON_SIZE_LG = 18    # Large icons
ICON_SIZE_MD = 16    # Medium icons
ICON_SIZE_SM = 14    # Small icons

# Font Weights
FONT_WEIGHT_REGULAR = "normal"
FONT_WEIGHT_MEDIUM = "normal"  # Tkinter limitation
FONT_WEIGHT_BOLD = "bold"

# Typography Styles (Font, Size, Weight)
FONT_TITLE = (FONT_FAMILY, FONT_SIZE_H1, FONT_WEIGHT_MEDIUM)
FONT_SECTION = (FONT_FAMILY, FONT_SIZE_H2, FONT_WEIGHT_MEDIUM)
FONT_SUBSECTION = (FONT_FAMILY, FONT_SIZE_H3, FONT_WEIGHT_MEDIUM)
FONT_LABEL = (FONT_FAMILY, FONT_SIZE_SMALL, FONT_WEIGHT_REGULAR)
FONT_BODY = (FONT_FAMILY, FONT_SIZE_BODY, FONT_WEIGHT_REGULAR)
FONT_BUTTON = (FONT_FAMILY, FONT_SIZE_BODY, FONT_WEIGHT_MEDIUM)
FONT_MONO = (FONT_FAMILY_MONO, FONT_SIZE_SMALL, FONT_WEIGHT_REGULAR)

# ============================================================================
# PHASE CONFIGURATION
# ============================================================================
PHASE_NAMES = {
    1: "Hazard Detection",
    2: "Hazard Visualization",
    3: "Guardrail Placement",
    4: "LLM Advisory"
}

PHASE_DESCRIPTIONS = {
    1: "Scan IFC model for construction safety hazards",
    2: "Apply color coding to detected hazard elements",
    3: "Generate OSHA-compliant protective guardrails",
    4: "AI-powered safety analysis and recommendations"
}

# Phase Icons (Minimal, Unicode)
PHASE_ICONS = {
    1: "🔍",  # Detection
    2: "🎨",  # Visualization
    3: "🛡️",  # Protection
    4: "🤖"   # Advisory
}

# Phase Colors (Soft, harmonious pastels)
PHASE_COLORS = {
    1: "#5a9fd4",  # Soft blue - Detection
    2: "#ffb74d",  # Soft orange - Visualization
    3: "#81c784",  # Soft green - Guardrails
    4: "#b39ddb"   # Soft purple - LLM Advisory
}

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE = "gui_application.log"
LOG_LEVEL = "INFO"
LOG_LINES_VISIBLE = 8  # Number of log lines to show in UI

# ============================================================================
# CHATBOT SETTINGS
# ============================================================================
CHAT_HISTORY_HEIGHT = 30
CHAT_INPUT_HEIGHT = 3
MAX_MESSAGE_LENGTH = 2000

# Message formatting
USER_PREFIX = "You"
ASSISTANT_PREFIX = "Assistant"

# Quick Actions
QUICK_QUESTIONS = [
    "What OSHA standards apply to this project?",
    "Show me the most critical hazards",
    "How many guardrails were placed?",
    "What are the top safety recommendations?",
    "Explain the floor opening hazards"
]

# ============================================================================
# BUTTON STYLES - Clean and Simple
# ============================================================================
BUTTON_STYLE_PRIMARY = {
    "bg": PRIMARY_COLOR,
    "fg": TEXT_ON_PRIMARY,
    "activebackground": PRIMARY_HOVER,
    "activeforeground": TEXT_ON_PRIMARY,
    "relief": "flat",
    "borderwidth": 0,
    "cursor": "hand2",
    "font": FONT_BUTTON
}

BUTTON_STYLE_SECONDARY = {
    "bg": "#e0e0e0",
    "fg": "#424242",
    "activebackground": "#bdbdbd",
    "activeforeground": "#212121",
    "relief": "flat",
    "borderwidth": 0,
    "cursor": "hand2",
    "font": FONT_BUTTON
}

BUTTON_STYLE_DANGER = {
    "bg": ERROR_COLOR,
    "fg": TEXT_ON_PRIMARY,
    "activebackground": "#ef5350",
    "activeforeground": TEXT_ON_PRIMARY,
    "relief": "flat",
    "borderwidth": 0,
    "cursor": "hand2",
    "font": FONT_BUTTON
}

BUTTON_STYLE_SUCCESS = {
    "bg": SUCCESS_COLOR,
    "fg": TEXT_ON_PRIMARY,
    "activebackground": "#66bb6a",
    "activeforeground": TEXT_ON_PRIMARY,
    "relief": "flat",
    "borderwidth": 0,
    "cursor": "hand2",
    "font": FONT_BUTTON
}

# ============================================================================
# ANIMATION SETTINGS
# ============================================================================
ANIMATION_DURATION_MS = 200  # For smooth transitions
PROGRESS_UPDATE_MS = 100     # Progress bar update frequency
