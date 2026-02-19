#!/usr/bin/env python3
"""
run_hazard_detection.py - MAIN RUNNER - FIXED VERSION

Just press the PLAY button in VS Code to run!
Configure settings in config.py
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

import numpy as np
try:
    import pandas as pd
except Exception:
    pd = None
try:
    from scipy.spatial import ConvexHull
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    ConvexHull = None
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tqdm import tqdm

try:
    import ifcopenshell
    import ifcopenshell.geom as geom
    import ifcopenshell.util.unit as unit_util
except Exception as e:
    print("ERROR: ifcopenshell not installed!")
    print("Install with: pip install ifcopenshell")
    sys.exit(1)

# Import configuration
try:
    from config import *
    import config  # Also import as module for getattr access
except ImportError:
    print("ERROR: config.py not found!")
    print("Please create config.py in the same directory.")
    sys.exit(1)

project_root_path = Path(__file__).resolve().parents[1]

# Enhanced stairway detection is now built-in
ENHANCED_STAIR_DETECTION = True

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# ==========================================
# REGULATIONS DATABASE
# ==========================================
REGULATIONS = {
    "FallFromHeight": {
        "OntologyID": "FH_001",
        "Category": "Elevated work hazards",
        "SpecificHazard": "Fall from height",
        "Definition": "Risk of falling from elevated work areas",
        "Threshold_mm": THRESHOLDS["FallFromHeight"],
        "Cause": "Lack of guardrails, unstable platforms, improper access",
        "Regulation": "JGJ80-2016, HKLD"
    },
    "UnprotectedSidesAndEdges": {
        "OntologyID": "FH_002",
        "Category": "Elevated work hazards",
        "SpecificHazard": "Unprotected sides and edges",
        "Definition": "Edges without fall protection",
        "Threshold_mm": THRESHOLDS["UnprotectedSidesAndEdges"],
        "Cause": "Absence of guardrails, unprotected edges",
        "Regulation": "Reg. 38B, CSSR Part VA"
    },
    "LeadingEdges": {
        "OntologyID": "FH_002",
        "Category": "Elevated work hazards",
        "SpecificHazard": "Leading edges",
        "Definition": "Work near unfinished or unprotected edges",
        "Threshold_mm": THRESHOLDS["LeadingEdges"],
        "Cause": "Activities near unfinished edges",
        "Regulation": "SSA-02/2021"
    },
    "FloorOpening": {
        "OntologyID": "FH_003",
        "Category": "Opening hazards",
        "SpecificHazard": "Floor openings (Horizontal)",
        "Definition": "Uncovered holes or openings in floors",
        "Threshold_mm": THRESHOLDS["FloorOpening"],
        "Cause": "Missing covers, unprotected floor openings",
        "Regulation": "GB10000-88"
    },
    "WallOpening": {
        "OntologyID": "FH_003",
        "Category": "Opening hazards",
        "SpecificHazard": "Wall openings (Vertical)",
        "Definition": "Uncovered holes or openings in walls",
        "Threshold_mm": THRESHOLDS["WallOpening"],
        "Cause": "Missing covers, unprotected wall openings",
        "Regulation": "GB10000-88"
    },
    "RoofOpening": {
        "OntologyID": "FH_003",
        "Category": "Opening hazards",
        "SpecificHazard": "Roof openings and skylights",
        "Definition": "Openings in roofs without protective measures",
        "Threshold_mm": THRESHOLDS["RoofOpening"],
        "Cause": "Unprotected roof penetrations",
        "Regulation": "SSA-01/2022"
    },
    "Scaffold": {
        "OntologyID": "FH_004",
        "Category": "Access hazards",
        "SpecificHazard": "Scaffolds",
        "Definition": "Work on scaffolds",
        "Threshold_mm": THRESHOLDS["Scaffold"],
        "Cause": "Missing guardrails, incomplete decking",
        "Regulation": "Reg. 38C-F, CSSR Part VA"
    },
    "Ladder": {
        "OntologyID": "FH_005",
        "Category": "Access hazards",
        "SpecificHazard": "Ladders",
        "Definition": "Use of portable ladders",
        "Threshold_mm": THRESHOLDS["Ladder"],
        "Cause": "Unsafe angle, inadequate extension, defective ladders",
        "Regulation": "Reg. 38C-F, CSSR Part VA"
    },
    "Stairway": {
        "OntologyID": "FH_006",
        "Category": "Access hazards",
        "SpecificHazard": "Stairways",
        "Definition": "Stairways without adequate safety measures",
        "Threshold_mm": THRESHOLDS["Stairway"],
        "Cause": "Missing handrails, unprotected sides",
        "Regulation": "Reg. 38C-F, CSSR Part VA"
    },
    "Excavation": {
        "OntologyID": "FH_001",
        "Category": "Excavation hazards",
        "SpecificHazard": "Excavation and pits",
        "Definition": "Ground openings posing fall hazards",
        "Threshold_mm": THRESHOLDS["Excavation"],
        "Cause": "Open pits or trenches, unprotected excavation edges",
        "Regulation": "Reg. 39-41, CSSR Part VI & VII"
    }
}

FALL_LEVELS = [
    ("Low-level fall", 0, 2000),
    ("Medium-level fall", 2000, 4500),
    ("High-level fall", 4500, float("inf"))
]

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def timestamp_str():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def create_output_folder():
    folder = os.path.join(OUTPUT_FOLDER, f"run_{timestamp_str()}")
    os.makedirs(folder, exist_ok=True)
    return folder

def setup_geom_context():
    try:
        settings = geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        return settings
    except Exception as e:
        logging.warning(f"Geometry settings creation failed: {e}")
        return geom.settings()

def get_mesh_vertices(ifc_entity, geom_settings):
    try:
        shape = geom.create_shape(geom_settings, ifc_entity)
        if hasattr(shape, 'geometry') and hasattr(shape.geometry, 'verts'):
            verts = shape.geometry.verts
            if len(verts) >= 9:
                return np.array(verts, dtype=float).reshape(-1, 3)
    except Exception:
        pass
    return None

def aabb_from_vertices(verts):
    if verts is None or len(verts) == 0:
        return None
    mins = verts.min(axis=0)
    maxs = verts.max(axis=0)
    return (mins.tolist(), maxs.tolist())

def aabb_dims(aabb):
    if aabb is None:
        return None
    mins = np.array(aabb[0])
    maxs = np.array(aabb[1])
    return (float(maxs[0]-mins[0]), float(maxs[1]-mins[1]), float(maxs[2]-mins[2]))

def overlap_xy(aabb1, aabb2, tol=1e-6):
    if aabb1 is None or aabb2 is None:
        return False
    min1 = np.array(aabb1[0])
    max1 = np.array(aabb1[1])
    min2 = np.array(aabb2[0])
    max2 = np.array(aabb2[1])
    if max1[0] < min2[0] - tol or max2[0] < min1[0] - tol:
        return False
    if max1[1] < min2[1] - tol or max2[1] < min1[1] - tol:
        return False
    return True

def detect_unit_factor(ifc):
    """FIXED: Detect unit conversion factor to mm"""
    
    # Check if forced unit factor is set in config
    if 'FORCE_UNIT_FACTOR' in globals() and FORCE_UNIT_FACTOR is not None:
        logging.info(f"Using forced unit factor: {FORCE_UNIT_FACTOR}")
        return FORCE_UNIT_FACTOR
    
    # Try to infer from actual geometry first
    try:
        test_elements = ifc.by_type("IfcSlab")[:3] + ifc.by_type("IfcWall")[:3]
        sample_dims = []
        
        for elem in test_elements:
            if hasattr(elem, 'ObjectPlacement'):
                # Try to get element dimensions from properties
                if hasattr(elem, 'IsDefinedBy'):
                    for definition in elem.IsDefinedBy:
                        if definition.is_a('IfcRelDefinesByProperties'):
                            prop_def = definition.RelatingPropertyDefinition
                            if prop_def.is_a('IfcPropertySet'):
                                for prop in prop_def.HasProperties:
                                    if prop.is_a('IfcPropertySingleValue'):
                                        if prop.Name in ['Height', 'Length', 'Width', 'Thickness']:
                                            if prop.NominalValue:
                                                val = float(prop.NominalValue.wrappedValue)
                                                sample_dims.append(val)
        
        if sample_dims:
            avg_dim = sum(sample_dims) / len(sample_dims)
            # If average dimension is between 0.1 and 20, likely meters
            if 0.1 < avg_dim < 20:
                logging.info(f"Detected meter units from element properties (avg dim: {avg_dim:.2f})")
                return 1000.0
            # If average dimension is between 100 and 20000, likely mm
            elif 100 < avg_dim < 20000:
                logging.info(f"Detected mm units from element properties (avg dim: {avg_dim:.2f})")
                return 1.0
    except Exception as e:
        logging.debug(f"Could not infer units from elements: {e}")
    
    # Check schema default
    default_factor = 1000.0  # Default to meters->mm
    if hasattr(ifc, 'schema'):
        if 'IFC4' in ifc.schema or 'IFC2X3' in ifc.schema:
            # These schemas typically use meters by default
            default_factor = 1000.0
    
    # Try official unit assignment
    try:
        unit_assignments = ifc.by_type("IfcUnitAssignment")
        if not unit_assignments:
            logging.warning(f"No unit assignment found, assuming meters (factor={default_factor})")
            return default_factor
        
        units = unit_assignments[0].Units
        for unit in units:
            if unit.is_a("IfcSIUnit"):
                unit_type = getattr(unit, "UnitType", "")
                if unit_type.upper() == "LENGTHUNIT":
                    name = getattr(unit, "Name", "METRE").upper()
                    prefix = getattr(unit, "Prefix", None)
                    
                    # Base conversion
                    base_conversions = {
                        "METRE": 1000.0,
                        "METER": 1000.0,
                        "MILLIMETRE": 1.0,
                        "MILLIMETER": 1.0,
                        "CENTIMETRE": 10.0,
                        "CENTIMETER": 10.0,
                        "FOOT": 304.8,
                        "INCH": 25.4
                    }
                    base_factor = base_conversions.get(name, 1000.0)
                    
                    # Apply prefix if exists
                    if prefix:
                        prefix_str = str(prefix).upper()
                        prefix_factors = {
                            "KILO": 1000.0,
                            "HECTO": 100.0,
                            "DECA": 10.0,
                            "DECI": 0.1,
                            "CENTI": 0.01,
                            "MILLI": 0.001,
                            "MICRO": 0.000001
                        }
                        if prefix_str in prefix_factors:
                            base_factor *= prefix_factors[prefix_str]
                    
                    logging.info(f"Detected {name} units (prefix: {prefix}), factor={base_factor}")
                    return base_factor
                    
    except Exception as e:
        logging.warning(f"Error reading unit assignment: {e}")
    
    # Check for conversion-based units
    try:
        conv_units = ifc.by_type("IfcConversionBasedUnit")
        for unit in conv_units:
            if hasattr(unit, 'UnitType') and unit.UnitType == "LENGTHUNIT":
                if hasattr(unit, 'ConversionFactor'):
                    factor = unit.ConversionFactor
                    if hasattr(factor, 'ValueComponent'):
                        value = float(factor.ValueComponent)
                        # This gives conversion to SI (meters)
                        return value * 1000.0
    except:
        pass
    
    logging.warning(f"Using default conversion factor: {default_factor}")
    return default_factor

def classify_opening_type(op_dims, op_name="", op_desc="", op_aabb=None):
    """IMPROVED: Classify opening based on dimensions and context"""
    if not op_dims:
        return "unknown"
    
    width = op_dims[0]
    depth = op_dims[1]
    height = op_dims[2]
    
    name_lower = (op_name or "").lower()
    desc_lower = (op_desc or "").lower()
    
    # Check keywords first
    if "skylight" in name_lower or "skylight" in desc_lower:
        return "skylight"
    if "roof" in name_lower or "roof" in desc_lower:
        return "roof"
    if "floor" in name_lower or "slab" in name_lower:
        return "floor"
    if "wall" in name_lower or "wall" in desc_lower:
        return "wall"
    if "door" in name_lower or "window" in name_lower:
        return "wall"
    
    # Enhanced dimension-based classification
    max_horizontal = max(width, depth)
    min_horizontal = min(width, depth)
    
    # Aspect ratios for classification
    horizontal_aspect = height / min_horizontal if min_horizontal > 0 else float('inf')
    vertical_aspect = min_horizontal / max_horizontal if max_horizontal > 0 else 0
    
    # HORIZONTAL OPENINGS (floor/roof) - height is smallest dimension
    if horizontal_aspect < OPENING_CLASSIFICATION["horizontal_ratio"]:
        # Check Z position if available to distinguish floor vs roof
        if op_aabb:
            z_pos = op_aabb[0][2]  # Bottom Z coordinate
            if z_pos > 5000:  # If opening is high up, likely roof
                return "roof"
        return "floor"
    
    # VERTICAL OPENINGS (wall) - one horizontal dim much smaller than other
    elif vertical_aspect < OPENING_CLASSIFICATION["vertical_ratio"]:
        return "wall"
    
    # Height-based classification
    elif height > max_horizontal * 0.8:
        return "wall"
    
    # Square-ish openings default to floor
    elif 0.5 < (min_horizontal / max_horizontal) < 2.0:
        if height < min_horizontal * 0.5:
            return "floor"
        else:
            return "wall"
    
    # Large horizontal openings
    elif max_horizontal > 1000 and height < 500:
        return "floor"
    
    # Default to floor for safety
    return "floor"

def calculate_severity(detected_value, threshold):
    """Calculate severity based on threshold exceedance"""
    if detected_value < threshold * 0.5:
        return "Low"
    elif detected_value < threshold:
        return "Medium"
    elif detected_value < threshold * 1.5:
        return "High"
    else:
        return "Critical"

def extract_location_from_aabb(aabb):
    """Extract center point location from AABB bounding box"""
    if not aabb:
        return None
    try:
        mins = np.array(aabb[0])
        maxs = np.array(aabb[1])
        center = (mins + maxs) / 2.0
        return {
            "X": round(float(center[0]), 2),
            "Y": round(float(center[1]), 2),
            "Z": round(float(center[2]), 2)
        }
    except Exception as e:
        logging.debug(f"Could not extract location from AABB: {e}")
        return None

def is_edge_opening(opening_aabb, slabs, edge_threshold=1000):
    """
    Check if an opening is near the edge of a slab (more dangerous)

    Args:
        opening_aabb: Opening bounding box
        slabs: List of slab elements
        edge_threshold: Distance from slab edge to consider as edge opening (mm)

    Returns:
        True if opening is within edge_threshold of any slab perimeter
    """
    if not opening_aabb or not slabs:
        return False

    op_center = np.array([
        (opening_aabb[0][0] + opening_aabb[1][0]) / 2.0,
        (opening_aabb[0][1] + opening_aabb[1][1]) / 2.0,
        (opening_aabb[0][2] + opening_aabb[1][2]) / 2.0
    ])

    for slab in slabs:
        slab_aabb = slab.get("AABB_mm")
        if not slab_aabb:
            continue

        # Check if opening is at approximately the same Z level as slab
        slab_z = (slab_aabb[0][2] + slab_aabb[1][2]) / 2.0
        if abs(op_center[2] - slab_z) > 500:  # 500mm Z tolerance
            continue

        # Check if opening overlaps with slab in XY
        if not overlap_xy(opening_aabb, slab_aabb, tol=100):
            continue

        # Calculate distance from opening center to slab edges
        slab_min = np.array(slab_aabb[0][:2])  # X, Y min
        slab_max = np.array(slab_aabb[1][:2])  # X, Y max
        op_xy = op_center[:2]

        # Distance to each edge
        dist_to_left = abs(op_xy[0] - slab_min[0])
        dist_to_right = abs(op_xy[0] - slab_max[0])
        dist_to_bottom = abs(op_xy[1] - slab_min[1])
        dist_to_top = abs(op_xy[1] - slab_max[1])

        min_dist = min(dist_to_left, dist_to_right, dist_to_bottom, dist_to_top)

        if min_dist <= edge_threshold:
            return True

    return False

def build_hazard_record(reg_key, detected_value_mm, element_context, severity, notes=None, location=None):
    """Build hazard record with Location coordinates for visualization"""
    reg = REGULATIONS.get(reg_key, {})
    rec = {
        "HazardType": reg_key,  # Add HazardType for Phase 3 compatibility
        "OntologyID": reg.get("OntologyID", ""),
        "Category": reg.get("Category", "Unknown"),
        "SpecificHazard": reg.get("SpecificHazard", reg_key),
        "Definition": reg.get("Definition", ""),
        "Threshold_mm": reg.get("Threshold_mm"),
        "DetectedValue_mm": round(detected_value_mm, 2),
        "Cause": reg.get("Cause", ""),
        "Regulation": reg.get("Regulation", ""),
        "Severity": severity,
        "ElementContext": element_context,
        "Notes": notes or []
    }
    # Add Location if provided (critical for Phase 3 marker creation)
    if location:
        rec["Location"] = location
    return rec

def fall_level_classification(elevation_mm):
    for label, low, high in FALL_LEVELS:
        if elevation_mm >= low and elevation_mm < high:
            return label
    return FALL_LEVELS[-1][0]

def get_multi_floor_levels(op_aabb, typical_floor_height=3000):
    """
    Detect if an opening spans multiple floors and return the Z-levels for each floor

    Args:
        op_aabb: Opening bounding box (min, max)
        typical_floor_height: Typical floor-to-floor height in mm (default 3000mm)

    Returns:
        List of Z-levels (center points) for each floor the opening affects
    """
    if not op_aabb:
        return []

    z_min = op_aabb[0][2]
    z_max = op_aabb[1][2]
    opening_height = z_max - z_min

    # More conservative threshold: only split if clearly taller than 1.5x floor height
    # This prevents normal tall openings (2.5m-3m) from being incorrectly split
    if opening_height > typical_floor_height * 1.5:  # 4500mm threshold (1.5 floors)
        # Calculate how many floors this opening affects
        num_floors = max(2, int(opening_height / typical_floor_height) + 1)

        # Cap at reasonable maximum (avoid thousands of markers for terrain elements)
        num_floors = min(num_floors, 4)  # Max 4 floor levels

        # Generate Z-levels for each floor (evenly distributed within the opening)
        z_levels = []
        for i in range(num_floors):
            # Place marker at center of each floor segment
            z_level = z_min + (opening_height / num_floors) * (i + 0.5)
            z_levels.append(z_level)

        return z_levels

    # Single floor opening - return center Z
    return [(z_min + z_max) / 2.0]

def is_opening_filled(opening_id, ifc_file, doors, windows):
    """
    Check if an opening is filled with a door or window

    In IFC, openings can be filled via IfcRelFillsElement relationship
    or we can check if a door/window references this opening

    Args:
        opening_id: GlobalId of the opening element
        ifc_file: IFC file object
        doors: List of door metadata
        windows: List of window metadata

    Returns:
        True if opening is filled, False otherwise
    """
    if not ifc_file:
        return False

    try:
        # Try to get the opening entity
        opening_entity = ifc_file.by_guid(opening_id)

        # Check if the opening has any filling elements (via HasFillings relationship)
        if hasattr(opening_entity, 'HasFillings') and opening_entity.HasFillings:
            for rel in opening_entity.HasFillings:
                if rel.is_a('IfcRelFillsElement'):
                    filling_element = rel.RelatedBuildingElement
                    if filling_element and (filling_element.is_a('IfcDoor') or filling_element.is_a('IfcWindow')):
                        logging.debug(f"  Opening {opening_id} is filled by {filling_element.is_a()}")
                        return True

        # Alternative check: Look through doors/windows to see if any reference this opening
        for door in doors:
            door_id = door.get("GlobalId")
            try:
                door_entity = ifc_file.by_guid(door_id)
                if hasattr(door_entity, 'FillsVoids') and door_entity.FillsVoids:
                    for rel in door_entity.FillsVoids:
                        if rel.is_a('IfcRelFillsElement'):
                            if rel.RelatingOpeningElement and rel.RelatingOpeningElement.GlobalId == opening_id:
                                logging.debug(f"  Opening {opening_id} is filled by door {door_id}")
                                return True
            except:
                pass

        for window in windows:
            window_id = window.get("GlobalId")
            try:
                window_entity = ifc_file.by_guid(window_id)
                if hasattr(window_entity, 'FillsVoids') and window_entity.FillsVoids:
                    for rel in window_entity.FillsVoids:
                        if rel.is_a('IfcRelFillsElement'):
                            if rel.RelatingOpeningElement and rel.RelatingOpeningElement.GlobalId == opening_id:
                                logging.debug(f"  Opening {opening_id} is filled by window {window_id}")
                                return True
            except:
                pass

    except Exception as e:
        logging.debug(f"Error checking if opening {opening_id} is filled: {e}")

    return False

def extract_slab_perimeter_2d(vertices_mm, z_tolerance=100):
    """
    Extract the perimeter of a slab from its 3D vertices by projecting to 2D.
    Uses boundary edge detection for irregular/concave shapes.

    Args:
        vertices_mm: Nx3 numpy array of vertices in mm
        z_tolerance: Tolerance for grouping vertices at same Z level (mm)

    Returns:
        Perimeter vertices as Nx2 array (X, Y) at top surface, or None if failed
    """
    if vertices_mm is None or len(vertices_mm) < 3:
        return None

    try:
        # Find the top surface vertices (maximum Z level within tolerance)
        z_values = vertices_mm[:, 2]
        z_max = np.max(z_values)

        # Get vertices at the top surface
        top_mask = z_values >= (z_max - z_tolerance)
        top_verts = vertices_mm[top_mask][:, :2]  # Project to XY plane

        if len(top_verts) < 3:
            return None

        # Remove duplicate points with tolerance
        from scipy.spatial.distance import pdist, squareform

        if len(top_verts) > 1:
            # Find duplicates within 10mm tolerance
            if len(top_verts) > 1:
                dists = squareform(pdist(top_verts))
                unique_mask = np.ones(len(top_verts), dtype=bool)
                for i in range(len(top_verts)):
                    if unique_mask[i]:
                        # Mark nearby points as duplicates
                        duplicates = dists[i] < 10  # 10mm tolerance
                        duplicates[i] = False  # Keep the first one
                        unique_mask[duplicates] = False

                unique_verts = top_verts[unique_mask]
            else:
                unique_verts = top_verts
        else:
            unique_verts = top_verts

        if len(unique_verts) < 3:
            return None

        # For irregular/concave shapes, we need actual boundary detection
        # Strategy: Create a very fine convex hull as starting approximation,
        # then refine using actual vertex positions

        if SCIPY_AVAILABLE and ConvexHull is not None:
            try:
                # First try convex hull (works for rectangular/convex shapes)
                hull = ConvexHull(unique_verts)
                hull_verts = unique_verts[hull.vertices]

                # Check if this is likely a concave shape by comparing
                # hull area vs minimum bounding box area
                hull_area = hull.volume  # In 2D, "volume" is area

                # Calculate bounding box
                x_span = np.ptp(unique_verts[:, 0])
                y_span = np.ptp(unique_verts[:, 1])
                bbox_area = x_span * y_span

                # For L-shaped and irregular floors, use convex hull
                # Convex hull works better than trying to detect concave boundaries
                # The 50mm inset will keep markers on the slab surface
                return hull_verts

            except Exception as e:
                logging.debug(f"Convex hull failed: {e}, using all unique vertices")
                return unique_verts
        else:
            # SciPy not available - basic angle-based sorting
            center = np.mean(unique_verts, axis=0)
            angles = np.arctan2(unique_verts[:, 1] - center[1],
                               unique_verts[:, 0] - center[0])
            sorted_indices = np.argsort(angles)
            return unique_verts[sorted_indices]

    except Exception as e:
        logging.debug(f"Failed to extract perimeter: {e}")
        return None


def point_in_polygon_2d(point, polygon):
    """
    Check if a 2D point is inside a polygon using ray casting algorithm.

    Args:
        point: (x, y) tuple or array
        polygon: Nx2 array of polygon vertices

    Returns:
        True if point is inside polygon, False otherwise
    """
    if polygon is None or len(polygon) < 3:
        return False

    x, y = point[0], point[1]
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def sample_perimeter_edges(perimeter_verts, marker_spacing=2000, inset_distance=50):
    """
    Sample points along a perimeter at regular intervals.
    Places markers directly on edges with minimal inset for stability.

    Args:
        perimeter_verts: Nx2 array of perimeter vertices in order
        marker_spacing: Distance between markers (mm)
        inset_distance: Minimal distance to inset markers from edge (mm) - default 50mm for stability

    Returns:
        List of (x, y) marker positions
    """
    if perimeter_verts is None or len(perimeter_verts) < 2:
        return []

    markers = []
    n_verts = len(perimeter_verts)

    # Calculate polygon center for inward direction
    center = np.mean(perimeter_verts, axis=0)

    # Process each edge of the perimeter
    for i in range(n_verts):
        v1 = perimeter_verts[i]
        v2 = perimeter_verts[(i + 1) % n_verts]

        # Calculate edge vector and length
        edge_vec = v2 - v1
        edge_length = np.linalg.norm(edge_vec)

        if edge_length < 100:  # Skip very short edges (< 100mm)
            continue

        # Normalize edge vector
        edge_dir = edge_vec / edge_length

        # FILTER: Skip diagonal edges for L-shaped floors
        # Diagonal edges are artifacts from convex hull that cut through interior space
        # Only keep STRICTLY axis-aligned edges (horizontal or vertical) which are real building edges
        dx = abs(edge_dir[0])
        dy = abs(edge_dir[1])

        # STRICT axis-alignment check:
        # - For horizontal: dx must be very close to 1.0 AND dy must be very close to 0.0
        # - For vertical: dy must be very close to 1.0 AND dx must be very close to 0.0
        # Tolerance: allow max 5 degrees off-axis (cos(5°) ≈ 0.996)
        is_horizontal = dx > 0.995 and dy < 0.1  # Almost purely X-direction
        is_vertical = dy > 0.995 and dx < 0.1    # Almost purely Y-direction
        is_axis_aligned = is_horizontal or is_vertical

        if not is_axis_aligned:
            # Diagonal or off-axis edge - skip to avoid markers in empty space
            logging.debug(f"    Skipping diagonal edge (dx={dx:.3f}, dy={dy:.3f}, len={edge_length:.0f}mm)")
            continue

        # Calculate perpendicular inward normal
        # Perpendicular to edge (rotate 90 degrees)
        edge_normal = np.array([-edge_dir[1], edge_dir[0]])

        # Ensure normal points inward (toward center)
        edge_midpoint = (v1 + v2) / 2.0
        to_center = center - edge_midpoint
        if np.dot(to_center, edge_normal) < 0:
            edge_normal = -edge_normal

        # Determine number of markers for this edge
        if edge_length < marker_spacing * 0.5:
            # Short edge - place one marker at midpoint
            num_markers = 1
            marker_positions = [0.5]
        else:
            # Long edge - place markers at regular intervals
            num_markers = max(1, int(edge_length / marker_spacing))
            # Create evenly spaced positions along edge (0.0 to 1.0)
            marker_positions = [(j + 0.5) / num_markers for j in range(num_markers)]

        # Place markers
        for t in marker_positions:
            # Point on edge
            point_on_edge = v1 + t * edge_vec

            # Apply minimal inset (50mm default - just enough to ensure it's "on" the slab)
            inset_point = point_on_edge + edge_normal * inset_distance

            markers.append((float(inset_point[0]), float(inset_point[1])))

    return markers


def detect_unprotected_slab_edges(slab_aabb, slab_name, railings, walls, min_height=2000, marker_spacing=2000, slab_vertices=None):
    """
    Detect unprotected edges of a slab and return marker locations.
    Now uses actual slab geometry when available for irregular shapes.
    Checks for BOTH railings AND walls for edge protection.

    Args:
        slab_aabb: Slab bounding box (min, max)
        slab_name: Slab name for logging
        railings: List of railing metadata
        walls: List of wall metadata
        min_height: Minimum height to check (mm)
        marker_spacing: Distance between markers along edge (mm)
        slab_vertices: Optional Nx3 array of actual slab vertices (for irregular shapes)

    Returns:
        List of unprotected edge marker locations with edge direction
    """
    if not slab_aabb:
        return []

    # Get slab parameters
    x_min, y_min, z_min = slab_aabb[0]
    x_max, y_max, z_max = slab_aabb[1]
    z_top = z_max  # Top surface of slab

    # Only check elevated slabs
    if z_top < min_height:
        return []

    min_railing_height = 760  # mm
    wall_tolerance = 800  # mm - distance to consider wall as protecting an edge

    # ==========================================
    # GEOMETRY-AWARE APPROACH: Use actual perimeter when available
    # ==========================================
    perimeter_verts = None
    candidate_markers_xy = []
    use_actual_perimeter = False

    # Extract perimeter for marker generation (if geometry available)
    if slab_vertices is not None:
        perimeter_verts = extract_slab_perimeter_2d(slab_vertices, z_tolerance=100)
        if perimeter_verts is not None and len(perimeter_verts) >= 3:
            use_actual_perimeter = True
            logging.debug(f"  {slab_name}: Using actual perimeter geometry ({len(perimeter_verts)} vertices)")
        else:
            logging.debug(f"  {slab_name}: Falling back to AABB edges")
            perimeter_verts = None

    # ==========================================
    # GENERATE CANDIDATE MARKERS
    # ==========================================
    if use_actual_perimeter:
        # For irregular shapes (L-shaped, etc.): Generate markers from ACTUAL perimeter edges
        # This ensures markers are placed on the real edges, not on AABB "ghost" edges
        candidate_markers_xy = sample_perimeter_edges(
            perimeter_verts,
            marker_spacing=marker_spacing,
            inset_distance=50
        )
        logging.debug(f"  {slab_name}: Generated {len(candidate_markers_xy)} markers from actual perimeter")
    else:
        # Fallback: Use AABB edges for simple rectangular slabs
        edges = [
            {"name": "North", "x1": x_min, "y1": y_max, "x2": x_max, "y2": y_max},
            {"name": "South", "x1": x_min, "y1": y_min, "x2": x_max, "y2": y_min},
            {"name": "East",  "x1": x_max, "y1": y_min, "x2": x_max, "y2": y_max},
            {"name": "West",  "x1": x_min, "y1": y_min, "x2": x_min, "y2": y_max},
        ]

        # Generate candidate markers from AABB edges
        for edge in edges:
            edge_length = max(
                abs(edge["x2"] - edge["x1"]),
                abs(edge["y2"] - edge["y1"])
            )
            num_markers = max(1, int(edge_length / marker_spacing))

            for i in range(num_markers):
                t = (i + 0.5) / num_markers
                marker_x = edge["x1"] + t * (edge["x2"] - edge["x1"])
                marker_y = edge["y1"] + t * (edge["y2"] - edge["y1"])
                candidate_markers_xy.append((marker_x, marker_y))

    # ==========================================
    # CHECK PROTECTION FOR EACH CANDIDATE MARKER
    # ==========================================
    unprotected_markers = []

    for idx, (marker_x, marker_y) in enumerate(candidate_markers_xy):
        marker_protected = False

        # Validation: For AABB-based markers only, check they're on the actual slab
        # For perimeter-based markers, they're already guaranteed to be on the slab edges
        if not use_actual_perimeter and perimeter_verts is not None:
            # AABB markers need validation against actual perimeter
            is_inside = point_in_polygon_2d((marker_x, marker_y), perimeter_verts)

            # Calculate distance to nearest perimeter edge
            min_dist_to_perimeter = float('inf')
            n_verts = len(perimeter_verts)

            for i in range(n_verts):
                v1 = perimeter_verts[i]
                v2 = perimeter_verts[(i + 1) % n_verts]

                # Calculate distance from marker to line segment v1-v2
                edge_vec = v2 - v1
                marker_vec = np.array([marker_x, marker_y]) - v1

                edge_len_sq = np.dot(edge_vec, edge_vec)
                if edge_len_sq > 0:
                    # Project marker onto edge
                    t = max(0, min(1, np.dot(marker_vec, edge_vec) / edge_len_sq))
                    projection = v1 + t * edge_vec
                    dist = np.linalg.norm(np.array([marker_x, marker_y]) - projection)
                    min_dist_to_perimeter = min(min_dist_to_perimeter, dist)

            # Marker must be inside slab OR within 300mm of perimeter edge
            if not is_inside and min_dist_to_perimeter > 300:
                # Marker is too far outside the slab - skip it
                logging.debug(f"    Marker at ({marker_x:.0f}, {marker_y:.0f}) outside slab (dist={min_dist_to_perimeter:.0f}mm) - skipping")
                continue

        # 1. Check for RAILING protection
        # Railing protects if it runs along the edge where this marker is located
        for r in railings:
            r_aabb = r.get("AABB_mm")
            r_dims = r.get("Dims_mm")

            if not r_aabb or not r_dims:
                continue

            # Check if railing is tall enough
            if r_dims[2] < min_railing_height:
                continue

            # Check if railing is at similar Z-level (within tolerance)
            r_z_center = (r_aabb[0][2] + r_aabb[1][2]) / 2.0
            if abs(r_z_center - z_top) > 1500:  # 1.5m Z tolerance
                continue

            # Get railing bounds
            r_x_min, r_y_min = r_aabb[0][0], r_aabb[0][1]
            r_x_max, r_y_max = r_aabb[1][0], r_aabb[1][1]

            tolerance = 600  # 600mm tolerance for edge proximity

            # Check if marker is within railing's area (with tolerance)
            # This allows boundary railings to protect edges effectively
            if (r_x_min - tolerance <= marker_x <= r_x_max + tolerance and
                r_y_min - tolerance <= marker_y <= r_y_max + tolerance):
                marker_protected = True
                logging.debug(f"    Marker at ({marker_x:.0f}, {marker_y:.0f}) protected by railing")
                break

        # 2. Check for WALL protection (if not already protected by railing)
        # Walls along edges provide fall protection
        if not marker_protected and walls:
            for w in walls:
                w_aabb = w.get("AABB_mm")
                if not w_aabb:
                    continue

                w_x_min, w_y_min, w_z_min = w_aabb[0]
                w_x_max, w_y_max, w_z_max = w_aabb[1]

                # Wall must provide adequate fall protection
                if w_z_min > z_top + 500:
                    continue  # Wall starts too high above the slab

                if w_z_max < z_top + min_railing_height:
                    continue  # Wall not tall enough for fall protection

                # Check if marker is near this wall (boundary wall protection)
                # Use generous tolerance for walls as they often run along entire edges
                if (w_x_min - wall_tolerance <= marker_x <= w_x_max + wall_tolerance and
                    w_y_min - wall_tolerance <= marker_y <= w_y_max + wall_tolerance):
                    marker_protected = True
                    logging.debug(f"    Marker at ({marker_x:.0f}, {marker_y:.0f}) protected by wall")
                    break

        # If marker is not protected, add it to unprotected list
        if not marker_protected:
            # Determine edge direction by position in AABB
            edge_name = "Edge"
            if abs(marker_y - y_max) < 100:
                edge_name = "North"
            elif abs(marker_y - y_min) < 100:
                edge_name = "South"
            elif abs(marker_x - x_max) < 100:
                edge_name = "East"
            elif abs(marker_x - x_min) < 100:
                edge_name = "West"

            unprotected_markers.append({
                "X": round(marker_x, 2),
                "Y": round(marker_y, 2),
                "Z": round(z_top, 2),
                "Edge": edge_name,
                "EdgeIndex": idx + 1,
                "TotalMarkers": len(candidate_markers_xy)
            })

    return unprotected_markers

def has_guardrail_protection(opening_aabb, railings, min_railing_height=None, xy_tolerance=None, z_tolerance=None):
    """
    Check if an opening has adequate guardrail protection nearby

    Protection requires:
    1. Railing overlaps with opening in XY plane (within xy_tolerance)
    2. Railing is at approximately the same Z level as opening (within z_tolerance)
    3. Railing is tall enough (>= min_railing_height)

    This prevents a guardrail on floor 1 from protecting the same opening on floors 2-3.
    """
    if not opening_aabb or not railings:
        return False

    # Use config values or defaults
    if min_railing_height is None:
        min_railing_height = globals().get('GUARDRAIL_HEIGHT_MIN', 760)
    if xy_tolerance is None:
        xy_tolerance = globals().get('GUARDRAIL_XY_TOLERANCE', 500)
    if z_tolerance is None:
        z_tolerance = globals().get('GUARDRAIL_Z_TOLERANCE', 1500)

    # Get opening Z range (bottom and top)
    opening_z_min = opening_aabb[0][2]
    opening_z_max = opening_aabb[1][2]
    opening_z_center = (opening_z_min + opening_z_max) / 2.0

    for r in railings:
        r_aabb = r.get("AABB_mm")
        r_dims = r.get("Dims_mm")

        if not r_aabb or not r_dims:
            continue

        # Get railing Z position
        railing_z_min = r_aabb[0][2]
        railing_z_max = r_aabb[1][2]
        railing_z_center = (railing_z_min + railing_z_max) / 2.0

        # Check if railing is at approximately the same Z level as opening
        z_diff = abs(opening_z_center - railing_z_center)
        if z_diff > z_tolerance:
            # Railing is on a different floor - doesn't protect this opening
            continue

        # Check if railing overlaps with opening in XY plane
        if overlap_xy(opening_aabb, r_aabb, tol=xy_tolerance):
            # Check if railing is tall enough
            if r_dims[2] >= min_railing_height:
                return True

    return False

# ==========================================
# ENHANCED 3D-SPATIAL STAIRWAY DETECTION
# ==========================================
def get_stair_full_geometry(stair_entity, stair_meta, unit_factor):
    """
    Extract comprehensive 3D geometry for a stairway

    Returns dict with geometry info or None
    """
    aabb = stair_meta.get("AABB_mm")

    if not aabb:
        return None

    # Extract bounding box
    min_pt = np.array(aabb[0])
    max_pt = np.array(aabb[1])

    # Calculate stair properties
    width = max_pt[0] - min_pt[0]
    depth = max_pt[1] - min_pt[1]
    height = max_pt[2] - min_pt[2]

    # Center point
    center = (min_pt + max_pt) / 2.0

    # Bottom and top levels
    bottom_z = min_pt[2]
    top_z = max_pt[2]

    geometry = {
        'aabb': aabb,
        'min_point': min_pt.tolist(),
        'max_point': max_pt.tolist(),
        'center': center.tolist(),
        'width': width,
        'depth': depth,
        'height': height,
        'bottom_z': bottom_z,
        'top_z': top_z,
        'volume': width * depth * height
    }

    # Try to get exact placement from IFC
    try:
        if hasattr(stair_entity, 'ObjectPlacement') and stair_entity.ObjectPlacement:
            placement = stair_entity.ObjectPlacement
            if placement.is_a('IfcLocalPlacement'):
                rel_placement = placement.RelativePlacement
                if rel_placement and rel_placement.is_a('IfcAxis2Placement3D'):
                    loc = rel_placement.Location
                    if loc and hasattr(loc, 'Coordinates'):
                        coords = loc.Coordinates
                        geometry['ifc_location'] = {
                            'X': float(coords[0]) * unit_factor,
                            'Y': float(coords[1]) * unit_factor,
                            'Z': float(coords[2]) * unit_factor if len(coords) > 2 else bottom_z
                        }
    except Exception:
        pass

    return geometry

def check_stair_3d_spatial_protection(stair_geom, railing_aabb, railing_dims):
    """
    Check 3D spatial relationship between stair and railing

    Returns dict with protection analysis
    """
    if not railing_aabb or not railing_dims:
        return {'protected': False, 'reason': 'Missing railing geometry'}

    # Get tolerances from config module (not globals!)
    min_guardrail_height = getattr(config, 'GUARDRAIL_HEIGHT_MIN', 760)
    xy_proximity_tolerance = getattr(config, 'STAIR_GUARDRAIL_XY_TOLERANCE', 1500)
    z_level_tolerance = getattr(config, 'STAIR_GUARDRAIL_Z_TOLERANCE', 2000)
    min_overlap_percentage = getattr(config, 'STAIR_MIN_OVERLAP_PERCENTAGE', 0.3)

    stair_min = np.array(stair_geom['min_point'])
    stair_max = np.array(stair_geom['max_point'])

    rail_min = np.array(railing_aabb[0])
    rail_max = np.array(railing_aabb[1])

    # 1. CHECK RAILING HEIGHT
    railing_height = railing_dims[2]
    if railing_height < min_guardrail_height:
        return {
            'protected': False,
            'reason': f'Railing too short ({railing_height:.0f}mm < {min_guardrail_height}mm)'
        }

    # 2. CHECK Z-LEVEL ALIGNMENT
    stair_z_center = (stair_min[2] + stair_max[2]) / 2.0
    rail_z_center = (rail_min[2] + rail_max[2]) / 2.0

    z_diff = abs(stair_z_center - rail_z_center)

    if z_diff > z_level_tolerance:
        return {
            'protected': False,
            'reason': f'Railing on different level (Z-diff: {z_diff:.0f}mm)',
            'z_difference': z_diff
        }

    # 3. CHECK XY OVERLAP/PROXIMITY
    overlap_x_start = max(stair_min[0], rail_min[0])
    overlap_x_end = min(stair_max[0], rail_max[0])
    overlap_x = max(0, overlap_x_end - overlap_x_start)

    overlap_y_start = max(stair_min[1], rail_min[1])
    overlap_y_end = min(stair_max[1], rail_max[1])
    overlap_y = max(0, overlap_y_end - overlap_y_start)

    # Calculate stair dimensions
    stair_width = stair_max[0] - stair_min[0]
    stair_depth = stair_max[1] - stair_min[1]

    # Calculate overlap percentage
    if overlap_x > 0 and overlap_y > 0:
        overlap_area = overlap_x * overlap_y
        stair_area = stair_width * stair_depth
        overlap_percentage = overlap_area / stair_area if stair_area > 0 else 0

        if overlap_percentage >= min_overlap_percentage:
            return {
                'protected': True,
                'reason': f'Adequate overlap ({overlap_percentage*100:.1f}%)',
                'overlap_percentage': overlap_percentage,
                'z_difference': z_diff
            }

    # 4. CHECK PROXIMITY (if no direct overlap)
    if overlap_x_end <= overlap_x_start:
        dist_x = min(abs(stair_min[0] - rail_max[0]), abs(stair_max[0] - rail_min[0]))
    else:
        dist_x = 0

    if overlap_y_end <= overlap_y_start:
        dist_y = min(abs(stair_min[1] - rail_max[1]), abs(stair_max[1] - rail_min[1]))
    else:
        dist_y = 0

    min_distance = np.sqrt(dist_x**2 + dist_y**2)

    if min_distance <= xy_proximity_tolerance:
        return {
            'protected': True,
            'reason': f'Railing nearby ({min_distance:.0f}mm)',
            'proximity_distance': min_distance,
            'z_difference': z_diff
        }

    return {
        'protected': False,
        'reason': f'Railing too far ({min_distance:.0f}mm)',
        'proximity_distance': min_distance,
        'z_difference': z_diff
    }

def detect_stairway_hazards_enhanced(element_meta, by_type, railings, unit_factor, ifc_file=None, config=None):
    """
    Enhanced stairway hazard detection using 3D spatial analysis
    """
    hazards = []
    stairs = by_type.get("IfcStair", [])
    
    logging.info(f"  Starting enhanced detection for {len(stairs)} stairs...")
    
    for st in stairs:
        st_id = st.get("GlobalId")
        st_name = st.get("Name") or st_id

        logging.info(f"  Checking stair: {st_name} ({st_id})")

        # Get entity
        st_entity = None
        if ifc_file:
             try:
                 st_entity = ifc_file.by_guid(st_id)
             except Exception as e:
                 logging.warning(f"  Failed to get entity for stair {st_name} ({st_id}): {e}")

        if not st_entity:
            # Fallback if by_guid fails or ifc_file not provided (though it should be)
            logging.warning(f"  ⚠ SKIPPING STAIR {st_name} ({st_id}) - Could not resolve IFC entity")
            logging.warning(f"     This stair was found in geometry processing but cannot be accessed for hazard detection.")
            logging.warning(f"     This may indicate a corrupt or malformed IFC file.")
            continue

        # Check for manual exclusion
        ignored_ids = getattr(config, 'IGNORED_ELEMENT_IDS', [])
        if st_id in ignored_ids or str(getattr(st_entity, 'id', '')) in ignored_ids:
            logging.info(f"  ✓ STAIR {st_name} ({st_id}) MANUALLY EXCLUDED (Assumed Safe)")
            continue

        # ---------------------------------------------------------
        # SEMANTIC CHECK: Is railing part of the stair assembly?
        # ---------------------------------------------------------
        has_semantic_protection = False
        min_guardrail_height = getattr(config, 'GUARDRAIL_HEIGHT_MIN', 760)

        if hasattr(st_entity, 'IsDecomposedBy'):
            for rel in st_entity.IsDecomposedBy:
                if rel.is_a('IfcRelAggregates'):
                    for part in rel.RelatedObjects:
                        if part.is_a('IfcRailing'):
                            # Found a railing child - now check if it's tall enough
                            part_id = part.GlobalId

                            # Find the railing metadata to check height
                            railing_meta = None
                            for r in railings:
                                if r.get("GlobalId") == part_id:
                                    railing_meta = r
                                    break

                            if railing_meta:
                                r_dims = railing_meta.get("Dims_mm")
                                if r_dims and r_dims[2] >= min_guardrail_height:
                                    has_semantic_protection = True
                                    logging.info(f"    - Semantically protected by attached railing: {part.Name} (height: {r_dims[2]:.0f}mm)")
                                    break
                                else:
                                    actual_height = r_dims[2] if r_dims else 0
                                    logging.info(f"    - Railing found but too short: {part.Name} (height: {actual_height:.0f}mm < {min_guardrail_height}mm)")
                            else:
                                logging.debug(f"    - Railing found but no geometry data: {part.Name}")

                if has_semantic_protection: break

        if has_semantic_protection:
             is_protected = True
             logging.info(f"  ✓ STAIR {st_name} PROTECTED (Semantic Connection with adequate railing)")
             # Skip spatial check if semantically protected
             continue


        st_geom = get_stair_full_geometry(st_entity, st, unit_factor)

        # If the stair itself has no geometry, it might be an assembly with children
        # Combine geometry from all children (flights/landings) to get full stair extent
        if not st_geom:
            if hasattr(st_entity, 'IsDecomposedBy'):
                child_aabbs = []
                for rel in st_entity.IsDecomposedBy:
                    if hasattr(rel, 'RelatedObjects'):
                        for child in rel.RelatedObjects:
                            # Skip railings, only look at flights/landings
                            if child.is_a('IfcRailing'):
                                continue

                            # Get geometry from child
                            child_id = child.GlobalId
                            child_meta = element_meta.get(child_id)
                            if child_meta and child_meta.get("AABB_mm"):
                                child_aabbs.append(child_meta.get("AABB_mm"))

                # If we found child geometries, combine them to get full stair extent
                if child_aabbs:
                    # Calculate combined bounding box
                    all_mins = [aabb[0] for aabb in child_aabbs]
                    all_maxs = [aabb[1] for aabb in child_aabbs]

                    combined_min = [
                        min(pt[0] for pt in all_mins),
                        min(pt[1] for pt in all_mins),
                        min(pt[2] for pt in all_mins)
                    ]
                    combined_max = [
                        max(pt[0] for pt in all_maxs),
                        max(pt[1] for pt in all_maxs),
                        max(pt[2] for pt in all_maxs)
                    ]

                    combined_aabb = (combined_min, combined_max)

                    # Create pseudo-metadata with combined AABB
                    combined_meta = {
                        "AABB_mm": combined_aabb,
                        "GlobalId": st_id,
                        "Name": st_name
                    }

                    st_geom = get_stair_full_geometry(st_entity, combined_meta, unit_factor)
                    if st_geom:
                        logging.info(f"    - Combined geometry from {len(child_aabbs)} children (full stair extent)")

        # SAFETY-FIRST APPROACH: If we can't verify geometry but know there's no guardrail protection,
        # flag as hazard (conservative approach - better safe than sorry)
        if not st_geom:
             logging.warning(f"  ⚠ STAIR {st_name} - Could not extract geometry from stair or its children")
             logging.warning(f"     Conservative approach: Marking as HAZARD since no guardrail protection was found")

             # Create a hazard with unknown/estimated height
             estimated_height = 3000  # Conservative estimate for typical stair height (3m)
             severity = "High"  # High severity due to uncertainty

             # Try to get at least a location from children if possible
             location = None
             if hasattr(st_entity, 'IsDecomposedBy'):
                 for rel in st_entity.IsDecomposedBy:
                     if hasattr(rel, 'RelatedObjects'):
                         for child in rel.RelatedObjects:
                             if not child.is_a('IfcRailing'):
                                 child_id = child.GlobalId
                                 child_meta = element_meta.get(child_id)
                                 if child_meta and child_meta.get("AABB_mm"):
                                     aabb = child_meta["AABB_mm"]
                                     center = [(aabb[0][i] + aabb[1][i]) / 2.0 for i in range(3)]
                                     location = {'X': round(center[0], 2), 'Y': round(center[1], 2), 'Z': round(center[2], 2)}
                                     break
                     if location:
                         break

             # Create hazard
             hazards.append(build_hazard_record(
                 "Stairway",
                 estimated_height,
                 {
                     "ElementID": st_id,
                     "Element": st_name,
                     "ElementType": "IfcStair",
                     "Storey": st.get("SpatialContainer"),
                     "StairHeight_mm": estimated_height,
                     "Note": "Geometry unavailable - Conservative safety assessment"
                 },
                 severity,
                 notes=["Stairway lacks guardrail protection (geometry unavailable - flagged for safety)"],
                 location=location
             ))
             logging.info(f"  ✓ STAIR HAZARD (No Geometry): {st_name} | Estimated Height: {estimated_height}mm | Severity: {severity}")
             continue

        # Check protection
        is_protected = False

        for r in railings:
             r_aabb = r.get("AABB_mm")
             r_dims = r.get("Dims_mm")

             protection = check_stair_3d_spatial_protection(st_geom, r_aabb, r_dims)
             if protection['protected']:
                 is_protected = True
                 logging.info(f"    - Spatially protected by railing {r.get('GlobalId')} - {protection['reason']}")
                 break
             else:
                 pass

        if is_protected:
            logging.info(f"  ✓ STAIR {st_name} PROTECTED (3D Spatial Check)")
        elif not is_protected:
            # Create Hazard
            height = st_geom['height']
            severity = "High" if height > 2000 else "Medium"
            location = {'X': round(st_geom['center'][0], 2), 
                        'Y': round(st_geom['center'][1], 2), 
                        'Z': round(st_geom['center'][2], 2)}
            
            hazards.append(build_hazard_record(
                "Stairway",
                height,
                {
                    "ElementID": st_id,
                    "Element": st_name,
                    "ElementType": "IfcStair",
                    "Storey": st.get("SpatialContainer"),
                    "StairHeight_mm": round(height, 2)
                },
                severity,
                notes=["Stairway lacks adequate railing protection"],
                location=location
            ))
            logging.info(f"  ✓ STAIR HAZARD: {st_name} | Height: {height:.1f}mm")
            
    return hazards

# ==========================================
# MAIN DETECTION FUNCTION - FIXED
# ==========================================
def detect_all_hazards(element_meta, by_type, railings, unit_factor, ifc_file=None):
    """FIXED: Comprehensive hazard detection with proper opening detection"""
    hazards = []

    slabs = by_type.get("IfcSlab", [])
    openings = by_type.get("IfcOpeningElement", [])
    doors = by_type.get("IfcDoor", [])
    windows = by_type.get("IfcWindow", [])
    stairs = by_type.get("IfcStair", [])
    columns = by_type.get("IfcColumn", [])
    beams = by_type.get("IfcBeam", [])
    
    logging.info("=" * 80)
    logging.info("STARTING COMPREHENSIVE HAZARD DETECTION")
    logging.info("=" * 80)
    logging.info(f"Unit factor: {unit_factor} (1.0 = already in mm, 1000.0 = meters to mm)")
    logging.info(f"Min opening size: {MIN_OPENING_SIZE}mm")
    logging.info(f"Detection mode: {'AGGRESSIVE (all openings)' if DETECT_ALL_OPENINGS else 'STANDARD'}")
    
    # ==========================================
    # 1. OPENING HAZARDS - CRITICAL FIX
    # ==========================================
    logging.info(f"\n[1/10] Processing {len(openings)} IfcOpeningElements...")
    opening_count = 0
    
    for op in openings:
        op_dims = op.get("Dims_mm")
        op_name = op.get("Name") or op.get("GlobalId")
        op_desc = op.get("Description") or ""
        op_type = op.get("Type")
        op_storey = op.get("SpatialContainer")
        op_aabb = op.get("AABB_mm")
        op_id = op.get("GlobalId")

        if not op_dims:
            logging.debug(f"  Opening {op_name} has no dimensions")
            continue

        # Filter out terrain/site elements that are incorrectly detected as openings
        terrain_keywords = ["toposolid", "terrain", "site", "ground", "grassland", "landscape", "earth"]
        if any(keyword in op_name.lower() for keyword in terrain_keywords):
            logging.debug(f"  Skipping terrain/site element: {op_name}")
            continue

        width = max(op_dims[0], op_dims[1])
        depth = min(op_dims[0], op_dims[1])
        height = op_dims[2]

        # Check minimum size
        max_dim = max(width, height, depth)
        if max_dim < MIN_OPENING_SIZE:
            logging.debug(f"  Opening {op_name} too small ({max_dim:.1f}mm < {MIN_OPENING_SIZE}mm)")
            continue

        # Filter out unreasonably large openings (likely terrain/site elements)
        # Max reasonable opening: 10m x 10m x 10m
        if width > 10000 or depth > 10000 or height > 10000:
            logging.debug(f"  Skipping unreasonably large opening: {op_name} ({width:.0f}x{depth:.0f}x{height:.0f}mm)")
            continue

        # Check if opening is filled with a door or window
        if is_opening_filled(op_id, ifc_file, doors, windows):
            if VERBOSE_DETECTION:
                logging.info(f"  Analyzing: {op_name}")
                logging.info(f"    Filled with door/window - SKIPPING")
            logging.info(f"  Skipping filled opening: {op_name}")
            continue

        # Classify opening
        opening_class = classify_opening_type(op_dims, op_name, op_desc, op_aabb)

        # Check if opening has guardrail protection
        has_protection = has_guardrail_protection(op_aabb, railings)

        if VERBOSE_DETECTION:
            logging.info(f"  Analyzing: {op_name}")
            logging.info(f"    Type: {opening_class}")
            logging.info(f"    Dimensions: W={width:.1f} x D={depth:.1f} x H={height:.1f}mm")
            if has_protection:
                logging.info(f"    Protection: Guardrail detected - SKIPPING")

        # Skip openings with adequate protection
        if has_protection:
            logging.debug(f"  Skipping protected opening: {op_name}")
            continue

        # Check if this is an edge opening (more critical)
        at_edge = is_edge_opening(op_aabb, slabs, edge_threshold=1000)

        # FLOOR OPENINGS
        if opening_class in ["floor", "unknown"]:
            threshold = REGULATIONS["FloorOpening"]["Threshold_mm"]
            check_dim = width  # Check largest horizontal dimension

            if DETECT_ALL_OPENINGS or check_dim >= threshold:
                opening_count += 1
                severity = calculate_severity(check_dim, threshold)

                # Upgrade severity for edge openings (extra dangerous)
                if at_edge and severity != "Critical":
                    severity = "High" if severity == "Medium" else "Critical"

                location = extract_location_from_aabb(op_aabb)
                edge_note = " [EDGE OPENING - REQUIRES GUARDRAIL]" if at_edge else ""
                hazards.append(build_hazard_record(
                    "FloorOpening",
                    check_dim,
                    {
                        "ElementID": op.get("GlobalId"),
                        "Opening": op_name,
                        "OpeningType": op_type,
                        "Storey": op_storey,
                        "Width_mm": round(width, 2),
                        "Depth_mm": round(depth, 2),
                        "Height_mm": round(height, 2),
                        "IsEdgeOpening": at_edge
                    },
                    severity,
                    notes=[f"Floor opening {width:.1f}mm x {depth:.1f}mm (threshold: {threshold}mm){edge_note}"],
                    location=location
                ))
                logging.info(f"  ✓ FLOOR OPENING: {op_name} | {check_dim:.1f}mm | Severity: {severity}{' [EDGE]' if at_edge else ''}")
        
        # WALL OPENINGS
        elif opening_class == "wall":
            threshold = REGULATIONS["WallOpening"]["Threshold_mm"]
            # For wall openings, check both height and width
            check_dim = max(height, width)

            if DETECT_ALL_OPENINGS or check_dim >= threshold:
                # Check if this opening spans multiple floors
                floor_levels = get_multi_floor_levels(op_aabb, typical_floor_height=3000)

                if len(floor_levels) > 1:
                    logging.info(f"  Multi-floor opening detected: {op_name} spans {len(floor_levels)} floors (height: {height:.1f}mm)")

                # Create a separate hazard entry for each floor level
                for i, z_level in enumerate(floor_levels):
                    opening_count += 1
                    severity = calculate_severity(check_dim, threshold)

                    # Create location for this specific floor level
                    base_location = extract_location_from_aabb(op_aabb)
                    location = {
                        "X": base_location["X"],
                        "Y": base_location["Y"],
                        "Z": round(z_level, 2)  # Use the specific floor Z-level
                    }

                    floor_note = f" [Floor {i+1}/{len(floor_levels)}]" if len(floor_levels) > 1 else ""
                    hazards.append(build_hazard_record(
                        "WallOpening",
                        check_dim,
                        {
                            "ElementID": op.get("GlobalId"),
                            "Opening": op_name + floor_note,
                            "OpeningType": op_type,
                            "Storey": op_storey,
                            "Width_mm": round(width, 2),
                            "Height_mm": round(height, 2),
                            "Depth_mm": round(depth, 2),
                            "MultiFloor": len(floor_levels) > 1,
                            "FloorLevel": i + 1,
                            "TotalFloors": len(floor_levels)
                        },
                        severity,
                        notes=[f"Wall opening {width:.1f}mm x {height:.1f}mm (threshold: {threshold}mm){floor_note}"],
                        location=location
                    ))
                    logging.info(f"  ✓ WALL OPENING: {op_name}{floor_note} | {check_dim:.1f}mm | Severity: {severity} | Z: {z_level:.1f}mm")
        
        # ROOF OPENINGS
        elif opening_class == "roof":
            threshold = REGULATIONS["RoofOpening"]["Threshold_mm"]
            check_dim = width

            if DETECT_ALL_OPENINGS or check_dim >= threshold:
                opening_count += 1
                severity = calculate_severity(check_dim, threshold)
                location = extract_location_from_aabb(op_aabb)
                hazards.append(build_hazard_record(
                    "RoofOpening",
                    check_dim,
                    {
                        "ElementID": op.get("GlobalId"),
                        "Opening": op_name,
                        "OpeningType": op_type,
                        "Storey": op_storey,
                        "Width_mm": round(width, 2),
                        "Depth_mm": round(depth, 2)
                    },
                    severity,
                    notes=[f"Roof opening {width:.1f}mm x {depth:.1f}mm (threshold: {threshold}mm)"],
                    location=location
                ))
                logging.info(f"  ✓ ROOF OPENING: {op_name} | {check_dim:.1f}mm | Severity: {severity}")

        # SKYLIGHTS (combined under RoofOpening)
        elif opening_class == "skylight":
            threshold = REGULATIONS["RoofOpening"]["Threshold_mm"]
            check_dim = width

            if DETECT_ALL_OPENINGS or check_dim >= threshold:
                opening_count += 1
                severity = calculate_severity(check_dim, threshold)
                location = extract_location_from_aabb(op_aabb)
                hazards.append(build_hazard_record(
                    "RoofOpening",
                    check_dim,
                    {
                        "ElementID": op.get("GlobalId"),
                        "Opening": op_name,
                        "OpeningType": op_type,
                        "Storey": op_storey,
                        "Width_mm": round(width, 2),
                        "Depth_mm": round(depth, 2)
                    },
                    severity,
                    notes=[f"Skylight opening {width:.1f}mm x {depth:.1f}mm (threshold: {threshold}mm)"],
                    location=location
                ))
                logging.info(f"  ✓ ROOF/SKYLIGHT: {op_name} | {check_dim:.1f}mm | Severity: {severity}")
    
    logging.info(f"  -> Total opening hazards found: {opening_count}")
    
    # ==========================================
    # 2. DOORS - SKIPPED (Doors are covered openings, not hazards)
    # ==========================================
    # Doors and windows fill openings and act as barriers, so they're not fall hazards
    # Only the underlying empty openings (IfcOpeningElement without fillings) are hazards
    logging.info(f"\n[2/10] Skipping {len(doors)} doors (covered openings - not hazards)...")
    door_count = 0
    logging.info(f"  → Doors are considered safe (barriers/fillings)")
    
    # ==========================================
    # 3. WINDOWS - SKIPPED (Windows are covered openings, not hazards)
    # ==========================================
    # Windows fill openings and act as barriers, so they're not fall hazards
    # Only the underlying empty openings (IfcOpeningElement without fillings) are hazards
    logging.info(f"\n[3/10] Skipping {len(windows)} windows (covered openings - not hazards)...")
    window_count = 0
    logging.info(f"  → Windows are considered safe (barriers/fillings)")
    
    # ==========================================
    # 4. SLABS - UNPROTECTED EDGES (FALL FROM HEIGHT)
    # ==========================================
    logging.info(f"\n[4/10] Processing {len(slabs)} slabs for unprotected edges...")
    slab_count = 0
    edge_marker_count = 0

    # Build set of stair-associated element IDs to skip
    stair_element_ids = set()
    if ifc_file:
        try:
            for stair in ifc_file.by_type("IfcStair"):
                # Add the stair itself
                stair_element_ids.add(stair.GlobalId)

                # Add all decomposed elements (landings, flights, etc.)
                if hasattr(stair, 'IsDecomposedBy'):
                    for rel in stair.IsDecomposedBy:
                        if hasattr(rel, 'RelatedObjects'):
                            for obj in rel.RelatedObjects:
                                if hasattr(obj, 'GlobalId'):
                                    stair_element_ids.add(obj.GlobalId)
        except:
            pass  # If IFC file not available, continue without filtering

    logging.debug(f"  Found {len(stair_element_ids)} stair-associated elements to skip")

    for sl in slabs:
        sl_aabb = sl.get("AABB_mm")
        sl_name = sl.get("Name") or sl.get("GlobalId")
        sl_storey = sl.get("SpatialContainer")
        sl_id = sl.get("GlobalId")
        sl_vertices = sl.get("Vertices_mm")  # Get actual geometry if available
        sl_type = sl.get("Type", "")

        if sl_aabb is None:
            continue

        # Filter 0: Skip slabs that are part of stairs (landings, flights)
        if sl_id in stair_element_ids:
            logging.debug(f"  Skipping stair component slab: {sl_name}")
            continue

        # Filter 1: Skip vertical slabs (likely walls misclassified as slabs)
        sl_dims = sl.get("Dims_mm")
        if sl_dims:
            width, depth, height = sl_dims
            # If height is much larger than width/depth, it's likely a vertical wall
            horizontal_dim = max(width, depth)
            min_horizontal_dim = min(width, depth)

            # Multiple checks for vertical orientation:
            # 1. Height > 2x the max horizontal dimension
            # 2. OR height > 1.5x AND min horizontal < 500mm (thin vertical element)
            is_vertical = (
                height > horizontal_dim * 2 or
                (height > horizontal_dim * 1.5 and min_horizontal_dim < 500) or
                (height > 2000 and min_horizontal_dim < 300)  # Tall and thin
            )

            if is_vertical:
                logging.debug(f"  Skipping vertical slab (wall): {sl_name} (H={height:.0f}mm vs W={width:.0f} D={depth:.0f}mm)")
                continue

        # Filter 2: Skip stair-related slabs (landings, runs)
        # Check if slab name/type indicates it's part of a stair
        stair_keywords = ["stair", "landing", "run", "flight", "tread", "riser"]
        if any(keyword in sl_name.lower() for keyword in stair_keywords):
            logging.debug(f"  Skipping stair-related slab: {sl_name}")
            continue
        if sl_type and any(keyword in sl_type.lower() for keyword in stair_keywords):
            logging.debug(f"  Skipping stair-related slab: {sl_name} (Type: {sl_type})")
            continue

        sl_top_z = float(sl_aabb[1][2])
        edge_threshold = REGULATIONS["UnprotectedSidesAndEdges"]["Threshold_mm"]

        # Detect unprotected edges using geometry-aware edge detection
        # Now uses actual slab perimeter for irregular shapes
        # Checks for BOTH railing AND wall protection
        walls_list = by_type.get("IfcWall", [])
        unprotected_edge_markers = detect_unprotected_slab_edges(
            sl_aabb,
            sl_name,
            railings,
            walls_list,
            min_height=edge_threshold,
            marker_spacing=2000,  # Place markers every 2 meters along unprotected edges
            slab_vertices=sl_vertices  # Pass actual geometry for irregular slabs
        )

        # Create hazards for each unprotected edge marker
        if unprotected_edge_markers:
            logging.info(f"  {sl_name}: Found {len(unprotected_edge_markers)} unprotected edge markers")

            for marker in unprotected_edge_markers:
                slab_count += 1
                edge_marker_count += 1
                severity = calculate_severity(sl_top_z, edge_threshold)

                edge_label = f"{marker['Edge']} Edge"
                if marker['TotalMarkers'] > 1:
                    edge_label += f" ({marker['EdgeIndex']}/{marker['TotalMarkers']})"

                hazards.append(build_hazard_record(
                    "UnprotectedSidesAndEdges",
                    sl_top_z,
                    {
                        "ElementID": sl_id,
                        "Element": f"{sl_name} - {edge_label}",
                        "ElementType": "IfcSlab",
                        "Storey": sl_storey,
                        "Elevation_mm": round(sl_top_z, 2),
                        "Edge": marker["Edge"],
                        "EdgeIndex": marker["EdgeIndex"],
                        "TotalEdgeMarkers": marker["TotalMarkers"]
                    },
                    severity,
                    notes=[f"Unprotected {marker['Edge'].lower()} edge at {sl_top_z:.1f}mm elevation (threshold: {edge_threshold}mm)"],
                    location=marker
                ))

            logging.info(f"  ✓ UNPROTECTED EDGES: {sl_name} at {sl_top_z:.1f}mm | {len(unprotected_edge_markers)} markers | Severity: {severity}")

    logging.info(f"  → Found {slab_count} unprotected edge hazards ({edge_marker_count} edge markers total)")
    
    # 5. COLUMNS - REMOVED (Not in scope per manuscript)
    logging.info(f"\n[5/10] Skipping column-specific checks per manuscript scope...")
    
    # ==========================================
    # 6. RAILINGS - HEIGHT COMPLIANCE
    # ==========================================
    logging.info(f"\n[6/10] Processing {len(railings)} railings...")
    railing_count = 0
    for r in railings:
        r_dims = r.get("Dims_mm")
        r_name = r.get("Name") or r.get("GlobalId")
        r_aabb = r.get("AABB_mm")

        if r_dims and r_dims[2] is not None:
            required_height = REGULATIONS["Stairway"]["Threshold_mm"]
            actual_height = r_dims[2]

            if actual_height < required_height:
                railing_count += 1
                severity = calculate_severity(actual_height, required_height)
                location = extract_location_from_aabb(r_aabb)
                hazards.append(build_hazard_record(
                    "UnprotectedSidesAndEdges",
                    actual_height,
                    {
                        "ElementID": r.get("GlobalId"),
                        "Element": r_name,
                        "ElementType": "IfcRailing",
                        "ActualHeight_mm": round(actual_height, 2),
                        "RequiredHeight_mm": required_height
                    },
                    severity,
                    notes=[f"Railing height {actual_height:.1f}mm below required {required_height}mm"],
                    location=location
                ))
                logging.info(f"  ✓ INSUFFICIENT RAILING: {r_name} | Height: {actual_height:.1f}mm")
    
    logging.info(f"  → Found {railing_count} railing hazards")
    
    # ==========================================
    # 7. STAIRS - SAFETY COMPLIANCE (ENHANCED 3D-SPATIAL DETECTION)
    # ==========================================
    logging.info(f"\n[7/10] Processing {len(stairs)} stairs...")

    if ENHANCED_STAIR_DETECTION:
        # Use enhanced 3D-spatially aware detection
        # Pass the actual config module, not a dict with globals
        stair_hazards = detect_stairway_hazards_enhanced(
            element_meta=element_meta,
            by_type=by_type,
            railings=railings,
            unit_factor=unit_factor,
            ifc_file=ifc_file,
            config=config  # Pass the actual config module
        )

        hazards.extend(stair_hazards)
        stair_count = len(stair_hazards)
    else:
        # Fallback to basic detection
        stair_count = 0
        for st in stairs:
            st_aabb = st.get("AABB_mm")
            st_name = st.get("Name") or st.get("GlobalId")
            st_storey = st.get("SpatialContainer")

            # Check if stair has adequate railing protection
            stair_protected = False
            for r in railings:
                r_aabb = r.get("AABB_mm")
                if r_aabb and st_aabb and overlap_xy(st_aabb, r_aabb):
                    r_dims = r.get("Dims_mm")
                    if r_dims and r_dims[2] >= REGULATIONS["Stairway"]["Threshold_mm"]:
                        stair_protected = True
                        break

            if not stair_protected:
                stair_count += 1
                stair_height = st_aabb[1][2] if st_aabb else 0.0
                severity = "High" if stair_height >= 2000 else "Medium"

                location = extract_location_from_aabb(st_aabb)

                hazards.append(build_hazard_record(
                    "Stairway",
                    stair_height,
                    {
                        "ElementID": st.get("GlobalId"),
                        "Element": st_name,
                        "ElementType": "IfcStair",
                        "Storey": st_storey,
                        "StairHeight_mm": round(stair_height, 2)
                    },
                    severity,
                    notes=[f"Stair lacks adequate railing protection"],
                    location=location
                ))
                logging.info(f"  ✓ STAIR HAZARD: {st_name} | Height: {stair_height:.1f}mm")

    logging.info(f"  → Found {stair_count} stair hazards")
    
    # ==========================================
    # 8-10. Name-based detection for special hazards
    # ==========================================
    logging.info(f"\n[8/10] Scanning for scaffolds...")
    scaffold_count = 0
    
    for gid, meta in element_meta.items():
        nm = (meta.get("Name") or "").lower()
        
        if "scaffold" in nm or "scaff" in nm:
            aabb = meta.get("AABB_mm")
            if aabb:
                top_z = aabb[1][2]
                threshold = REGULATIONS["Scaffold"]["Threshold_mm"]
                
                if top_z >= threshold:
                    scaffold_count += 1
                    severity = calculate_severity(top_z, threshold)
                    location = extract_location_from_aabb(aabb)
                    hazards.append(build_hazard_record(
                        "Scaffold",
                        top_z,
                        {
                            "ElementID": gid,
                            "Element": meta.get("Name") or gid,
                            "ElementType": meta.get("Type"),
                            "Height_mm": round(top_z, 2)
                        },
                        severity,
                        notes=[f"Scaffold at {top_z:.1f}mm height (threshold: {threshold}mm)"],
                        location=location
                    ))
                    logging.info(f"  ✓ SCAFFOLD: {meta.get('Name')} at {top_z:.1f}mm")
    
    logging.info(f"  → Found {scaffold_count} scaffold hazards")
    
    logging.info(f"\n[9/10] Scanning for ladders...")
    ladder_count = 0
    
    for gid, meta in element_meta.items():
        nm = (meta.get("Name") or "").lower()
        
        if "ladder" in nm:
            aabb = meta.get("AABB_mm")
            if aabb:
                top_z = aabb[1][2]
                threshold = REGULATIONS["Ladder"]["Threshold_mm"]
                
                if top_z >= threshold:
                    ladder_count += 1
                    severity = calculate_severity(top_z, threshold)
                    location = extract_location_from_aabb(aabb)
                    hazards.append(build_hazard_record(
                        "Ladder",
                        top_z,
                        {
                            "ElementID": gid,
                            "Element": meta.get("Name") or gid,
                            "ElementType": meta.get("Type"),
                            "Height_mm": round(top_z, 2)
                        },
                        severity,
                        notes=[f"Ladder at {top_z:.1f}mm height (threshold: {threshold}mm)"],
                        location=location
                    ))
                    logging.info(f"  ✓ LADDER: {meta.get('Name')} at {top_z:.1f}mm")
    
    logging.info(f"  → Found {ladder_count} ladder hazards")
    
    logging.info(f"\n[10/10] Scanning for excavations...")
    excavation_count = 0
    
    for gid, meta in element_meta.items():
        nm = (meta.get("Name") or "").lower()
        desc = (meta.get("Description") or "").lower()
        
        if any(kw in nm or kw in desc for kw in ["excavat", "pit", "trench", "ditch"]):
            aabb = meta.get("AABB_mm")
            if aabb:
                depth_z = abs(aabb[0][2])
                threshold = REGULATIONS["Excavation"]["Threshold_mm"]
                
                if depth_z >= threshold:
                    excavation_count += 1
                    severity = calculate_severity(depth_z, threshold)
                    location = extract_location_from_aabb(aabb)
                    hazards.append(build_hazard_record(
                        "Excavation",
                        depth_z,
                        {
                            "ElementID": gid,
                            "Element": meta.get("Name") or gid,
                            "ElementType": meta.get("Type"),
                            "Depth_mm": round(depth_z, 2)
                        },
                        severity,
                        notes=[f"Excavation depth {depth_z:.1f}mm (threshold: {threshold}mm)"],
                        location=location
                    ))
                    logging.info(f"  ✓ EXCAVATION: {meta.get('Name')} at {depth_z:.1f}mm depth")
    
    logging.info(f"  → Found {excavation_count} excavation hazards")
    
    # Add fall level classification
    for h in hazards:
        detected = h.get("DetectedValue_mm")
        if isinstance(detected, (int, float)) and detected > 0:
            cat = h.get("Category", "").lower()
            if "fall" in cat or "elevated" in cat or "edge" in cat:
                h["FallLevel"] = fall_level_classification(float(detected))
    
    logging.info("\n" + "=" * 80)
    logging.info(f"DETECTION COMPLETE: {len(hazards)} total hazards")
    logging.info("=" * 80)
    
    cat_counts = Counter([h.get("Category", "Unknown") for h in hazards])
    for cat, count in sorted(cat_counts.items()):
        logging.info(f"  • {cat}: {count}")
    
    return hazards

# ==========================================
# MAIN PIPELINE
# ==========================================
def run_pipeline():
    """Main pipeline execution"""
    start_time = time.time()
    
    # Find IFC file
   
    if config.IFC_FILENAME:
        ifc_path = project_root_path / config.IFC_FILENAME     
           
    else: # Try to find IFC in input_data/ if not specified
        input_dir = project_root_path / "input_data"  # Default input directory
        ifc_files = list(input_dir.glob("*.ifc"))
        
        if not ifc_files:
                print("ERROR: No IFC file found in input_data/")
                print("Please specify IFC file with --ifc option or set SOURCE_IFC_PATH in config.py")
                return 1

        # pick latest IFC instead of hardcoded name
        ifc_path = max(ifc_files, key=os.path.getmtime)
        
    print(f"[OK] Using IFC file: {ifc_path}")

    
    logging.info("=" * 80)
    logging.info("IFC HAZARD DETECTION PIPELINE")
    logging.info("=" * 80)
    if config.IFC_FILENAME:
        logging.info(f"IFC File: {IFC_FILENAME}")
    else:
        logging.info(f"Automatically detected IFC file: {ifc_path.name} from input_data")

    logging.info(f"Output: {OUTPUT_FOLDER}")
    
    # Create output folder
    run_folder = create_output_folder()
    logging.info(f"Run folder: {run_folder}")
    
    # Open IFC
    ifc = ifcopenshell.open(ifc_path)
    logging.info(f"IFC Schema: {ifc.schema}")
    
    # Detect units - FIXED
    unit_factor = detect_unit_factor(ifc)
    logging.info(f"Unit factor: {unit_factor} (conversion to mm)")
    
    # Setup geometry
    geom_settings = setup_geom_context()
    
    # Get relevant elements
    RELEVANT_TYPES = [
        "IfcSlab", "IfcOpeningElement", "IfcRailing", "IfcStair",
        "IfcRamp", "IfcWall", "IfcDoor", "IfcWindow", 
        "IfcBeam", "IfcColumn", "IfcRoof", "IfcCovering"
    ]
    
    element_meta = {}
    all_elements = []
    
    for etype in RELEVANT_TYPES:
        elements = ifc.by_type(etype)
        all_elements.extend(elements)
        logging.info(f"Found {len(elements)} {etype}")
    
    # Process geometry with correct unit conversion
    logging.info(f"\nProcessing {len(all_elements)} elements...")
    successful = 0
    failed = 0
    
    for ent in tqdm(all_elements, desc="Geometry"):
        gid = ent.GlobalId
        e_type = ent.is_a()

        verts = get_mesh_vertices(ent, geom_settings)
        aabb = aabb_from_vertices(verts)

        if aabb is not None:
            # Apply unit conversion here
            mins = [v * unit_factor for v in aabb[0]]
            maxs = [v * unit_factor for v in aabb[1]]
            aabb_mm = (mins, maxs)
            dims = aabb_dims(aabb_mm)

            # Store vertices for slabs (needed for accurate edge detection)
            verts_mm = None
            if e_type == "IfcSlab" and verts is not None:
                verts_mm = verts * unit_factor  # Convert to mm

            successful += 1
        else:
            aabb_mm = None
            dims = None
            verts_mm = None
            failed += 1

        element_meta[gid] = {
            "GlobalId": gid,
            "Type": e_type,
            "Name": getattr(ent, "Name", None),
            "Description": getattr(ent, "Description", None),
            "AABB_mm": aabb_mm,
            "Dims_mm": dims,
            "Vertices_mm": verts_mm,  # Store actual vertices for slabs
            "SpatialContainer": None
        }
    
    logging.info(f"Geometry: {successful} success, {failed} failed ({100*successful/len(all_elements):.1f}%)")
    
    # Organize by type
    by_type = defaultdict(list)
    for gid, meta in element_meta.items():
        by_type[meta["Type"]].append(meta)
    
    railings = by_type.get("IfcRailing", [])

    # RUN DETECTION
    hazards = detect_all_hazards(element_meta, by_type, railings, unit_factor, ifc_file=ifc)
    
    # Save results
    results = {
        "run_info": {
            "timestamp": timestamp_str(),
            "ifc_file": IFC_FILENAME,
            "unit_factor": unit_factor,
            "processing_time_s": round(time.time() - start_time, 2)
        },
        "statistics": {
            "total_elements": len(element_meta),
            "geometry_success_rate": round(successful / len(all_elements), 3),
            "total_hazards": len(hazards)
        },
        "hazards_by_category": dict(Counter([h.get("Category", "Unknown") for h in hazards]))
    }
    
    # Write JSON files
    with open(os.path.join(run_folder, "hazards_detected.json"), 'w') as f:
        json.dump(hazards, f, indent=2)
    
    with open(os.path.join(run_folder, "run_summary.json"), 'w') as f:
        json.dump(results, f, indent=2)
    
    # Write CSV
    if pd is not None:
        df = pd.DataFrame(hazards)
        df.to_csv(os.path.join(run_folder, "hazards.csv"), index=False)
    
    # Generate graphs
    logging.info("\nGenerating visualizations...")
    
    # 1. Hazards by category
    plt.figure(figsize=(10, 6))
    cat_counts = Counter([h.get("Category", "Unknown") for h in hazards])
    if cat_counts:
        plt.bar(cat_counts.keys(), cat_counts.values(), color=['#e74c3c', '#f39c12', '#3498db', '#2ecc71'])
        plt.title("Hazards by Category", fontsize=16, fontweight='bold')
        plt.ylabel("Count", fontsize=12)
        plt.xticks(rotation=15, ha='right')
        plt.tight_layout()
        plt.savefig(os.path.join(run_folder, "01_hazards_by_category.png"), dpi=150)
        plt.close()
    
    # 2. Hazards by severity
    plt.figure(figsize=(8, 6))
    sev_counts = Counter([h.get("Severity", "Unknown") for h in hazards])
    if sev_counts:
        colors = {'Low': '#2ecc71', 'Medium': '#f39c12', 'High': '#e74c3c', 'Critical': '#c0392b'}
        plt.bar(sev_counts.keys(), sev_counts.values(), 
                color=[colors.get(k, '#95a5a6') for k in sev_counts.keys()])
        plt.title("Hazards by Severity", fontsize=16, fontweight='bold')
        plt.ylabel("Count", fontsize=12)
        plt.tight_layout()
        plt.savefig(os.path.join(run_folder, "02_hazards_by_severity.png"), dpi=150)
        plt.close()
    
    # 3. Specific hazard types
    plt.figure(figsize=(12, 8))
    spec_counts = Counter([h.get("SpecificHazard", "Unknown") for h in hazards])
    if spec_counts:
        if spec_counts:
            sorted_items = sorted(spec_counts.items(), key=lambda x: x[1])
            
            labels = [item[0] for item in sorted_items]
            values = [item[1] for item in sorted_items]
            # --------------------------------

            plt.barh(labels, values, color='#3498db')
            
            # Add labels to the end of bars
            for i, v in enumerate(values):
                plt.text(v + 0.1, i, str(v), va='center', fontweight='bold')
            
        
        # plt.barh(list(spec_counts.keys()), list(spec_counts.values()), color='#3498db')
        plt.title("Specific Hazard Types", fontsize=16, fontweight='bold')
        plt.xlabel("Count", fontsize=12)
        plt.tight_layout()
        plt.savefig(os.path.join(run_folder, "03_specific_hazards.png"), dpi=150)
        plt.close()
    
    # 4. Summary dashboard
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Hazard Detection Summary - {IFC_FILENAME}", fontsize=16, fontweight='bold')
    
    # Category pie
    if cat_counts:
        axes[0, 0].pie(cat_counts.values(), labels=cat_counts.keys(), autopct='%1.1f%%', startangle=90)
        axes[0, 0].set_title("Categories")
    
    # Severity bar
    if sev_counts:
        colors_map = {'Low': '#2ecc71', 'Medium': '#f39c12', 'High': '#e74c3c', 'Critical': '#c0392b'}
        axes[0, 1].bar(sev_counts.keys(), sev_counts.values(),
                       color=[colors_map.get(k, '#95a5a6') for k in sev_counts.keys()])
        axes[0, 1].set_title("Severity Distribution")
        axes[0, 1].set_ylabel("Count")
    
    # Stats text
    stats_text = f"""
PROCESSING STATISTICS

Total Elements: {len(element_meta)}
Geometry Success: {successful}/{len(all_elements)} ({100*successful/len(all_elements):.1f}%)

Total Hazards: {len(hazards)}

By Category:
  - Elevated work: {results['hazards_by_category'].get('Elevated work hazards', 0)}
  • Opening hazards: {results['hazards_by_category'].get('Opening hazards', 0)}
  • Access hazards: {results['hazards_by_category'].get('Access hazards', 0)}
  • Excavation: {results['hazards_by_category'].get('Excavation hazards', 0)}

Processing Time: {results['run_info']['processing_time_s']}s
Unit Factor: {unit_factor} (to mm)
"""
    axes[1, 0].text(0.1, 0.5, stats_text, fontsize=10, family='monospace', 
                    verticalalignment='center', transform=axes[1, 0].transAxes)
    axes[1, 0].axis('off')
    
    # Top hazards
    if spec_counts:
        top_5 = spec_counts.most_common(5)
        axes[1, 1].barh([h[0] for h in top_5], [h[1] for h in top_5], color='#e74c3c')
        axes[1, 1].set_title("Top 5 Hazard Types")
        axes[1, 1].set_xlabel("Count")
    
    plt.tight_layout()
    plt.savefig(os.path.join(run_folder, "00_summary_dashboard.png"), dpi=150)
    plt.close()
    
    # Final summary
    logging.info("\n" + "=" * 80)
    logging.info("PIPELINE COMPLETE!")
    logging.info("=" * 80)
    logging.info(f"Processing time: {results['run_info']['processing_time_s']}s")
    logging.info(f"Unit factor applied: {unit_factor}")
    logging.info(f"Total hazards: {len(hazards)}")
    logging.info(f"Output folder: {run_folder}")
    logging.info("")
    logging.info("Files generated:")
    logging.info(f"  - hazards_detected.json - Complete hazard data")
    logging.info(f"  • hazards.csv - CSV format")
    logging.info(f"  • run_summary.json - Statistics")
    logging.info(f"  • 4 PNG visualizations")
    logging.info("=" * 80)
    
    return results

# ==========================================
# MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("IFC HAZARD DETECTION PIPELINE - FIXED VERSION")
    print("=" * 80)
    print(f"Configuration: config.py")
    print(f"IFC File: {IFC_FILENAME}")
    print(f"Detection Mode: {'AGGRESSIVE' if DETECT_ALL_OPENINGS else 'STANDARD'}")
    print(f"Unit Conversion: {FORCE_UNIT_FACTOR if 'FORCE_UNIT_FACTOR' in globals() and FORCE_UNIT_FACTOR else 'AUTO-DETECT'}")
    print("=" * 80 + "\n")
    
    try:
        results = run_pipeline()
        if results:
            print("\n[OK] SUCCESS! Check the output folder for results.")
            print(f"  Total hazards detected: {results['statistics']['total_hazards']}")
            print(f"  Output folder: {results['run_info']['timestamp']}\n")
            sys.exit(0)
        else:
            print("\n[FAIL] FAILED! Check the log messages above.\n")
            sys.exit(1)
    except Exception as e:
        logging.exception("Pipeline failed with error:")
        print(f"\n[FAIL] ERROR: {e}\n")
        sys.exit(1)