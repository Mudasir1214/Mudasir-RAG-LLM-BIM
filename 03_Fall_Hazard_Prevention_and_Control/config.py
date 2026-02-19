"""
Phase 3 - Configuration File
Customize OSHA guardrail dimensions and detection settings here
"""

# ============================================================================
# INPUT/OUTPUT PATHS
# ============================================================================
# Source IFC file (relative to Phase 3 directory)
SOURCE_IFC_PATH = None

# Output directory for results
OUTPUT_DIR = "output_data/hazard_prevention_and_control_results"



# ============================================================================
# OSHA-COMPLIANT GUARDRAIL DIMENSIONS (all in millimeters)
# ============================================================================
# Based on OSHA 1926.502 and international construction safety standards

# Guardrail heights
TOP_RAIL_HEIGHT = 1100.0      # Top rail: 42" (1100mm) ±3" OSHA standard
MID_RAIL_HEIGHT = 550.0       # Mid rail: halfway between top rail and platform
TOE_BOARD_HEIGHT = 100.0      # Toe board: 4" (100mm) minimum

# Component dimensions
RAIL_DIAMETER = 50.0          # Rail diameter: 50mm (cylindrical rails)
POST_DIAMETER = 80.0          # Post diameter: 80mm (sturdier support)
POST_SPACING = 2000.0         # Post spacing: 2000mm (2m) maximum

# Visual appearance
RAIL_COLOR = (1.0, 1.0, 0.0)  # Yellow (RGB 1.0, 1.0, 0.0) - OSHA safety color


# ============================================================================
# PERIMETER DETECTION SETTINGS
# ============================================================================
# How to sample and place guardrails around floor edges

PERIMETER_SAMPLE_SPACING = 2000.0   # Sample points every 2000mm (2m) along perimeter
EDGE_INSET = 200.0                  # Inset railings 200mm from edge (prevents overhang)
MIN_EDGE_LENGTH = 100.0             # Minimum edge length to place railing (100mm)


# ============================================================================
# BOUNDARY EXTRACTION METHOD
# ============================================================================
# Method for extracting floor slab boundaries
# True = Use mesh topology (accurate for L-shapes, U-shapes, complex geometries)
# False = Use ConvexHull (faster but only works for convex shapes)
USE_MESH_TOPOLOGY_EXTRACTION = True


# ============================================================================
# SAFETY FILTERS
# ============================================================================
# Ground level threshold - floors below this height are considered ground-level
# and don't require fall protection guardrails
GROUND_LEVEL_THRESHOLD_MM = 1500.0  # 1.5m - skip floors below this height

# Opening ground level threshold (more conservative)
OPENING_GROUND_THRESHOLD_MM = 500.0  # 0.5m - skip openings below this

# Collision detection tolerance for wall/column intersection
COLLISION_TOLERANCE_MM = 150.0      # 150mm - reduced for precision

# Existing railing detection radius
EXISTING_RAILING_RADIUS_MM = 5000.0  # 5m - search radius for existing railings


# ============================================================================
# LOGGING
# ============================================================================
VERBOSE_LOGGING = True  # Set to False for minimal output
