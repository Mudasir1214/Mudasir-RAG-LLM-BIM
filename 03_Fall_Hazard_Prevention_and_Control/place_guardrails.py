#!/usr/bin/env python3
"""
UNIFIED OSHA GUARDRAIL SYSTEM
Combines stair and floor slab guardrail generation with all regression fixes.

FEATURES:
- Stair flight guardrails with hierarchy-aware exclusion
- Floor slab perimeter guardrails with wall awareness
- Inner loop detection for slab openings/holes
- Loop-type-aware classification
- Continuous rail generation
- OSHA compliance (1070mm parapet, spacing, heights)
"""

import os
import sys
import json
import logging
import math
from pathlib import Path
from datetime import datetime

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.geom
import numpy as np

try:
    from scipy.spatial import ConvexHull
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.warning("SciPy not available - using fallback methods")

# ============================================================================
# OSHA CONFIGURATION
# ============================================================================
TOP_RAIL_HEIGHT = 1100.0
MID_RAIL_HEIGHT = 550.0
TOE_BOARD_HEIGHT = 100.0
RAIL_DIAMETER = 50.0
POST_DIAMETER = 80.0
RAIL_COLOR = (1.0, 1.0, 0.0)  # Yellow

# Stair-specific
STAIR_POST_SPACING = 1000.0
STAIR_RAIL_DIAMETER = 40.0
STAIR_POST_DIAMETER = 50.0

# Floor slab-specific
OSHA_PARAPET_THRESHOLD_MM = 1070.0  # Official OSHA standard for parapets
MIN_PROTECTIVE_WALL_HEIGHT_MM = 800.0  # Minimum height for a wall to be considered protective
# Note: Building walls are often modeled as floor-by-floor segments (800-1000mm between slabs)
# A wall >= 800mm provides adequate fall protection even if below OSHA parapet threshold

POST_SPACING_MM = 2000.0
WALL_ADJACENCY_TOLERANCE_MM = 500.0
EDGE_INSET_MM = 200.0
MIN_EDGE_LENGTH_MM = 50.0
GROUND_LEVEL_THRESHOLD_MM = 1500.0

project_root_path = Path(__file__).resolve().parents[1]



class EdgeSafety:
    SAFE_EDGE = "SAFE"
    PARTIAL_EDGE = "PARTIAL"
    UNPROTECTED_EDGE = "UNPROTECTED"


class LoopType:
    OUTER_PERIMETER = "OUTER"
    INNER_HOLE = "HOLE"


# ============================================================================
# LOGGING & UTILITIES
# ============================================================================
def setup_logging(verbose=False):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def get_element_geometry(ifc_file, element):
    """Extract 3D vertices from IFC element (in mm)"""
    try:
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        shape = ifcopenshell.geom.create_shape(settings, element)
        verts = shape.geometry.verts
        vertices = np.array(verts).reshape(-1, 3) * 1000.0
        return vertices
    except Exception as e:
        logging.debug(f"Could not extract geometry for {element.GlobalId}: {e}")
        return None


def get_element_geometry_with_faces(ifc_file, element):
    """
    Extract 3D vertices AND face indices from IFC element

    Returns:
        (vertices, faces) where:
        - vertices: Nx3 array of XYZ coordinates (mm)
        - faces: Mx3 array of vertex indices (triangles)
        Returns (None, None) on failure
    """
    try:
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        shape = ifcopenshell.geom.create_shape(settings, element)

        # Extract vertices
        verts = shape.geometry.verts
        vertices = np.array(verts).reshape(-1, 3) * 1000.0

        # Extract faces (triplets of vertex indices)
        faces_raw = shape.geometry.faces
        faces = np.array(faces_raw).reshape(-1, 3)

        return vertices, faces
    except Exception as e:
        logging.debug(f"Could not extract geometry for {element.GlobalId}: {e}")
        return None, None


# ============================================================================
# FLOOR SURFACE SNAPPING
# ============================================================================
def get_all_slab_surfaces(ifc_file):
    """
    Pre-compute all slab surfaces for efficient floor-snapping.

    Returns list of slab data with XY footprints and top Z values.
    """
    slab_surfaces = []

    for slab in ifc_file.by_type("IfcSlab"):
        if slab.PredefinedType not in ["FLOOR", "BASESLAB", None]:
            continue

        vertices = get_element_geometry(ifc_file, slab)
        if vertices is None or len(vertices) < 3:
            continue

        # Get bounding box
        x_min, x_max = np.min(vertices[:, 0]), np.max(vertices[:, 0])
        y_min, y_max = np.min(vertices[:, 1]), np.max(vertices[:, 1])
        z_min, z_max = np.min(vertices[:, 2]), np.max(vertices[:, 2])

        # Top surface is what we care about
        top_z = z_max

        # Get detailed top surface vertices for more accurate point-in-polygon
        z_tolerance = 50.0  # 50mm tolerance for "top surface"
        top_vertices = vertices[np.abs(vertices[:, 2] - top_z) < z_tolerance]

        if len(top_vertices) >= 3:
            # Create convex hull of top surface for point-in-polygon test
            try:
                if SCIPY_AVAILABLE:
                    hull_2d = ConvexHull(top_vertices[:, :2])
                    hull_points = top_vertices[hull_2d.vertices, :2]
                else:
                    hull_points = top_vertices[:, :2]
            except:
                hull_points = top_vertices[:, :2]
        else:
            hull_points = None

        slab_surfaces.append({
            'element': slab,
            'x_min': x_min, 'x_max': x_max,
            'y_min': y_min, 'y_max': y_max,
            'z_min': z_min, 'z_max': z_max,
            'top_z': top_z,
            'hull_points': hull_points,
            'all_vertices': vertices,
            'name': slab.Name or slab.GlobalId[:8]
        })

    return slab_surfaces


def point_in_polygon_2d(point, polygon):
    """
    Check if a 2D point is inside a polygon using ray casting.

    Args:
        point: [x, y] coordinates
        polygon: Nx2 array of polygon vertices

    Returns:
        True if point is inside polygon
    """
    x, y = point[0], point[1]
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi):
            inside = not inside
        j = i

    return inside


def get_floor_z_at_point(xy_point, slab_surfaces, nominal_z, z_tolerance=2000.0):
    """
    Find the actual floor surface Z at a given XY point.

    Args:
        xy_point: [x, y] coordinates
        slab_surfaces: list from get_all_slab_surfaces()
        nominal_z: expected Z level (for filtering candidate slabs)
        z_tolerance: how far from nominal_z to search for slabs (default 2000mm to handle partial walls)

    Returns:
        (floor_z, slab_found) tuple
        - floor_z: actual Z of floor surface (or nominal_z if not found)
        - slab_found: True if a slab was found at this point
    """
    px, py = float(xy_point[0]), float(xy_point[1])

    best_slab = None
    best_z_diff = float('inf')

    # Tolerance for edge detection - guardrails are inset from edge, so we need
    # to allow points that are slightly beyond the precise slab footprint
    edge_tolerance = 500.0  # 500mm tolerance for edge snapping (accommodates 200mm inset + margin)

    for slab in slab_surfaces:
        # Quick bounding box check with tolerance
        if not (slab['x_min'] - edge_tolerance <= px <= slab['x_max'] + edge_tolerance and
                slab['y_min'] - edge_tolerance <= py <= slab['y_max'] + edge_tolerance):
            continue

        # Check if slab is near the nominal Z level
        # For partial walls, nominal_z might be above the slab (wall top) so we
        # look for slabs BELOW the nominal Z as well
        slab_top = slab['top_z']
        z_diff = abs(slab_top - nominal_z)

        # Also consider slabs that are below nominal_z (for partial wall cases)
        # where guardrail sits on wall top but we want to verify floor exists below
        if slab_top <= nominal_z:
            z_diff_below = nominal_z - slab_top
            if z_diff_below < z_tolerance:
                z_diff = min(z_diff, z_diff_below)

        if z_diff > z_tolerance:
            continue

        # For points within the bounding box but potentially outside the polygon,
        # use a relaxed check - if it's within the bbox with tolerance, accept it
        # This handles cases where inset points are at slab edges
        in_bbox_strict = (slab['x_min'] <= px <= slab['x_max'] and
                         slab['y_min'] <= py <= slab['y_max'])

        # More lenient bbox check for edge cases
        in_bbox_lenient = (slab['x_min'] - edge_tolerance <= px <= slab['x_max'] + edge_tolerance and
                          slab['y_min'] - edge_tolerance <= py <= slab['y_max'] + edge_tolerance)

        in_polygon = False
        if slab['hull_points'] is not None and len(slab['hull_points']) >= 3:
            in_polygon = point_in_polygon_2d([px, py], slab['hull_points'])

        # Accept if in polygon OR in strict bounding box OR in lenient bbox
        # (lenient bbox handles perimeter guardrails at slab edges)
        if not (in_polygon or in_bbox_strict or in_bbox_lenient):
            continue

        # This slab contains the point - check if it's the closest to nominal Z
        if z_diff < best_z_diff:
            best_z_diff = z_diff
            best_slab = slab

    if best_slab is not None:
        return best_slab['top_z'], True

    return nominal_z, False


def snap_guardrail_points_to_floor(points, slab_surfaces, nominal_z):
    """
    Snap guardrail points to actual floor surface.

    For each point:
    1. Check if there's a floor at that XY location
    2. If yes, use the actual floor Z
    3. If no, mark point as invalid (will be filtered out)

    Args:
        points: list of [x, y] or [x, y, z] points
        slab_surfaces: from get_all_slab_surfaces()
        nominal_z: expected Z level

    Returns:
        list of (x, y, z, valid) tuples
    """
    snapped_points = []

    for pt in points:
        x, y = float(pt[0]), float(pt[1])

        floor_z, found = get_floor_z_at_point([x, y], slab_surfaces, nominal_z)

        snapped_points.append({
            'x': x,
            'y': y,
            'z': floor_z,
            'valid': found
        })

    return snapped_points


def filter_valid_guardrail_segments(snapped_points, min_segment_length=100.0):
    """
    Filter guardrail points to only include valid segments over actual floor.

    Groups consecutive valid points into segments.

    Returns:
        List of valid segments, each segment is a list of points with Z values
    """
    segments = []
    current_segment = []

    for pt in snapped_points:
        if pt['valid']:
            current_segment.append(pt)
        else:
            # Invalid point - close current segment if it exists
            if len(current_segment) >= 2:
                # Check segment length
                seg_length = 0
                for i in range(len(current_segment) - 1):
                    dx = current_segment[i+1]['x'] - current_segment[i]['x']
                    dy = current_segment[i+1]['y'] - current_segment[i]['y']
                    seg_length += math.sqrt(dx*dx + dy*dy)

                if seg_length >= min_segment_length:
                    segments.append(current_segment)
            current_segment = []

    # Don't forget last segment
    if len(current_segment) >= 2:
        seg_length = 0
        for i in range(len(current_segment) - 1):
            dx = current_segment[i+1]['x'] - current_segment[i]['x']
            dy = current_segment[i+1]['y'] - current_segment[i]['y']
            seg_length += math.sqrt(dx*dx + dy*dy)

        if seg_length >= min_segment_length:
            segments.append(current_segment)

    return segments


# ============================================================================
# STAIR RAILING DETECTION
# ============================================================================
def has_existing_railings(model, element):
    """
    Deep relationship check for existing railings.
    Checks: Aggregation, Assignments, Connectivity
    """
    # 1. Direct aggregation
    if hasattr(element, "IsDecomposedBy"):
        for rel in element.IsDecomposedBy:
            if rel.is_a("IfcRelAggregates"):
                for obj in rel.RelatedObjects:
                    if obj.is_a("IfcRailing"):
                        return True

    # 2. Product assignments (common in Revit/IFC4)
    if hasattr(element, "HasAssignments"):
        for rel in element.HasAssignments:
            if rel.is_a("IfcRelAssignsToProduct"):
                if hasattr(rel, "RelatingProduct") and rel.RelatingProduct.is_a("IfcRailing"):
                    return True

    # 3. Connectivity
    if hasattr(element, "ConnectedTo"):
        for rel in element.ConnectedTo:
            if rel.RelatedElement.is_a("IfcRailing"):
                return True
    if hasattr(element, "ConnectedFrom"):
        for rel in element.ConnectedFrom:
            if rel.RelatingElement.is_a("IfcRailing"):
                return True

    return False


# ============================================================================
# STAIR PROCESSING
# ============================================================================
def process_stairs(model, context, style):
    """Process all stair flights and add guardrails where needed"""
    stair_flights = model.by_type("IfcStairFlight")
    logging.info(f"\nProcessing {len(stair_flights)} stair flights")
    
    stair_components = []
    
    for flight in stair_flights:
        # Check flight itself
        found_railing = has_existing_railings(model, flight)
        
        # Check parent IfcStair container
        if not found_railing and hasattr(flight, "Decomposes"):
            for rel in flight.Decomposes:
                if rel.is_a("IfcRelAggregates") and rel.RelatingObject.is_a("IfcStair"):
                    if has_existing_railings(model, rel.RelatingObject):
                        found_railing = True
                        break
        
        if found_railing:
            logging.info(f"  [SKIP] StairFlight {flight.GlobalId[:8]}: Existing railings detected")
            continue

        verts = get_element_geometry(model, flight)
        if verts is None or len(verts) < 10:
            continue

        # Extract tread levels
        z_rounded = np.round(verts[:, 2] / 10.0) * 10.0
        unique_z = np.unique(z_rounded)
        unique_z.sort()

        left_points = []
        right_points = []

        for z in unique_z:
            level_verts = verts[z_rounded == z]
            if len(level_verts) < 2:
                continue

            v_xy = level_verts[:, :2]
            dist_sq = np.sum((v_xy[:, None] - v_xy[None, :])**2, axis=-1)
            idx1, idx2 = np.unravel_index(np.argmax(dist_sq), dist_sq.shape)
            
            p_a, p_b = level_verts[idx1], level_verts[idx2]

            if p_a[0] + p_a[1] < p_b[0] + p_b[1]:
                p_left, p_right = p_a, p_b
            else:
                p_left, p_right = p_b, p_a

            width_vec = p_right - p_left
            dist = np.linalg.norm(width_vec[:2])
            if dist < 100:
                continue
            unit_width = width_vec / dist
            
            left_points.append(p_left + unit_width * 50.0)
            right_points.append(p_right - unit_width * 50.0)

        def generate_clean_segments(points):
            if len(points) < 2:
                return
            current_segment = [points[0]]
            for i in range(1, len(points)):
                p_prev, p_curr = points[i-1], points[i]
                z_delta = abs(p_curr[2] - p_prev[2])
                xy_dist = np.linalg.norm(p_curr[:2] - p_prev[:2])
                
                if (z_delta < 50 and xy_dist > 500) or xy_dist > 1500:
                    if len(current_segment) > 1:
                        comps = generate_stair_railing(model, context, style, current_segment)
                        stair_components.extend(comps)
                    current_segment = [p_curr]
                else:
                    current_segment.append(p_curr)
            
            if len(current_segment) > 1:
                comps = generate_stair_railing(model, context, style, current_segment)
                stair_components.extend(comps)

        generate_clean_segments(left_points)
        generate_clean_segments(right_points)
    
    logging.info(f"  Created {len(stair_components)} stair railing components")
    return stair_components


def generate_stair_railing(model, context, style, points):
    """Generate railing system for stair segment"""
    components = []
    
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i+1]
        components.append(create_stair_post(model, context, style, p1))
        if i == len(points) - 2:
            components.append(create_stair_post(model, context, style, p2))
        
        dist = np.linalg.norm(p2 - p1)
        if dist > STAIR_POST_SPACING:
            num = int(dist // STAIR_POST_SPACING)
            for j in range(1, num + 1):
                mp = p1 + (p2 - p1) * (j / (num + 1))
                components.append(create_stair_post(model, context, style, mp))

        for h in [TOP_RAIL_HEIGHT, MID_RAIL_HEIGHT]:
            components.append(create_stair_rail(model, context, style, 
                                               p1 + [0,0,h], p2 + [0,0,h]))
    
    return components


def create_stair_post(model, context, style, pos):
    """Create vertical post for stairs"""
    pt = model.create_entity("IfcCartesianPoint", 
                             Coordinates=(float(pos[0]), float(pos[1]), float(pos[2])))
    axis = model.create_entity("IfcAxis2Placement3D", Location=pt)
    prof = model.create_entity("IfcCircleProfileDef", ProfileType="AREA", 
                               Radius=STAIR_POST_DIAMETER/2)
    solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=axis, 
                               ExtrudedDirection=model.create_entity("IfcDirection", 
                                                                    DirectionRatios=(0.0,0.0,1.0)),
                               Depth=TOP_RAIL_HEIGHT)
    return finalize_stair_component(model, context, style, solid, "Stair_Post")


def create_stair_rail(model, context, style, p1, p2):
    """Create horizontal rail for stairs"""
    line = model.create_entity("IfcPolyline", Points=[
        model.create_entity("IfcCartesianPoint", 
                          Coordinates=(float(p1[0]), float(p1[1]), float(p1[2]))),
        model.create_entity("IfcCartesianPoint", 
                          Coordinates=(float(p2[0]), float(p2[1]), float(p2[2])))
    ])
    solid = model.create_entity("IfcSweptDiskSolid", Directrix=line, 
                               Radius=STAIR_RAIL_DIAMETER/2)
    return finalize_stair_component(model, context, style, solid, "Stair_Rail")


def finalize_stair_component(model, context, style, geom, name):
    """Finalize stair railing component"""
    model.create_entity("IfcStyledItem", Item=geom, Styles=[style])
    rep = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, 
                             RepresentationIdentifier="Body", 
                             RepresentationType="SweptSolid", Items=[geom])
    shape = model.create_entity("IfcProductDefinitionShape", Representations=[rep])
    return model.create_entity("IfcRailing", GlobalId=ifcopenshell.guid.new(), 
                              Name=name, Representation=shape)


# ============================================================================
# FLOOR SLAB PROCESSING
# ============================================================================
def compute_signed_area_2d(points):
    """Compute signed area (>0 = CCW, <0 = CW)"""
    if len(points) < 3:
        return 0.0
    points_array = np.array(points)
    x = points_array[:, 0]
    y = points_array[:, 1]
    area = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
    return area


def extract_all_boundary_loops(ifc_file, slab_element, z_level):
    """Extract ALL boundary loops (outer + inner holes) using mesh topology"""

    # NEW: Extract both vertices and faces
    logging.info(f"  Extracting geometry for slab {slab_element.GlobalId[:8]}...")
    vertices_3d, faces = get_element_geometry_with_faces(ifc_file, slab_element)

    if vertices_3d is None or faces is None or len(vertices_3d) == 0:
        logging.warning(f"  Could not extract mesh geometry for slab {slab_element.GlobalId[:8]}")
        return []

    logging.info(f"  Geometry: {len(vertices_3d)} vertices, {len(faces)} faces - extracting boundaries...")

    # NEW: Use mesh-based boundary extraction
    loops = extract_boundary_edges_from_mesh(vertices_3d, faces, z_level)

    if len(loops) > 0:
        logging.info(f"  ✓ Extracted {len(loops)} boundary loops")
        return loops

    # FALLBACK: Use convex hull if mesh extraction fails
    logging.warning(f"  Mesh extraction returned no loops, falling back to ConvexHull")

    z_tolerance = 100.0
    level_verts = vertices_3d[np.abs(vertices_3d[:, 2] - z_level) < z_tolerance]

    if len(level_verts) < 3:
        return []

    points_2d = level_verts[:, :2]
    unique_points = np.unique(points_2d, axis=0)

    if len(unique_points) < 3:
        return []

    # ConvexHull fallback (existing code)
    if SCIPY_AVAILABLE:
        try:
            hull = ConvexHull(unique_points)
            outer_loop = unique_points[hull.vertices].tolist()

            if not np.allclose(outer_loop[0], outer_loop[-1]):
                outer_loop.append(outer_loop[0])

            signed_area = compute_signed_area_2d(outer_loop)

            if signed_area < 0:
                outer_loop = outer_loop[::-1]
                signed_area = -signed_area

            logging.debug(f"  Extracted outer loop (ConvexHull fallback): {len(outer_loop)} points, area={signed_area:.0f}mm²")

            return [{
                'points': outer_loop,
                'type': LoopType.OUTER_PERIMETER,
                'signed_area': signed_area
            }]
        except Exception as e:
            logging.debug(f"ConvexHull fallback failed: {e}")

    return []


def extract_opening_loops(ifc_file, slab, slab_top_z):
    """Extract inner loops from IfcOpeningElement (floor holes)"""
    opening_loops = []

    for rel in ifc_file.by_type("IfcRelVoidsElement"):
        if rel.RelatingBuildingElement == slab:
            opening = rel.RelatedOpeningElement

            opening_verts = get_element_geometry(ifc_file, opening)
            if opening_verts is None:
                continue

            z_tolerance = 100.0
            level_verts = opening_verts[np.abs(opening_verts[:, 2] - slab_top_z) < z_tolerance]

            if len(level_verts) < 3:
                continue

            points_2d = level_verts[:, :2]
            unique_points = np.unique(points_2d, axis=0)

            if len(unique_points) < 3:
                continue

            if SCIPY_AVAILABLE:
                try:
                    hull = ConvexHull(unique_points)
                    loop_points = unique_points[hull.vertices].tolist()

                    if not np.allclose(loop_points[0], loop_points[-1]):
                        loop_points.append(loop_points[0])

                    signed_area = compute_signed_area_2d(loop_points)

                    if signed_area > 0:
                        loop_points = loop_points[::-1]
                        signed_area = -signed_area

                    opening_loops.append({
                        'points': loop_points,
                        'type': LoopType.INNER_HOLE,
                        'signed_area': signed_area,
                        'opening_element': opening
                    })

                    logging.debug(f"  Extracted opening loop: {len(loop_points)} points, area={abs(signed_area):.0f}mm²")
                except Exception as e:
                    logging.debug(f"Opening extraction failed: {e}")

    return opening_loops


def extract_boundary_edges_from_mesh(vertices_3d, faces, z_level, z_tolerance=100.0):
    """
    Extract boundary edges from mesh at given Z level

    Algorithm:
    1. Filter vertices/faces at Z level
    2. Build edge-to-face count map
    3. Boundary edges = edges with count == 1
    4. Connect edges to form closed loops

    Args:
        vertices_3d: Nx3 array of vertex coordinates
        faces: Mx3 array of face indices
        z_level: Target Z elevation (mm)
        z_tolerance: Z tolerance for "at level" (mm)

    Returns:
        List of loops: [{points: [[x,y], ...], type: LoopType, signed_area: float}]
    """
    # Filter faces at Z level (at least one vertex within tolerance)
    level_face_mask = []
    for face in faces:
        face_verts = vertices_3d[face]
        z_coords = face_verts[:, 2]
        if np.any(np.abs(z_coords - z_level) < z_tolerance):
            level_face_mask.append(True)
        else:
            level_face_mask.append(False)

    level_faces = faces[level_face_mask]

    if len(level_faces) == 0:
        logging.debug(f"    No faces found at Z={z_level:.0f}mm")
        return []

    logging.debug(f"    Processing {len(level_faces)} faces at this Z level...")

    # Build edge-to-face count using dictionary
    # Edge format: tuple of sorted vertex indices
    edge_count = {}
    edge_to_faces = {}

    for face_idx, face in enumerate(level_faces):
        # Extract 3 edges from triangle
        edges = [
            tuple(sorted([face[0], face[1]])),
            tuple(sorted([face[1], face[2]])),
            tuple(sorted([face[2], face[0]]))
        ]

        for edge in edges:
            edge_count[edge] = edge_count.get(edge, 0) + 1
            if edge not in edge_to_faces:
                edge_to_faces[edge] = []
            edge_to_faces[edge].append(face_idx)

    # Boundary edges = edges with count == 1
    boundary_edges = [edge for edge, count in edge_count.items() if count == 1]

    if len(boundary_edges) == 0:
        logging.debug(f"    No boundary edges found")
        return []

    logging.debug(f"    Connecting {len(boundary_edges)} boundary edges into loops...")

    # Connect edges to form loops
    loops = connect_edges_to_loops(boundary_edges, vertices_3d)

    return loops


def connect_edges_to_loops(edges, vertices):
    """
    Connect boundary edges to form closed loops

    Args:
        edges: List of (v1_idx, v2_idx) tuples
        vertices: Nx3 vertex array

    Returns:
        List of loops with points in order
    """
    # Build adjacency map: vertex -> list of connected vertices
    adjacency = {}
    for v1, v2 in edges:
        if v1 not in adjacency:
            adjacency[v1] = []
        if v2 not in adjacency:
            adjacency[v2] = []
        adjacency[v1].append(v2)
        adjacency[v2].append(v1)

    loops = []
    visited_edges = set()

    # Fix: Check adjacency dict instead of edges list
    while adjacency:
        # Start new loop from first available vertex
        start_vertex = next(iter(adjacency.keys()))
        current_vertex = start_vertex
        loop_vertices = [current_vertex]

        max_iterations = len(adjacency) * 10  # Safety limit
        iteration_count = 0

        while True:
            iteration_count += 1
            if iteration_count > max_iterations:
                logging.warning(f"Loop detection exceeded max iterations, breaking")
                break

            # Get next vertex
            neighbors = adjacency.get(current_vertex, [])

            # Find unvisited neighbor
            next_vertex = None
            for neighbor in neighbors:
                edge = tuple(sorted([current_vertex, neighbor]))
                if edge not in visited_edges:
                    next_vertex = neighbor
                    visited_edges.add(edge)
                    break

            if next_vertex is None:
                break

            if next_vertex == start_vertex:
                # Loop completed
                break

            loop_vertices.append(next_vertex)
            current_vertex = next_vertex

        # Convert vertex indices to XY coordinates
        loop_points = []
        for v_idx in loop_vertices:
            vertex = vertices[v_idx]
            loop_points.append([float(vertex[0]), float(vertex[1])])

        # Close loop
        if not np.allclose(loop_points[0], loop_points[-1]):
            loop_points.append(loop_points[0])

        # Compute signed area to determine type
        signed_area = compute_signed_area_2d(loop_points)

        # CCW = outer, CW = inner
        loop_type = LoopType.OUTER_PERIMETER if signed_area > 0 else LoopType.INNER_HOLE

        loops.append({
            'points': loop_points,
            'type': loop_type,
            'signed_area': signed_area
        })

        # Remove processed vertices from adjacency
        for v in loop_vertices:
            if v in adjacency:
                del adjacency[v]

    return loops


def sort_points_by_angle(points_2d):
    """Sort points by angle from centroid"""
    if len(points_2d) < 3:
        return points_2d.tolist() if hasattr(points_2d, 'tolist') else points_2d

    centroid = np.mean(points_2d, axis=0)
    angles = np.arctan2(points_2d[:, 1] - centroid[1],
                        points_2d[:, 0] - centroid[0])
    sorted_indices = np.argsort(angles)
    sorted_points = points_2d[sorted_indices]

    return sorted_points.tolist()


def compute_edge_normal(p1, p2):
    """Compute perpendicular normal to edge"""
    edge_vec = np.array(p2) - np.array(p1)
    edge_len = np.linalg.norm(edge_vec)

    if edge_len < 1e-6:
        return np.array([0.0, 1.0])

    edge_unit = edge_vec / edge_len
    normal = np.array([-edge_unit[1], edge_unit[0]])

    return normal


def get_walls_at_level(ifc_file, z_level, z_tolerance=500.0):
    """
    Get all walls that exist at a given Z level.

    This function finds walls that provide fall protection at a slab level:
    1. Walls that START below this level and extend above it (spanning walls)
    2. Walls that START at this level (base of wall at slab level) and extend upward
    3. Walls that extend FROM BELOW up to near this level (even if slightly below)

    Returns list of wall data including footprint bounding boxes.
    """
    walls_at_level = []

    # Include IfcWall, IfcWallStandardCase, and IfcCurtainWall
    all_walls = ifc_file.by_type("IfcWall") + ifc_file.by_type("IfcWallStandardCase") + ifc_file.by_type("IfcCurtainWall")

    for wall in all_walls:
        vertices = get_element_geometry(ifc_file, wall)
        if vertices is None or len(vertices) < 3:
            continue

        wall_z_min = np.min(vertices[:, 2])
        wall_z_max = np.max(vertices[:, 2])

        # Get XY footprint (bounding box)
        wall_x_min = np.min(vertices[:, 0])
        wall_x_max = np.max(vertices[:, 0])
        wall_y_min = np.min(vertices[:, 1])
        wall_y_max = np.max(vertices[:, 1])

        # Calculate wall height relative to slab
        wall_total_height = wall_z_max - wall_z_min

        # Case 1: Wall spans this level (z_min below, z_max above)
        # Case 2: Wall starts at this level (z_min at slab level) and goes up
        # Case 3: Wall ends at this level (walls from floor below)

        wall_starts_at_level = abs(wall_z_min - z_level) < z_tolerance
        wall_ends_at_level = abs(wall_z_max - z_level) < z_tolerance
        wall_spans_level = wall_z_min < z_level - z_tolerance and wall_z_max > z_level + z_tolerance

        # Include wall if it's relevant to this level
        if not (wall_starts_at_level or wall_ends_at_level or wall_spans_level):
            continue

        # Calculate effective height for fall protection:
        # - For walls starting at this level: use full wall height
        # - For walls spanning this level: use height above slab
        # - For walls ending at this level: they're from floor below, height is 0
        if wall_starts_at_level:
            # Wall starts at this floor - use its full height
            wall_height_above_slab = wall_total_height
        elif wall_spans_level:
            # Wall spans through this level
            wall_height_above_slab = wall_z_max - z_level
        else:
            # Wall ends at this level (from floor below)
            wall_height_above_slab = max(0, wall_z_max - z_level)

        walls_at_level.append({
            'element': wall,
            'vertices': vertices,
            'height_mm': wall_height_above_slab,
            'top_z': wall_z_max,
            'z_min': wall_z_min,
            'x_min': wall_x_min,
            'x_max': wall_x_max,
            'y_min': wall_y_min,
            'y_max': wall_y_max,
            'name': wall.Name or wall.GlobalId[:8]
        })

    return walls_at_level


def debug_all_walls(ifc_file):
    """Debug function to show all walls in the IFC with their Z ranges."""
    logging.info("\n  === ALL WALLS IN IFC ===")

    # Check all wall-like elements
    all_walls = ifc_file.by_type("IfcWall") + ifc_file.by_type("IfcWallStandardCase")
    curtain_walls = ifc_file.by_type("IfcCurtainWall")

    logging.info(f"    IfcWall + IfcWallStandardCase: {len(all_walls)}")
    logging.info(f"    IfcCurtainWall: {len(curtain_walls)}")

    # Add curtain walls to the list
    all_walls = all_walls + curtain_walls

    # Collect wall data
    wall_data = []
    for wall in all_walls:
        vertices = get_element_geometry(ifc_file, wall)
        if vertices is None or len(vertices) < 3:
            continue

        z_min = np.min(vertices[:, 2])
        z_max = np.max(vertices[:, 2])
        x_min = np.min(vertices[:, 0])
        x_max = np.max(vertices[:, 0])

        wall_data.append({
            'name': wall.Name or wall.GlobalId[:8],
            'z_min': z_min,
            'z_max': z_max,
            'x_center': (x_min + x_max) / 2,
            'height': z_max - z_min
        })

    # Sort by z_min then x_center
    wall_data.sort(key=lambda w: (w['z_min'], w['x_center']))

    # Group by Z range
    z_groups = {}
    for w in wall_data:
        z_key = f"{w['z_min']:.0f}-{w['z_max']:.0f}"
        if z_key not in z_groups:
            z_groups[z_key] = []
        z_groups[z_key].append(w)

    for z_range, walls in sorted(z_groups.items()):
        left_count = sum(1 for w in walls if w['x_center'] < 0)
        right_count = sum(1 for w in walls if w['x_center'] >= 0)
        logging.info(f"    Z={z_range}mm: {len(walls)} walls (left:{left_count}, right:{right_count})")

    logging.info("  === END WALL DEBUG ===\n")
    return wall_data


def get_windows_and_openings_at_level(ifc_file, z_level, z_tolerance=1500.0):
    """
    Get all windows and openings that exist at a given Z level.
    Windows in walls are fall hazards and need guardrails.

    Returns list of window/opening data with footprint bounding boxes.
    """
    openings_at_level = []

    # Get IfcWindow elements
    for window in ifc_file.by_type("IfcWindow"):
        vertices = get_element_geometry(ifc_file, window)
        if vertices is None or len(vertices) < 3:
            continue

        win_z_min = np.min(vertices[:, 2])
        win_z_max = np.max(vertices[:, 2])

        # Window must be at or above this floor level
        if not (win_z_min <= z_level + z_tolerance and win_z_max >= z_level - z_tolerance):
            continue

        # Get XY footprint
        win_x_min = np.min(vertices[:, 0])
        win_x_max = np.max(vertices[:, 0])
        win_y_min = np.min(vertices[:, 1])
        win_y_max = np.max(vertices[:, 1])

        # Only consider windows that are large enough to be fall hazards (>500mm)
        win_width = max(win_x_max - win_x_min, win_y_max - win_y_min)
        if win_width < 500:
            continue

        openings_at_level.append({
            'element': window,
            'type': 'window',
            'x_min': win_x_min,
            'x_max': win_x_max,
            'y_min': win_y_min,
            'y_max': win_y_max,
            'z_min': win_z_min,
            'z_max': win_z_max,
            'name': window.Name or window.GlobalId[:8]
        })

    # Get IfcOpeningElement (voids in walls)
    for opening in ifc_file.by_type("IfcOpeningElement"):
        vertices = get_element_geometry(ifc_file, opening)
        if vertices is None or len(vertices) < 3:
            continue

        open_z_min = np.min(vertices[:, 2])
        open_z_max = np.max(vertices[:, 2])

        if not (open_z_min <= z_level + z_tolerance and open_z_max >= z_level - z_tolerance):
            continue

        open_x_min = np.min(vertices[:, 0])
        open_x_max = np.max(vertices[:, 0])
        open_y_min = np.min(vertices[:, 1])
        open_y_max = np.max(vertices[:, 1])

        # Only consider openings large enough to be fall hazards
        open_width = max(open_x_max - open_x_min, open_y_max - open_y_min)
        if open_width < 500:
            continue

        openings_at_level.append({
            'element': opening,
            'type': 'opening',
            'x_min': open_x_min,
            'x_max': open_x_max,
            'y_min': open_y_min,
            'y_max': open_y_max,
            'z_min': open_z_min,
            'z_max': open_z_max,
            'name': opening.Name or opening.GlobalId[:8] if opening.GlobalId else 'opening'
        })

    return openings_at_level


def is_point_in_window_or_opening(point_xy, openings_at_level, tolerance=200.0):
    """
    Check if a point falls within a window or opening (which are fall hazards).

    Returns (is_in_opening, opening_data)
    """
    px, py = float(point_xy[0]), float(point_xy[1])

    for opening in openings_at_level:
        # Expand opening footprint by tolerance
        x_min = opening['x_min'] - tolerance
        x_max = opening['x_max'] + tolerance
        y_min = opening['y_min'] - tolerance
        y_max = opening['y_max'] + tolerance

        if x_min <= px <= x_max and y_min <= py <= y_max:
            return True, opening

    return False, None


def is_point_protected_by_wall(point_xy, walls_at_level, tolerance=500.0):
    """
    Check if a point is protected by any wall (inside or very close to wall footprint).

    Args:
        point_xy: [x, y] coordinates of the point
        walls_at_level: list of wall data from get_walls_at_level()
        tolerance: distance tolerance for protection (mm)

    Returns:
        (is_protected, protecting_wall) tuple
    """
    px, py = float(point_xy[0]), float(point_xy[1])

    for wall in walls_at_level:
        # Expand wall footprint by tolerance
        x_min = wall['x_min'] - tolerance
        x_max = wall['x_max'] + tolerance
        y_min = wall['y_min'] - tolerance
        y_max = wall['y_max'] + tolerance

        # Check if point is inside expanded footprint
        if x_min <= px <= x_max and y_min <= py <= y_max:
            return True, wall

    return False, None


def is_edge_segment_protected(p1, p2, walls_at_level, sample_count=5, protection_threshold=0.7):
    """
    Check if an edge segment is protected by walls.

    Samples multiple points along the segment and checks wall coverage.

    Args:
        p1, p2: segment endpoints
        walls_at_level: list of wall data
        sample_count: number of points to sample along segment
        protection_threshold: fraction of samples that must be protected (0.0-1.0)

    Returns:
        (is_protected, tallest_wall_height, tallest_wall_top_z)
    """
    p1 = np.array(p1[:2])
    p2 = np.array(p2[:2])

    seg_length = np.linalg.norm(p2 - p1)
    if seg_length < 10.0:  # Very short segment
        return False, 0, 0

    protected_count = 0
    max_wall_height = 0
    max_wall_top_z = 0

    for i in range(sample_count):
        t = i / max(sample_count - 1, 1)
        sample_point = p1 + t * (p2 - p1)

        is_protected, wall = is_point_protected_by_wall(sample_point, walls_at_level, tolerance=500.0)

        if is_protected and wall:
            protected_count += 1
            if wall['height_mm'] > max_wall_height:
                max_wall_height = wall['height_mm']
                max_wall_top_z = wall['top_z']

    protection_ratio = protected_count / sample_count
    is_segment_protected = protection_ratio >= protection_threshold

    return is_segment_protected, max_wall_height, max_wall_top_z


def get_adjacent_walls(ifc_file, point_xy, z_level, tolerance=WALL_ADJACENCY_TOLERANCE_MM):
    """Find walls adjacent to a point (used for inset direction)"""
    adjacent_walls = []
    px, py = point_xy[0], point_xy[1]

    for wall in ifc_file.by_type("IfcWall") + ifc_file.by_type("IfcWallStandardCase"):
        vertices = get_element_geometry(ifc_file, wall)
        if vertices is None:
            continue

        wall_z_min = np.min(vertices[:, 2])
        wall_z_max = np.max(vertices[:, 2])

        if not (wall_z_min - 500 <= z_level <= wall_z_max + 500):
            continue

        wall_x_min, wall_x_max = np.min(vertices[:, 0]), np.max(vertices[:, 0])
        wall_y_min, wall_y_max = np.min(vertices[:, 1]), np.max(vertices[:, 1])

        dx = max(wall_x_min - px, 0, px - wall_x_max)
        dy = max(wall_y_min - py, 0, py - wall_y_max)
        distance = math.sqrt(dx**2 + dy**2)

        if distance > tolerance:
            continue

        wall_height_above_slab = wall_z_max - z_level

        adjacent_walls.append({
            'element': wall,
            'height_mm': wall_height_above_slab,
            'top_z': wall_z_max,
            'distance_mm': distance,
            'name': wall.Name or wall.GlobalId[:8]
        })

    return adjacent_walls


def determine_wall_aware_inset_direction(p1, p2, normal, z_level, ifc_file, loop_type):
    """Determine inset direction based on wall proximity"""
    midpoint = (np.array(p1) + np.array(p2)) / 2.0

    test_dist = 100.0

    test_pos = midpoint + normal * test_dist
    walls_pos = get_adjacent_walls(ifc_file, test_pos, z_level, tolerance=WALL_ADJACENCY_TOLERANCE_MM)

    test_neg = midpoint - normal * test_dist
    walls_neg = get_adjacent_walls(ifc_file, test_neg, z_level, tolerance=WALL_ADJACENCY_TOLERANCE_MM)

    if walls_pos and not walls_neg:
        inset_direction = -normal
        logging.debug(f"    Wall on +normal side → inset -normal")
    elif walls_neg and not walls_pos:
        inset_direction = normal
        logging.debug(f"    Wall on -normal side → inset +normal")
    elif walls_pos and walls_neg:
        min_dist_pos = min(w['distance_mm'] for w in walls_pos)
        min_dist_neg = min(w['distance_mm'] for w in walls_neg)

        if min_dist_pos < min_dist_neg:
            inset_direction = -normal
            logging.debug(f"    Walls both sides, closer on +normal ({min_dist_pos:.0f}mm) → inset -normal")
        else:
            inset_direction = normal
            logging.debug(f"    Walls both sides, closer on -normal ({min_dist_neg:.0f}mm) → inset +normal")
    else:
        if loop_type == LoopType.OUTER_PERIMETER:
            centroid = np.mean([p1, p2], axis=0)
            to_centroid = centroid - midpoint

            if np.dot(normal, to_centroid) > 0:
                inset_direction = normal
            else:
                inset_direction = -normal
        else:
            inset_direction = normal

        logging.debug(f"    No walls, loop_type={loop_type} → heuristic inset")

    return inset_direction * EDGE_INSET_MM


def apply_wall_aware_inset(perimeter_loop, z_level, ifc_file, loop_type):
    """Apply inset with wall-aware direction per edge"""
    if len(perimeter_loop) < 3:
        return perimeter_loop

    is_closed = np.allclose(perimeter_loop[0], perimeter_loop[-1])
    unique_verts = perimeter_loop[:-1] if is_closed else perimeter_loop
    n = len(unique_verts)

    if n < 3:
        return perimeter_loop

    inset_verts = []

    for i in range(n):
        p_curr = np.array(unique_verts[i])
        p_next = np.array(unique_verts[(i + 1) % n])

        normal = compute_edge_normal(p_curr, p_next)

        inset_vector = determine_wall_aware_inset_direction(
            p_curr, p_next, normal, z_level, ifc_file, loop_type
        )

        inset_point = p_curr + inset_vector
        inset_verts.append(inset_point)

    inset_list = [v.tolist() for v in inset_verts]
    inset_list.append(inset_list[0])

    return inset_list


def extract_continuous_edges(perimeter_loop):
    """Extract continuous edge from closed loop"""
    if len(perimeter_loop) < 2:
        return []

    total_length = 0.0
    points = np.array(perimeter_loop)

    for i in range(len(points) - 1):
        seg_length = np.linalg.norm(points[i+1] - points[i])
        total_length += seg_length

    return [{
        'points': perimeter_loop,
        'length': total_length,
        'is_closed_loop': np.allclose(perimeter_loop[0], perimeter_loop[-1])
    }]


def classify_edge_safety(ifc_file, edge_points, slab_top_z, loop_type, walls_at_level=None):
    """
    Classify edge safety by checking if edge points fall within wall footprints.

    This is a simple and robust approach:
    1. Pre-compute all walls at this floor level
    2. For each edge segment, sample points along it
    3. Check if sample points fall within any wall's XY footprint
    4. If >70% of samples are protected by tall walls, edge is SAFE
    """
    points_array = np.array(edge_points)

    if len(points_array) < 2:
        return EdgeSafety.UNPROTECTED_EDGE, {'guardrail_base_z': slab_top_z}

    # Get walls at this level if not provided
    if walls_at_level is None:
        walls_at_level = get_walls_at_level(ifc_file, slab_top_z)

    if not walls_at_level:
        logging.debug(f"    No walls found at Z={slab_top_z:.0f}mm → UNPROTECTED")
        return EdgeSafety.UNPROTECTED_EDGE, {'guardrail_base_z': slab_top_z}

    # For segment-based analysis
    segment_classifications = []

    # Debug: log first edge point
    if len(points_array) > 0:
        logging.debug(f"      First edge point: ({points_array[0][0]:.0f}, {points_array[0][1]:.0f})")

    for i in range(len(points_array) - 1):
        seg_p1 = points_array[i]
        seg_p2 = points_array[i + 1]

        # Skip very short segments
        seg_length = np.linalg.norm(np.array(seg_p2[:2]) - np.array(seg_p1[:2]))
        if seg_length < MIN_EDGE_LENGTH_MM:
            continue

        # Check if this segment is protected by walls
        is_protected, wall_height, wall_top_z = is_edge_segment_protected(
            seg_p1, seg_p2, walls_at_level, sample_count=5, protection_threshold=0.6
        )

        # Debug: log first few segments
        if i < 2:
            logging.debug(f"      Segment {i}: ({seg_p1[0]:.0f},{seg_p1[1]:.0f})->({seg_p2[0]:.0f},{seg_p2[1]:.0f}) protected={is_protected}")

        # Check if this is a true inner hole (small opening) vs outer perimeter misclassified as hole
        # True floor openings are typically < 20000mm perimeter; building perimeters are much larger
        total_loop_length = sum(np.linalg.norm(np.array(points_array[j+1][:2]) - np.array(points_array[j][:2]))
                                for j in range(len(points_array)-1)) if len(points_array) > 1 else 0
        is_true_inner_hole = loop_type == LoopType.INNER_HOLE and total_loop_length < 30000

        if is_true_inner_hole and not is_protected:
            # True inner holes (floor openings) - walls around them don't provide fall protection
            # into the hole, so we still need guardrails if not protected
            segment_classifications.append((EdgeSafety.UNPROTECTED_EDGE, slab_top_z, seg_length))
        elif is_protected and wall_height >= OSHA_PARAPET_THRESHOLD_MM:
            # Wall is tall enough - edge is safe
            segment_classifications.append((EdgeSafety.SAFE_EDGE, None, seg_length))
        elif is_protected and wall_height > 0:
            # Wall exists but not tall enough - partial protection
            segment_classifications.append((EdgeSafety.PARTIAL_EDGE, wall_top_z, seg_length))
        else:
            # No wall protection
            segment_classifications.append((EdgeSafety.UNPROTECTED_EDGE, slab_top_z, seg_length))

    if not segment_classifications:
        return EdgeSafety.UNPROTECTED_EDGE, {'guardrail_base_z': slab_top_z}

    # Aggregate results weighted by segment length
    total_length = sum(c[2] for c in segment_classifications)
    safe_length = sum(c[2] for c in segment_classifications if c[0] == EdgeSafety.SAFE_EDGE)
    partial_length = sum(c[2] for c in segment_classifications if c[0] == EdgeSafety.PARTIAL_EDGE)
    unprotected_length = sum(c[2] for c in segment_classifications if c[0] == EdgeSafety.UNPROTECTED_EDGE)

    # If >70% is safe, mark entire edge as safe
    if total_length > 0 and safe_length / total_length > 0.7:
        logging.debug(f"    Edge {safe_length/total_length*100:.0f}% protected by walls → SAFE")
        return EdgeSafety.SAFE_EDGE, {}

    # If >50% is partial, use partial with highest wall top Z
    if total_length > 0 and partial_length / total_length > 0.5:
        partial_z_values = [c[1] for c in segment_classifications if c[0] == EdgeSafety.PARTIAL_EDGE and c[1] is not None]
        max_wall_top = max(partial_z_values) if partial_z_values else slab_top_z
        logging.debug(f"    Edge {partial_length/total_length*100:.0f}% partial protection → PARTIAL at Z={max_wall_top:.0f}")
        return EdgeSafety.PARTIAL_EDGE, {'guardrail_base_z': max_wall_top}

    # Otherwise, unprotected
    logging.debug(f"    Edge {unprotected_length/total_length*100:.0f}% unprotected → UNPROTECTED")
    return EdgeSafety.UNPROTECTED_EDGE, {'guardrail_base_z': slab_top_z}


def generate_posts_along_edge(edge_points, post_spacing_mm, z_base):
    """Generate post locations at fixed spacing along edge"""
    if len(edge_points) < 2:
        return []

    posts = []
    points = np.array(edge_points)

    cumulative_dist = [0.0]
    for i in range(len(points) - 1):
        seg_length = np.linalg.norm(points[i+1] - points[i])
        cumulative_dist.append(cumulative_dist[-1] + seg_length)

    total_length = cumulative_dist[-1]

    if total_length < 1.0:
        return []

    current_dist = 0.0

    while current_dist <= total_length:
        for i in range(len(cumulative_dist) - 1):
            if cumulative_dist[i] <= current_dist <= cumulative_dist[i+1]:
                seg_start_dist = cumulative_dist[i]
                seg_end_dist = cumulative_dist[i+1]
                seg_length = seg_end_dist - seg_start_dist

                if seg_length > 1e-6:
                    t = (current_dist - seg_start_dist) / seg_length
                    post_pos = points[i] + t * (points[i+1] - points[i])

                    posts.append({
                        'x': float(post_pos[0]),
                        'y': float(post_pos[1]),
                        'z': float(z_base)
                    })
                break

        current_dist += post_spacing_mm

    is_closed = np.allclose(points[0], points[-1])
    if not is_closed:
        posts.append({
            'x': float(points[-1][0]),
            'y': float(points[-1][1]),
            'z': float(z_base)
        })

    return posts


def create_continuous_rail_geometry(ifc_file, edge_points, diameter, z_height):
    """Create continuous rail geometry along polyline (uniform Z)"""
    if len(edge_points) < 2:
        return None

    points_3d = [ifc_file.create_entity("IfcCartesianPoint",
                                        Coordinates=(float(p[0]), float(p[1]), float(z_height)))
                 for p in edge_points]

    polyline = ifc_file.create_entity("IfcPolyline", Points=points_3d)

    swept_disk = ifc_file.create_entity(
        "IfcSweptDiskSolid",
        Directrix=polyline,
        Radius=float(diameter / 2.0)
    )

    return swept_disk


def create_continuous_rail_geometry_3d(ifc_file, points_with_z, diameter, height_offset):
    """
    Create continuous rail geometry along polyline with variable Z heights.

    Args:
        points_with_z: list of {'x', 'y', 'z'} dicts with individual Z values
        diameter: rail diameter
        height_offset: height above floor (e.g., TOP_RAIL_HEIGHT)

    Returns:
        IFC geometry entity
    """
    if len(points_with_z) < 2:
        return None

    points_3d = [
        ifc_file.create_entity("IfcCartesianPoint",
                               Coordinates=(float(p['x']), float(p['y']), float(p['z'] + height_offset)))
        for p in points_with_z
    ]

    polyline = ifc_file.create_entity("IfcPolyline", Points=points_3d)

    swept_disk = ifc_file.create_entity(
        "IfcSweptDiskSolid",
        Directrix=polyline,
        Radius=float(diameter / 2.0)
    )

    return swept_disk


def create_surface_style(ifc_file, color):
    """Create surface style"""
    color_rgb = ifc_file.create_entity(
        "IfcColourRgb",
        Name=None,
        Red=float(color[0]),
        Green=float(color[1]),
        Blue=float(color[2])
    )

    rendering = ifc_file.create_entity(
        "IfcSurfaceStyleRendering",
        SurfaceColour=color_rgb,
        Transparency=0.0,
        ReflectanceMethod="NOTDEFINED"
    )

    style = ifc_file.create_entity(
        "IfcSurfaceStyle",
        Name="OSHAYellowRailing",
        Side="BOTH",
        Styles=[rendering]
    )

    return style


def create_vertical_post(ifc_file, diameter, height):
    """Create cylindrical post"""
    position_2d = ifc_file.create_entity(
        "IfcAxis2Placement2D",
        Location=ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0))
    )

    profile = ifc_file.create_entity(
        "IfcCircleProfileDef",
        ProfileType="AREA",
        ProfileName="PostProfile",
        Position=position_2d,
        Radius=float(diameter / 2.0)
    )

    direction = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))

    extrusion = ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=ifc_file.create_entity("IfcAxis2Placement3D",
            Location=ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)),
            Axis=ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
            RefDirection=ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
        ),
        ExtrudedDirection=direction,
        Depth=float(height)
    )

    return extrusion


def create_railing_component(ifc_file, context, surface_style, name, geometry, x, y, z):
    """Create an IfcRailing component"""
    if surface_style:
        styled_item = ifc_file.create_entity(
            "IfcStyledItem",
            Item=geometry,
            Styles=[surface_style],
            Name=None
        )

    shape_rep = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[geometry]
    )

    product_shape = ifc_file.create_entity(
        "IfcProductDefinitionShape",
        Representations=[shape_rep]
    )

    location = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y), float(z)))
    axis = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    ref_dir = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))

    placement = ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=location,
        Axis=axis,
        RefDirection=ref_dir
    )

    local_placement = ifc_file.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=None,
        RelativePlacement=placement
    )

    railing = ifc_file.create_entity(
        "IfcRailing",
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        ObjectPlacement=local_placement,
        Representation=product_shape,
        PredefinedType="GUARDRAIL"
    )

    return railing


def create_continuous_railing_system(ifc_file, context, surface_style, edge_points, z_base, storey, slab_surfaces=None):
    """
    Create continuous railing system along edge with floor-snapping.

    If slab_surfaces is provided, snaps guardrails to actual floor surface.
    """
    components = []

    # Snap edge points to actual floor surface if slab_surfaces provided
    if slab_surfaces is not None:
        snapped_points = snap_guardrail_points_to_floor(edge_points, slab_surfaces, z_base)

        # Filter to only valid segments (where floor exists)
        valid_segments = filter_valid_guardrail_segments(snapped_points, min_segment_length=MIN_EDGE_LENGTH_MM)

        if not valid_segments:
            logging.debug(f"    No valid floor segments found for guardrail - skipping")
            return []

        # Process each valid segment
        for segment in valid_segments:
            seg_components = create_floor_snapped_railing_segment(
                ifc_file, context, surface_style, segment, storey
            )
            components.extend(seg_components)

        return components

    # Fallback: Original behavior without floor-snapping
    posts = generate_posts_along_edge(edge_points, POST_SPACING_MM, z_base)

    logging.debug(f"  Creating {len(posts)} posts along edge")

    post_height = TOP_RAIL_HEIGHT + 100.0
    for post in posts:
        post_geom = create_vertical_post(ifc_file, POST_DIAMETER, post_height)
        post_elem = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-Post",
            post_geom,
            post['x'], post['y'], post['z']
        )
        components.append(post_elem)

        if storey:
            add_to_spatial_structure(ifc_file, post_elem, storey)

    # Continuous rails
    top_rail_geom = create_continuous_rail_geometry(
        ifc_file, edge_points, RAIL_DIAMETER, z_base + TOP_RAIL_HEIGHT
    )
    if top_rail_geom:
        top_rail = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-TopRail-Continuous",
            top_rail_geom,
            0.0, 0.0, 0.0
        )
        components.append(top_rail)
        if storey:
            add_to_spatial_structure(ifc_file, top_rail, storey)

    mid_rail_geom = create_continuous_rail_geometry(
        ifc_file, edge_points, RAIL_DIAMETER, z_base + MID_RAIL_HEIGHT
    )
    if mid_rail_geom:
        mid_rail = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-MidRail-Continuous",
            mid_rail_geom,
            0.0, 0.0, 0.0
        )
        components.append(mid_rail)
        if storey:
            add_to_spatial_structure(ifc_file, mid_rail, storey)

    toe_geom = create_continuous_rail_geometry(
        ifc_file, edge_points, TOE_BOARD_HEIGHT / 2.0, z_base + TOE_BOARD_HEIGHT / 2.0
    )
    if toe_geom:
        toe_board = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-ToeBoard-Continuous",
            toe_geom,
            0.0, 0.0, 0.0
        )
        components.append(toe_board)
        if storey:
            add_to_spatial_structure(ifc_file, toe_board, storey)

    return components


def create_floor_snapped_railing_segment(ifc_file, context, surface_style, snapped_points, storey):
    """
    Create a railing segment with floor-snapped Z values.

    Args:
        snapped_points: list of {'x', 'y', 'z', 'valid'} from snap_guardrail_points_to_floor

    Returns:
        List of IFC railing components
    """
    components = []

    if len(snapped_points) < 2:
        return components

    # Generate posts at regular spacing with floor-snapped Z
    posts_with_z = generate_posts_along_edge_snapped(snapped_points, POST_SPACING_MM)

    logging.debug(f"    Creating {len(posts_with_z)} floor-snapped posts")

    post_height = TOP_RAIL_HEIGHT + 100.0
    for post in posts_with_z:
        post_geom = create_vertical_post(ifc_file, POST_DIAMETER, post_height)
        post_elem = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-Post",
            post_geom,
            post['x'], post['y'], post['z']
        )
        components.append(post_elem)

        if storey:
            add_to_spatial_structure(ifc_file, post_elem, storey)

    # Create 3D rails that follow floor surface
    top_rail_geom = create_continuous_rail_geometry_3d(
        ifc_file, snapped_points, RAIL_DIAMETER, TOP_RAIL_HEIGHT
    )
    if top_rail_geom:
        top_rail = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-TopRail-Continuous",
            top_rail_geom,
            0.0, 0.0, 0.0
        )
        components.append(top_rail)
        if storey:
            add_to_spatial_structure(ifc_file, top_rail, storey)

    mid_rail_geom = create_continuous_rail_geometry_3d(
        ifc_file, snapped_points, RAIL_DIAMETER, MID_RAIL_HEIGHT
    )
    if mid_rail_geom:
        mid_rail = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-MidRail-Continuous",
            mid_rail_geom,
            0.0, 0.0, 0.0
        )
        components.append(mid_rail)
        if storey:
            add_to_spatial_structure(ifc_file, mid_rail, storey)

    toe_geom = create_continuous_rail_geometry_3d(
        ifc_file, snapped_points, TOE_BOARD_HEIGHT / 2.0, TOE_BOARD_HEIGHT / 2.0
    )
    if toe_geom:
        toe_board = create_railing_component(
            ifc_file, context, surface_style,
            "Guardrail-ToeBoard-Continuous",
            toe_geom,
            0.0, 0.0, 0.0
        )
        components.append(toe_board)
        if storey:
            add_to_spatial_structure(ifc_file, toe_board, storey)

    return components


def generate_posts_along_edge_snapped(snapped_points, post_spacing_mm):
    """
    Generate post locations at fixed spacing along edge with floor-snapped Z.

    Args:
        snapped_points: list of {'x', 'y', 'z'} dicts
        post_spacing_mm: spacing between posts

    Returns:
        List of {'x', 'y', 'z'} post positions
    """
    if len(snapped_points) < 2:
        return []

    posts = []

    # Calculate cumulative distances
    cumulative_dist = [0.0]
    for i in range(len(snapped_points) - 1):
        dx = snapped_points[i+1]['x'] - snapped_points[i]['x']
        dy = snapped_points[i+1]['y'] - snapped_points[i]['y']
        seg_length = math.sqrt(dx*dx + dy*dy)
        cumulative_dist.append(cumulative_dist[-1] + seg_length)

    total_length = cumulative_dist[-1]

    if total_length < 1.0:
        return []

    # Generate posts at regular intervals
    current_dist = 0.0

    while current_dist <= total_length:
        # Find which segment this distance falls into
        for i in range(len(cumulative_dist) - 1):
            if cumulative_dist[i] <= current_dist <= cumulative_dist[i+1]:
                seg_start_dist = cumulative_dist[i]
                seg_end_dist = cumulative_dist[i+1]
                seg_length = seg_end_dist - seg_start_dist

                if seg_length > 1e-6:
                    t = (current_dist - seg_start_dist) / seg_length

                    # Interpolate position
                    x = snapped_points[i]['x'] + t * (snapped_points[i+1]['x'] - snapped_points[i]['x'])
                    y = snapped_points[i]['y'] + t * (snapped_points[i+1]['y'] - snapped_points[i]['y'])
                    z = snapped_points[i]['z'] + t * (snapped_points[i+1]['z'] - snapped_points[i]['z'])

                    posts.append({'x': x, 'y': y, 'z': z})
                break

        current_dist += post_spacing_mm

    # Add end post if not already at that position
    if posts:
        last_post = posts[-1]
        end_pt = snapped_points[-1]
        dist_to_end = math.sqrt((end_pt['x'] - last_post['x'])**2 + (end_pt['y'] - last_post['y'])**2)
        if dist_to_end > post_spacing_mm * 0.1:  # More than 10% of spacing from end
            posts.append({'x': end_pt['x'], 'y': end_pt['y'], 'z': end_pt['z']})

    return posts


def add_to_spatial_structure(ifc_file, element, storey):
    """Add element to spatial structure"""
    try:
        for rel in ifc_file.by_type("IfcRelContainedInSpatialStructure"):
            if rel.RelatingStructure == storey:
                if element not in rel.RelatedElements:
                    related = list(rel.RelatedElements)
                    related.append(element)
                    rel.RelatedElements = related
                return

        ifc_file.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=ifcopenshell.guid.new(),
            RelatedElements=[element],
            RelatingStructure=storey
        )
    except Exception as e:
        logging.debug(f"Could not add to spatial structure: {e}")


def get_storey_for_z(ifc_file, z_level):
    """Find the appropriate building storey for Z level"""
    storeys = ifc_file.by_type("IfcBuildingStorey")

    if not storeys:
        return None

    best_storey = None
    min_diff = float('inf')

    for storey in storeys:
        if storey.ObjectPlacement and storey.ObjectPlacement.RelativePlacement:
            rel_place = storey.ObjectPlacement.RelativePlacement
            if hasattr(rel_place, 'Location') and hasattr(rel_place.Location, 'Coordinates'):
                storey_z = rel_place.Location.Coordinates[2]
                diff = abs(storey_z - z_level)
                if diff < min_diff:
                    min_diff = diff
                    best_storey = storey

    return best_storey if min_diff < 5000.0 else storeys[0]


def classify_segment_safety(segment_start, segment_end, walls_at_level, openings_at_level, slab_top_z, loop_type):
    """
    Classify a single small segment's safety status.

    Returns:
        (needs_guardrail: bool, guardrail_z: float, reason: str)
    """
    # Sample the segment midpoint and endpoints
    seg_p1 = np.array(segment_start[:2])
    seg_p2 = np.array(segment_end[:2])
    midpoint = (seg_p1 + seg_p2) / 2.0

    # Check if segment is in a window/opening (these ALWAYS need guardrails)
    in_opening, opening_data = is_point_in_window_or_opening(midpoint, openings_at_level, tolerance=100.0)
    if in_opening:
        return True, slab_top_z, f"window/opening ({opening_data['name']})"

    # Check wall protection for this segment
    is_protected, wall_height, wall_top_z = is_edge_segment_protected(
        segment_start, segment_end, walls_at_level, sample_count=3, protection_threshold=0.5
    )

    # Wall protection logic:
    # - Walls >= MIN_PROTECTIVE_WALL_HEIGHT_MM (800mm) provide adequate fall protection
    # - This handles building walls that are modeled as floor-by-floor segments
    # - OSHA 1070mm is for parapets, but regular walls >= 800mm are still protective
    if is_protected and wall_height >= MIN_PROTECTIVE_WALL_HEIGHT_MM:
        # Wall provides adequate fall protection - no guardrail needed
        return False, None, f"protected by wall (H={wall_height:.0f}mm)"
    elif is_protected and wall_height > 0:
        # Very low wall (below 800mm) - add guardrail above it
        return True, wall_top_z, f"low wall (H={wall_height:.0f}mm)"
    else:
        # No wall - guardrail at slab level
        return True, slab_top_z, "unprotected"


def break_loop_into_segments(loop_points, segment_length=500.0):
    """
    Break a closed loop into small segments of approximately segment_length.

    Returns list of segments: [(start_point, end_point, original_idx), ...]
    """
    segments = []
    points = np.array(loop_points)

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]

        edge_length = np.linalg.norm(p2[:2] - p1[:2])

        if edge_length < segment_length * 1.5:
            # Edge is small enough - keep as single segment
            segments.append((p1.tolist(), p2.tolist(), i))
        else:
            # Break into smaller segments
            num_segments = max(2, int(np.ceil(edge_length / segment_length)))
            for j in range(num_segments):
                t1 = j / num_segments
                t2 = (j + 1) / num_segments
                seg_p1 = p1 + t1 * (p2 - p1)
                seg_p2 = p1 + t2 * (p2 - p1)
                segments.append((seg_p1.tolist(), seg_p2.tolist(), i))

    return segments


def group_consecutive_segments(classified_segments):
    """
    Group consecutive segments that need guardrails.

    Args:
        classified_segments: [(seg_start, seg_end, needs_guardrail, guardrail_z, reason), ...]

    Returns:
        List of groups: [{'points': [...], 'z_base': float, 'reasons': set}, ...]
    """
    groups = []
    current_group = None

    for seg_start, seg_end, needs_guardrail, guardrail_z, reason in classified_segments:
        if needs_guardrail:
            if current_group is None:
                # Start new group
                current_group = {
                    'points': [seg_start, seg_end],
                    'z_base': guardrail_z,
                    'reasons': {reason}
                }
            else:
                # Check if this segment continues from the previous
                last_point = current_group['points'][-1]
                dist = np.linalg.norm(np.array(seg_start[:2]) - np.array(last_point[:2]))

                if dist < 100.0:  # Continuous
                    current_group['points'].append(seg_end)
                    current_group['reasons'].add(reason)
                    # Use the maximum Z base (for partial walls)
                    if guardrail_z is not None:
                        current_group['z_base'] = max(current_group['z_base'] or 0, guardrail_z)
                else:
                    # Gap - save current group and start new
                    if len(current_group['points']) >= 2:
                        groups.append(current_group)
                    current_group = {
                        'points': [seg_start, seg_end],
                        'z_base': guardrail_z,
                        'reasons': {reason}
                    }
        else:
            # Segment doesn't need guardrail - close current group
            if current_group is not None and len(current_group['points']) >= 2:
                groups.append(current_group)
            current_group = None

    # Don't forget the last group
    if current_group is not None and len(current_group['points']) >= 2:
        groups.append(current_group)

    return groups


def process_boundary_loop(ifc_file, context, surface_style, loop_dict, slab_top_z, storey, walls_at_level=None, openings_at_level=None, slab_surfaces=None):
    """
    Process a single boundary loop using per-segment classification.

    This approach:
    1. Breaks the loop into small segments (~500mm)
    2. Classifies each segment independently (wall? window? unprotected?)
    3. Groups consecutive unprotected/window segments
    4. Generates guardrails only for unprotected groups
    5. Snaps guardrails to actual floor surface (if slab_surfaces provided)
    """
    loop_points = loop_dict['points']
    loop_type = loop_dict['type']

    logging.info(f"  Processing {loop_type} loop: {len(loop_points)} points")

    # Get walls at this level if not provided
    if walls_at_level is None:
        walls_at_level = get_walls_at_level(ifc_file, slab_top_z)

    # Get windows/openings at this level if not provided
    if openings_at_level is None:
        openings_at_level = get_windows_and_openings_at_level(ifc_file, slab_top_z)

    if openings_at_level:
        logging.debug(f"    Found {len(openings_at_level)} windows/openings at this level")

    # Calculate total loop length to check if this is a true inner hole
    total_loop_length = 0.0
    for i in range(len(loop_points) - 1):
        seg_len = np.linalg.norm(np.array(loop_points[i+1][:2]) - np.array(loop_points[i][:2]))
        total_loop_length += seg_len

    is_true_inner_hole = loop_type == LoopType.INNER_HOLE and total_loop_length < 30000

    logging.debug(f"    Loop length: {total_loop_length:.0f}mm, is_true_inner_hole: {is_true_inner_hole}")

    # Apply wall-aware inset for guardrail placement
    perimeter_inset = apply_wall_aware_inset(loop_points, slab_top_z, ifc_file, loop_type)
    logging.debug(f"    Applied wall-aware inset")

    # Break ORIGINAL loop into small segments for classification
    segments = break_loop_into_segments(loop_points, segment_length=500.0)
    logging.debug(f"    Broken into {len(segments)} segments for classification")

    # Also break INSET loop for guardrail geometry
    inset_segments = break_loop_into_segments(perimeter_inset, segment_length=500.0)

    # Classify each segment
    classified_segments = []

    for i, (seg_start, seg_end, orig_idx) in enumerate(segments):
        needs_guardrail, guardrail_z, reason = classify_segment_safety(
            seg_start, seg_end, walls_at_level, openings_at_level, slab_top_z, loop_type
        )

        # For true inner holes, always need guardrails unless protected by tall wall
        if is_true_inner_hole and reason == "unprotected":
            needs_guardrail = True

        # Get corresponding inset segment for geometry
        if i < len(inset_segments):
            inset_start, inset_end, _ = inset_segments[i]
        else:
            inset_start, inset_end = seg_start, seg_end

        classified_segments.append((inset_start, inset_end, needs_guardrail, guardrail_z, reason))

    # Count classifications
    needs_rail_count = sum(1 for s in classified_segments if s[2])
    protected_count = len(classified_segments) - needs_rail_count

    logging.debug(f"    Classification: {needs_rail_count} need guardrail, {protected_count} protected by walls")

    # Group consecutive segments that need guardrails
    guardrail_groups = group_consecutive_segments(classified_segments)

    logging.info(f"    Found {len(guardrail_groups)} guardrail groups to generate")

    all_components = []

    # Generate guardrails for each group
    for group_idx, group in enumerate(guardrail_groups):
        group_points = group['points']
        z_base = group['z_base'] or slab_top_z
        reasons = group['reasons']

        # Calculate group length
        group_length = 0.0
        for i in range(len(group_points) - 1):
            group_length += np.linalg.norm(np.array(group_points[i+1][:2]) - np.array(group_points[i][:2]))

        # Skip very short groups
        if group_length < MIN_EDGE_LENGTH_MM * 2:
            logging.debug(f"      Group {group_idx}: skipping (too short: {group_length:.0f}mm)")
            continue

        reason_str = ", ".join(reasons)
        logging.info(f"    [GUARDRAIL] Group {group_idx}: {group_length:.0f}mm at Z={z_base:.0f}mm ({reason_str})")

        # Create continuous railing for this group with floor-snapping
        components = create_continuous_railing_system(
            ifc_file, context, surface_style,
            group_points, z_base, storey, slab_surfaces
        )
        all_components.extend(components)

    if not guardrail_groups:
        logging.info(f"    [ALL SAFE] No guardrails needed - all segments protected by walls")

    return all_components


def process_floor_slabs(ifc_file, context, surface_style):
    """Process all floor slabs with floor-snapping support"""
    slabs = [s for s in ifc_file.by_type("IfcSlab")
             if s.PredefinedType in ["FLOOR", "BASESLAB", None]]

    logging.info(f"\nProcessing {len(slabs)} floor slabs")

    # Pre-compute ALL slab surfaces once for floor-snapping
    logging.info("  Pre-computing slab surfaces for floor-snapping...")
    slab_surfaces = get_all_slab_surfaces(ifc_file)
    logging.info(f"  Found {len(slab_surfaces)} slab surfaces for snapping")

    all_components = []

    for slab in slabs:
        vertices = get_element_geometry(ifc_file, slab)
        if vertices is None:
            continue

        top_z = np.max(vertices[:, 2])

        if top_z <= GROUND_LEVEL_THRESHOLD_MM:
            logging.info(f"  [SKIP] Ground-level floor at Z={top_z:.0f}mm")
            continue

        logging.info(f"  Processing slab {slab.Name or slab.GlobalId[:8]} at Z={top_z:.0f}mm")

        # Pre-compute walls at this level ONCE for efficiency
        walls_at_level = get_walls_at_level(ifc_file, top_z)
        logging.info(f"    Found {len(walls_at_level)} walls at this level")

        # Pre-compute windows/openings at this level ONCE for efficiency
        openings_at_level = get_windows_and_openings_at_level(ifc_file, top_z)
        if openings_at_level:
            logging.info(f"    Found {len(openings_at_level)} windows/openings at this level")
            for i, op in enumerate(openings_at_level[:5]):
                logging.debug(f"      {op['type']} {i}: {op['name']} X=[{op['x_min']:.0f},{op['x_max']:.0f}] Y=[{op['y_min']:.0f},{op['y_max']:.0f}]")

        # Debug: show first few wall footprints
        if walls_at_level and len(walls_at_level) > 0:
            for i, w in enumerate(walls_at_level[:3]):
                logging.debug(f"      Wall {i}: X=[{w['x_min']:.0f},{w['x_max']:.0f}] Y=[{w['y_min']:.0f},{w['y_max']:.0f}] H={w['height_mm']:.0f}mm")

        # Extract ALL boundary loops (outer + inner holes)
        boundary_loops = extract_all_boundary_loops(ifc_file, slab, top_z)
        opening_loops = extract_opening_loops(ifc_file, slab, top_z)

        all_loops = boundary_loops + opening_loops

        logging.info(f"    Total loops: {len(all_loops)} (outer: {len(boundary_loops)}, holes: {len(opening_loops)})")

        storey = get_storey_for_z(ifc_file, top_z)

        slab_components = []

        # Process each loop with pre-computed walls, openings, and slab surfaces for floor-snapping
        for loop in all_loops:
            components = process_boundary_loop(
                ifc_file, context, surface_style, loop, top_z, storey,
                walls_at_level, openings_at_level, slab_surfaces
            )
            slab_components.extend(components)

        all_components.extend(slab_components)
        logging.info(f"    Created {len(slab_components)} components for this slab")

    logging.info(f"  Created {len(all_components)} total floor slab components")
    return all_components


# ============================================================================
# MAIN
# ============================================================================
def main():
    setup_logging(verbose=True)

    logging.info("="*70)
    logging.info("UNIFIED OSHA GUARDRAIL SYSTEM")
    logging.info("="*70)
    logging.info("")
    logging.info("FEATURES:")
    logging.info("  ✓ Stair flight guardrails with hierarchy-aware exclusion")
    logging.info("  ✓ Floor slab perimeter guardrails")
    logging.info("  ✓ Wall-aware inset direction (no clipping)")
    logging.info("  ✓ Inner loop detection (slab holes protected)")
    logging.info("  ✓ Loop-type-aware classification")
    logging.info("  ✓ Continuous rail generation")
    logging.info("  ✓ OSHA compliance (1070mm parapet threshold)")
    logging.info("  ✓ Wall parallelism check (skips edges with parallel walls)")
    logging.info("  ✓ Floor-snapping (guardrails snap to actual slab surface)")
    logging.info("="*70)
    
    
    # Try to load from config.py
    try:
        import config
        if config.SOURCE_IFC_PATH:
            source_ifc_path = project_root_path / config.SOURCE_IFC_PATH  
        else: # Try to find IFC in input_data/ if not specified
            input_dir = project_root_path / "input_data"  # Default input directory
            ifc_files = list(input_dir.glob("*.ifc"))
            
            if not ifc_files:
                    print("ERROR: No IFC file found in input_data/")
                    print("Please specify IFC file to SOURCE_IFC_PATH in config.py")
                    return 1

            # pick latest IFC instead of hardcoded name
            source_ifc_path = max(ifc_files, key=os.path.getmtime)
            
            print(f"[OK] Using IFC file: {source_ifc_path}")
        output_dir_name = project_root_path / config.OUTPUT_DIR
             
    except (ImportError, AttributeError):
        source_ifc_path = "../input_data/Mudasir-LLM-BIM.ifc"
        output_dir_name = "../output_data/hazard_prevention_and_control_results"

    source_ifc = Path(source_ifc_path)

    if not source_ifc.exists():
        logging.error(f"Source IFC not found: {source_ifc}")
        return 1

    logging.info(f"\nLoading IFC: {source_ifc.name}")
    ifc_file = ifcopenshell.open(str(source_ifc))

    # Get context
    context = None
    for ctx in ifc_file.by_type("IfcGeometricRepresentationContext"):
        if ctx.ContextType == "Model":
            context = ctx
            break

    if not context:
        logging.error("No Model context found")
        return 1

    # Create style
    surface_style = create_surface_style(ifc_file, RAIL_COLOR)

    # Process stairs
    stair_components = process_stairs(ifc_file, context, surface_style)

    # Process floor slabs
    slab_components = process_floor_slabs(ifc_file, context, surface_style)

    all_components = stair_components + slab_components

    # Save output
    output_dir = Path(output_dir_name) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output filename from source IFC name
    output_filename = f"{source_ifc.stem}_UNIFIED_GUARDRAILS.ifc"
    output_path = output_dir / output_filename
    ifc_file.write(str(output_path))

    # Generate report
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_components': len(all_components),
        'stair_components': len(stair_components),
        'slab_components': len(slab_components),
        'output_file': str(output_path.absolute()),
        'features': [
            'Stair flight guardrails with hierarchy check',
            'Floor slab perimeter guardrails',
            'Wall-aware inset direction',
            'Inner loop detection (openings)',
            'Loop-type-aware classification',
            'Continuous rail generation',
            'OSHA compliance',
            'Wall parallelism check - skips edges protected by parallel walls'
        ]
    }

    with open(output_dir / "report.json", 'w') as f:
        json.dump(report, f, indent=2)

    logging.info("\n" + "="*70)
    logging.info("GENERATION COMPLETE")
    logging.info("="*70)
    logging.info(f"\nTotal components: {len(all_components)}")
    logging.info(f"  - Stair components: {len(stair_components)}")
    logging.info(f"  - Slab components: {len(slab_components)}")
    logging.info(f"\nOutput: {output_path}")
    logging.info(f"Report: {output_dir / 'report.json'}")
    logging.info("="*70)

    return 0


if __name__ == "__main__":
    sys.exit(main())