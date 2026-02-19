"""
config.py
Configuration file for IFC Hazard Detection Pipeline

╔═══════════════════════════════════════════════════════════════════════════╗
║  IMPORTANT: Use Final_Ifc_v2.py for best Phase 3 compatibility!          ║
║  The enhanced version captures element IDs needed for visualization.     ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""

# ==========================================
# ⚙️ FILE CONFIGURATION - CHANGE THESE ⚙️
# ==========================================

# ┌─────────────────────────────────────────────────────────────────┐
# │ IFC FILE - Your building model to analyze                      │
# └─────────────────────────────────────────────────────────────────┘
# Place your IFC file in Phase 1 folder and specify filename here
# Options:
#   - "Mudasir LLM-BIM.ifc" (default test file)
#   - "LTU_A-House_redesign.ifc" (large house model)
#   - "your-custom-file.ifc"

IFC_FILENAME = None #"input_data/Mudasir-LLM-BIM.ifc"  # Relative path within Phase 1 final Files folder

# ┌─────────────────────────────────────────────────────────────────┐
# │ OUTPUT FOLDER - Where to save detection results                │
# └─────────────────────────────────────────────────────────────────┘
# Results will be in: OUTPUT_FOLDER/run_YYYYMMDD_HHMMSS/
# Contains: hazards_detected.json (for Phase 3) + run_summary.json

OUTPUT_FOLDER = "../output_data/hazard_identification_results"

# Optional ontology CSV (usually not needed)
ONTOLOGY_CSV = None

# ==========================================
# DETECTION THRESHOLDS (in millimeters)
# ==========================================
# Adjust these if your IFC units are different
THRESHOLDS = {
    # Elevated work hazards
    "FallFromHeight": 2000,
    "UnprotectedSidesAndEdges": 1800,
    "LeadingEdges": 2000,
    
    # Opening hazards (Strict User Config)
    "FloorOpening": 500,
    "WallOpening": 500,
    "RoofOpening": 400,
    
    # Access hazards
    "Scaffold": 3000,
    "Ladder": 915,
    "Stairway": 760,
    
    # Excavation hazards
    "Excavation": 2000
}

CONSIDERED_HAZARDS = [
    "FallFromHeight",
    "UnprotectedSidesAndEdges",
    "FloorOpening",
    "WallOpening",
    "Stairway"
]

# Optional: map to 3 major categories for 3x3 confusion matrix
MAJOR_HAZARD_CATEGORIES = [
    "FallFromHeight",           # FFH (global)
    "Openings",                 # Floor/Wall/Roof grouped
    "Access"                    # Ladders/Scaffolds/Stairways grouped
]

# ==========================================
# DETECTION SENSITIVITY
# ==========================================
# Set to True for more aggressive opening detection
DETECT_ALL_OPENINGS = True

# Minimum opening size to consider (mm)
# Openings smaller than this will be ignored
MIN_OPENING_SIZE = 100  # Detect openings >= 100mm (adjust to 300, 500, etc. as needed)

# Opening classification thresholds
OPENING_CLASSIFICATION = {
    "horizontal_ratio": 0.3,  # If height < (min(width,depth) * ratio), it's horizontal
    "vertical_ratio": 0.3,    # If min(w,d) < max(w,d) * ratio, it's vertical
    "roof_proximity": 500     # mm from slab top to be considered roof opening
}

# ==========================================
# GUARDRAIL PROTECTION DETECTION
# ==========================================
# These parameters control when an opening is considered "protected" by a guardrail

# Minimum railing height to provide adequate protection (mm)
GUARDRAIL_HEIGHT_MIN = 760  # Standard safety railing height (760mm = 30 inches)

# Horizontal distance tolerance for guardrail overlap check (mm)
# Guardrail must be within this distance in XY plane to protect opening
GUARDRAIL_XY_TOLERANCE = 500  # 500mm tolerance

# Vertical distance tolerance for guardrail protection (mm)
# Guardrail must be at approximately same Z level as opening
# This prevents a guardrail on floor 1 from protecting same opening on floors 2-3
GUARDRAIL_Z_TOLERANCE = 1500  # Guardrail must be within 1500mm (1.5m) vertically

# ==========================================
# EDGE OPENING DETECTION
# ==========================================
# Distance from slab edge to consider an opening as "edge opening" (mm)
# Edge openings are more critical and require extra protection
EDGE_OPENING_THRESHOLD = 1000  # Openings within 1000mm (1m) of slab edge

# ==========================================
# STAIRWAY GUARDRAIL DETECTION (3D-Spatial Aware)
# ==========================================
# Enhanced parameters for stairway-specific guardrail detection

# Horizontal distance tolerance for stair-guardrail proximity (mm)
# Guardrails must be within this distance to protect stairways
STAIR_GUARDRAIL_XY_TOLERANCE = 500  # Reduced: only truly adjacent railings count

# Vertical distance tolerance for stair-guardrail alignment (mm)
# Allows for stairs spanning multiple levels
STAIR_GUARDRAIL_Z_TOLERANCE = 3000  # Increased to 3m

# Minimum overlap percentage for guardrail to be considered protective
# e.g., 0.3 = guardrail must cover at least 30% of stair footprint
STAIR_MIN_OVERLAP_PERCENTAGE = 0.01  # Reduced to 1% to catch perimeter railings

# ==========================================
# EXCLUSIONS
# ==========================================
# List of Element IDs (GlobalId or numeric) to strictly IGNORE during detection
# Used for manually verified "safe" elements that fail automated checks
IGNORED_ELEMENT_IDS = [
    # "1HdfZJUMf0EhQ4hSrvABXL", # User reported safe stair (Now handled dynamically)
    # "1HdfZJUMf0EhQ4hSrvABaW", 
    # "1HdfZJUMf0EhQ4hSrvAB_4"
]

# ==========================================
# UNIT CONVERSION FIX
# ==========================================
# Force unit conversion if automatic detection fails
# Set to None to use automatic detection, or set to 1000.0 for meters->mm
FORCE_UNIT_FACTOR = 1000.0  # Your IFC is in meters, convert to mm

# ==========================================
# SEVERITY CALCULATION
# ==========================================
SEVERITY_RANGES = {
    "Low": (0.0, 1.0),      # Below threshold to 100% of threshold
    "Medium": (1.0, 1.5),   # 100% to 150% of threshold
    "High": (1.5, 2.0),     # 150% to 200% of threshold
    "Critical": (2.0, 999)  # Above 200% of threshold
}

# ==========================================
# LOGGING CONFIGURATION
# ==========================================
# ==========================================
# LOGGING CONFIGURATION
# ==========================================
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
VERBOSE_DETECTION = True  # Show detailed detection info

# ==========================================
# HAZARD COLORS (RGB 0-1 Scale)
# ==========================================
# 6 Colors for 6 Hazard Types
HAZARD_COLORS = {
    "FallFromHeight": (1.0, 0.0, 0.0),           # Red (Critical)
    "UnprotectedSidesAndEdges": (1.0, 1.0, 0.0), # Yellow (Caution)
    "FloorOpening": (1.0, 0.5, 0.0),             # Orange (High Alert)
    "WallOpening": (1.0, 0.0, 1.0),              # Magenta (Distinct)
    "Stairway": (1.0, 0.0, 0.0),                 # RED (Distinct from default Blue/Cyan)
    "Stairways": (1.0, 0.0, 0.0),                # RED
    "RoofOpening": (1.0, 0.5, 0.0),              # Orange (Same as FloorOpening)
    "Unknown": (0.5, 0.5, 0.5)                   # Grey
}

# SEVERITY COLORS (Legacy/Fallback)
SEVERITY_COLORS = {
    "Low": (0.0, 1.0, 0.0),       # Green
    "Medium": (1.0, 1.0, 0.0),    # Yellow
    "High": (1.0, 0.5, 0.0),      # Orange
    "Critical": (1.0, 0.0, 0.0),  # Red
    "Unknown": (0.5, 0.5, 0.5)    # Grey
}

# VISUALIZATION SETTINGS
CREATE_OPENING_MARKERS = True  # Always create markers for openings (voids)
MARKER_SIZE = 500.0            # Size of the hazard marker box (mm)
PRESERVE_EXISTING_COLORS = False # Overwrite existing element colors
COLOR_TRANSPARENCY = 0.8         # Opacity of colored elements (0.0-1.0)
