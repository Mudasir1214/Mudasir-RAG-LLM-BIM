"""
Phase 3 Configuration
Color-coding and visualization settings for hazard detection
"""

# ==========================================
# ⚙️ MAIN CONFIGURATION - CHANGE THESE PATHS ⚙️
# ==========================================

# ┌─────────────────────────────────────────────────────────────────┐
# │ 1. HAZARDS FILE - Path to hazards_detected.json from Phase 1   │
# └─────────────────────────────────────────────────────────────────┘
# Default: Auto-detect from Phase 1 (uses latest run)
# Will be set at runtime by visualize_hazards.py

HAZARDS_JSON_PATH = None  # Auto-detect latest from Phase 1 output

# ┌─────────────────────────────────────────────────────────────────┐
# │ 2. IFC FILE - Source building model to visualize               │
# └─────────────────────────────────────────────────────────────────┘
# IMPORTANT: Use the SAME IFC file that was used to generate the hazards!

SOURCE_IFC_PATH = None  # Will be set by visualize_hazards.py or GUI pipeline

# ┌─────────────────────────────────────────────────────────────────┐
# │ 3. OUTPUT FOLDER - Where to save colored IFC and reports       │
# └─────────────────────────────────────────────────────────────────┘

OUTPUT_FOLDER = "output_data/hazard_visualization_results"

# ==========================================
# END OF MAIN CONFIGURATION
# ==========================================
# Advanced settings below - usually don't need to change these


# ==========================================
# ⚠️ CRITICAL: File Consistency Check ⚠️
# ==========================================
# The IFC file specified above MUST be the same file used to generate
# the hazards_detected.json in Phase 1. If they don't match, you'll get
# low success rates (most elements won't be found).
#
# To ensure consistency:
#   1. Run Phase 1 on your IFC file
#   2. Note the output folder: hazard_results/run_YYYYMMDD_HHMMSS/
#   3. Set HAZARDS_JSON_PATH to that folder's hazards_detected.json
#   4. Set SOURCE_IFC_PATH to the SAME IFC file used in step 1
# ==========================================

# ==========================================
# HAZARD COLORS (RGB 0-1 Scale)
# ==========================================
# Based on Table 3: Automated fall hazard detection and visualization strategies
# Hazard-type-based detection color scheme:
#   - Falls from height: Purple
#   - Unprotected sides and edges: Concrete Gray (updated from Blue)
#   - Stairways: Green
#   - Floor openings (horizontal): Orange
#   - Wall openings (vertical): Red
#
# 💡 TIP: You can easily customize these colors by changing the RGB values below.
#         RGB values range from 0.0 to 1.0 (e.g., 0.5 = 50% intensity)
#         Common colors:
#           Red: (1.0, 0.0, 0.0)     | Green: (0.0, 1.0, 0.0)   | Blue: (0.0, 0.0, 1.0)
#           Yellow: (1.0, 1.0, 0.0)  | Purple: (0.5, 0.0, 0.5)  | Orange: (1.0, 0.65, 0.0)
#           Concrete: (0.5, 0.5, 0.5)| Cement: (0.65, 0.65, 0.65) | Dark Gray: (0.3, 0.3, 0.3)

HAZARD_COLORS = {
    "FallFromHeight": (0.5, 0.0, 0.5),           # Purple (128, 0, 128) - Table 3
    "UnprotectedSidesAndEdges": (0.65, 0.65, 0.65), # Concrete Gray (166, 166, 166) - Realistic material color
    "FloorOpening": (1.0, 0.65, 0.0),            # Orange (255, 165, 0) - Table 3
    "WallOpening": (1.0, 0.0, 0.0),              # Red (255, 0, 0) - Table 3
    "Stairway": (0.0, 1.0, 0.0),                 # Green (0, 255, 0) - Table 3
    "Stairways": (0.0, 1.0, 0.0),                # Green - Table 3
    "RoofOpening": (1.0, 0.65, 0.0),             # Orange (same as FloorOpening)
    "Unknown": (0.5, 0.5, 0.5)                   # Grey
}

# ==========================================
# 🎨 ALTERNATIVE COLOR SCHEMES (Uncomment to use)
# ==========================================
# You can quickly switch between different color schemes by commenting/uncommenting sections below

# Option 1: Brighter Concrete (lighter cement color)
# HAZARD_COLORS = {
#     "FallFromHeight": (0.5, 0.0, 0.5),
#     "UnprotectedSidesAndEdges": (0.75, 0.75, 0.75),  # Light Concrete (191, 191, 191)
#     "FloorOpening": (1.0, 0.65, 0.0),
#     "WallOpening": (1.0, 0.0, 0.0),
#     "Stairway": (0.0, 1.0, 0.0),
#     "Stairways": (0.0, 1.0, 0.0),
#     "RoofOpening": (1.0, 0.65, 0.0),
#     "Unknown": (0.5, 0.5, 0.5)
# }

# Option 2: Dark Concrete (charcoal/asphalt color)
# HAZARD_COLORS = {
#     "FallFromHeight": (0.5, 0.0, 0.5),
#     "UnprotectedSidesAndEdges": (0.4, 0.4, 0.4),  # Dark Concrete (102, 102, 102)
#     "FloorOpening": (1.0, 0.65, 0.0),
#     "WallOpening": (1.0, 0.0, 0.0),
#     "Stairway": (0.0, 1.0, 0.0),
#     "Stairways": (0.0, 1.0, 0.0),
#     "RoofOpening": (1.0, 0.65, 0.0),
#     "Unknown": (0.5, 0.5, 0.5)
# }

# Option 3: Warm Concrete (beige/tan concrete with slight brown tint)
# HAZARD_COLORS = {
#     "FallFromHeight": (0.5, 0.0, 0.5),
#     "UnprotectedSidesAndEdges": (0.7, 0.68, 0.62),  # Warm Concrete (179, 173, 158)
#     "FloorOpening": (1.0, 0.65, 0.0),
#     "WallOpening": (1.0, 0.0, 0.0),
#     "Stairway": (0.0, 1.0, 0.0),
#     "Stairways": (0.0, 1.0, 0.0),
#     "RoofOpening": (1.0, 0.65, 0.0),
#     "Unknown": (0.5, 0.5, 0.5)
# }

# Option 4: Original Blue (from Table 3 research paper)
# HAZARD_COLORS = {
#     "FallFromHeight": (0.5, 0.0, 0.5),
#     "UnprotectedSidesAndEdges": (0.0, 0.0, 1.0),  # Blue (0, 0, 255)
#     "FloorOpening": (1.0, 0.65, 0.0),
#     "WallOpening": (1.0, 0.0, 0.0),
#     "Stairway": (0.0, 1.0, 0.0),
#     "Stairways": (0.0, 1.0, 0.0),
#     "RoofOpening": (1.0, 0.65, 0.0),
#     "Unknown": (0.5, 0.5, 0.5)
# }

# ==========================================
# SEVERITY COLOR SCHEME (RGB 0-1 scale)
# ==========================================
# Based on Table 3: Severity-based detection color scheme:
#   - Low: Green (0, 1, 0)
#   - Medium: Yellow (1, 1, 0)
#   - High: Red (1, 0, 0)
#
# 💡 TIP: You can customize severity colors here to match your organization's standards

SEVERITY_COLORS = {
    "Critical": (1.0, 0.0, 0.0),    # Red (treat Critical same as High)
    "High": (1.0, 0.0, 0.0),        # Red (1, 0, 0) - Table 3
    "Medium": (1.0, 1.0, 0.0),      # Yellow (1, 1, 0) - Table 3
    "Low": (0.0, 1.0, 0.0),         # Green (0, 1, 0) - Table 3
    "Unknown": (0.5, 0.5, 0.5)      # Gray
}

# ==========================================
# 🎨 ALTERNATIVE SEVERITY SCHEMES (Uncomment to use)
# ==========================================

# Option 1: Gradient from Red to Yellow (traffic light style)
# SEVERITY_COLORS = {
#     "Critical": (0.8, 0.0, 0.0),    # Dark Red
#     "High": (1.0, 0.2, 0.0),        # Red-Orange
#     "Medium": (1.0, 0.6, 0.0),      # Orange
#     "Low": (1.0, 0.9, 0.0),         # Light Yellow
#     "Unknown": (0.7, 0.7, 0.7)      # Light Gray
# }

# Option 2: Soft Pastel Colors (easier on the eyes)
# SEVERITY_COLORS = {
#     "Critical": (0.9, 0.4, 0.4),    # Soft Red
#     "High": (1.0, 0.6, 0.4),        # Peach
#     "Medium": (1.0, 0.9, 0.5),      # Soft Yellow
#     "Low": (0.5, 0.9, 0.5),         # Soft Green
#     "Unknown": (0.7, 0.7, 0.7)      # Light Gray
# }

# Option 3: Bold High-Contrast (for presentations/reports)
# SEVERITY_COLORS = {
#     "Critical": (1.0, 0.0, 0.0),    # Bright Red
#     "High": (1.0, 0.5, 0.0),        # Orange
#     "Medium": (1.0, 1.0, 0.0),      # Bright Yellow
#     "Low": (0.0, 1.0, 0.0),         # Bright Green
#     "Unknown": (0.5, 0.5, 0.5)      # Gray
# }

# ==========================================
# HAZARD TYPE PRIORITIES
# ==========================================
# When multiple hazards detected on same element, use highest priority
HAZARD_PRIORITY = {
    "FallFromHeight": 10,
    "UnprotectedSidesAndEdges": 9,
    "LeadingEdges": 8,
    "RoofOpening": 7,
    "FloorOpening": 7,
    "WallOpening": 7,
    "Scaffold": 6,
    "Ladder": 5,
    "Stairway": 5,
    "Excavation": 8
}

# ==========================================
# VISUALIZATION OPTIONS
# ==========================================
# Create marker geometry for openings (spheres/boxes at opening locations)
CREATE_OPENING_MARKERS = True
MARKER_SIZE = 500  # mm

# Color transparency (0.0 = fully transparent, 1.0 = fully opaque)
COLOR_TRANSPARENCY = 1.0

# Highlight mode
HIGHLIGHT_MODE = "ELEMENT"  # ELEMENT (color whole element) or MARKER (create markers)

# Edge detection for edge hazards
EDGE_DETECTION_TOLERANCE = 100  # mm - tolerance for detecting edges

# ==========================================
# REPORT CONFIGURATION
# ==========================================
REPORT_FORMAT = "both"  # "txt", "json", or "both"
INCLUDE_STATISTICS = True
INCLUDE_ELEMENT_DETAILS = True
GENERATE_SUMMARY_TABLE = True

# ==========================================
# ADVANCED OPTIONS
# ==========================================
# Skip elements that already have colors
PRESERVE_EXISTING_COLORS = False

# Create backup of original IFC
CREATE_BACKUP = True

# Verbose logging
VERBOSE = True

# Only color hazards above this severity (None = color all)
MIN_SEVERITY_TO_COLOR = None  # Options: "Low", "Medium", "High", "Critical", None

# ==========================================
# ELEMENT TYPE MAPPING
# ==========================================
# Map hazard types to IFC element types to search for
HAZARD_ELEMENT_TYPES = {
    "FallFromHeight": ["IfcSlab", "IfcRoof", "IfcPlate"],
    "UnprotectedSidesAndEdges": ["IfcSlab", "IfcRoof", "IfcPlate", "IfcWall"],
    "FloorOpening": ["IfcOpeningElement", "IfcSlab"],
    "WallOpening": ["IfcOpeningElement", "IfcWall", "IfcWindow", "IfcDoor"],
    "Stairway": ["IfcStair", "IfcStairFlight", "IfcRamp"],
    "RoofOpening": ["IfcOpeningElement", "IfcRoof"]
}

# ==========================================
# SEARCH TOLERANCES
# ==========================================
# Tolerance for location-based element search (mm)
LOCATION_SEARCH_TOLERANCE = 1000  # mm - how close an element must be to hazard location

# Z-axis tolerance for vertical alignment (mm)
Z_TOLERANCE = 500  # mm - vertical tolerance for matching elements

# ==========================================
# OUTPUT FILE NAMING
# ==========================================
# Naming convention for output files
OUTPUT_IFC_SUFFIX = "_colored"  # Will create: model_colored.ifc
OUTPUT_REPORT_NAME = "visualization_report"  # Will create: visualization_report.txt/json

# ==========================================
# IFC STYLING OPTIONS
# ==========================================
# Method for applying colors to IFC elements
STYLING_METHOD = "surface_style"  # "surface_style" or "presentation_style"

# Create separate representation for colored elements
CREATE_SEPARATE_REPRESENTATION = False

# ==========================================
# MARKER GEOMETRY OPTIONS
# ==========================================
# Shape of markers for voids/openings
MARKER_SHAPE = "box"  # "box" or "sphere"

# Marker positioning
MARKER_Z_OFFSET = 0  # mm - vertical offset for markers

# ==========================================
# PERFORMANCE OPTIONS
# ==========================================
# Process elements in batches for large models
BATCH_SIZE = 100  # Number of elements to process at once

# Skip elements that take too long to process
ELEMENT_TIMEOUT = 5  # seconds - max time to spend on one element

# ==========================================
# DEBUG OPTIONS
# ==========================================
DEBUG_MODE = False  # Enable detailed debug logging
SAVE_INTERMEDIATE_FILES = False  # Save IFC after each modification
LOG_ELEMENT_SEARCHES = False  # Log all element search attempts
