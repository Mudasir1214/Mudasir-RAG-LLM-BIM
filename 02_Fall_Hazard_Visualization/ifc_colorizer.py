"""
IFC Colorizer Module
Handles coloring of IFC elements based on detected hazards
"""

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any


class IfcColorizer:
    """Handles IFC element coloring for hazard visualization"""

    def __init__(self, ifc_file: ifcopenshell.file, config):
        """
        Initialize the colorizer

        Args:
            ifc_file: Loaded IFC file
            config: Configuration module
        """
        self.ifc = ifc_file
        self.config = config
        self.colored_elements = []
        self.color_mapping = {}  # element_id -> (hazard_type, severity, color)
        self.created_markers = []

        logging.info(f"Initialized IFC Colorizer for schema: {ifc_file.schema}")

    def color_hazard(self, hazard: Dict[str, Any]) -> bool:
        """
        Color an element based on detected hazard
        
        Args:
            hazard: Hazard dictionary from hazards_detected.json
            
        Returns:
            True if successfully colored, False otherwise
        """
        # Handle different JSON formats
        hazard_type = hazard.get("HazardType") or hazard.get("SpecificHazard", "Unknown")
        severity = hazard.get("Severity", "Unknown")
        
        # Try to get element ID from different possible fields
        element_id = hazard.get("ElementID")
        element_type = hazard.get("ElementType")
        location = hazard.get("Location", {})

        # If no direct ElementID, try ElementContext
        if not element_id and "ElementContext" in hazard:
            ctx = hazard["ElementContext"]
            
            # PRIORITY 1: Direct numeric ElementID field (from Phase 1 V2)
            if "ElementID" in ctx and ctx["ElementID"]:
                element_id = str(ctx["ElementID"])
                logging.debug(f"Found numeric ElementID: {element_id}")
            
            # PRIORITY 2: Extract from name strings
            if not element_id:
                for field in ["Opening", "Element", "Slab", "Beam", "Column", "Wall", "Roof"]:
                    if field in ctx and ctx[field]:
                        extracted_id = self._extract_element_id_from_string(str(ctx[field]))
                        if extracted_id:
                            element_id = extracted_id
                            logging.debug(f"Extracted ElementID {element_id} from {field}: {ctx[field]}")
                            break
            
            # Get element type from context
            type_fields = ["OpeningType", "ElementType", "SlabType", "BeamType", "ColumnType", "WallType"]
            for field in type_fields:
                if field in ctx and ctx[field]:
                    element_type = ctx[field]
                    break
        
        # Get color for this HAZARD TYPE (5-Color Warning System)
        if hasattr(self.config, 'HAZARD_COLORS'):
            # Direct hazard mapping
            color = self.config.HAZARD_COLORS.get(hazard_type)
            # Fallback for generic 'Opening' to FloorOpening color if specific not found
            if not color and "Opening" in hazard_type:
                color = self.config.HAZARD_COLORS.get("FloorOpening")
            # Fallback to Unknown
            if not color:
                color = self.config.HAZARD_COLORS.get("Unknown", (0.5, 0.5, 0.5))
        else:
            # Fallback to severity (Legacy)
            color = self.config.SEVERITY_COLORS.get(severity, self.config.SEVERITY_COLORS["Unknown"])

        success = False

        # Determine if we should create a marker
        # Markers ONLY for openings (voids) - stairs should be colored, not marked
        is_opening = "Opening" in hazard_type or "Void" in str(element_type)
        is_stairway = "Stairway" in hazard_type or "Stair" in hazard_type
        should_create_marker = is_opening and getattr(self.config, 'CREATE_OPENING_MARKERS', True)

        # 1. Try to color existing element (Primary visualization for solid objects like Stairs, Slabs)
        if element_id:
            element = self._find_element_by_id(element_id)
            if element:
                # If location is missing/invalid, try to get it from the element
                # This is crucial for Openings/Voids where we need a marker location but JSON might not have it
                if not location or (location.get("X") == 0 and location.get("Y") == 0 and location.get("Z") == 0):
                     elem_pos = self._get_element_position(element)
                     if elem_pos is not None:
                         location = {"X": elem_pos[0], "Y": elem_pos[1], "Z": elem_pos[2]}
                         logging.debug(f"Derived location from element {element_id}: {location}")

                # Try to color the element
                # For openings: skip coloring (they're voids), go straight to markers
                # For stairs and other elements: color them
                if is_opening:
                    pass  # Openings (voids) can't be colored, will create markers below
                else:
                    # Color stairs, slabs, walls, etc.
                    if self._apply_color_to_element(element, color, hazard_type, severity):
                        success = True
                        if is_stairway:
                            logging.info(f"Colored stair element {element_id} - {hazard_type} ({severity})")
                        else:
                            logging.info(f"Colored element {element_id} ({element_type}) - {hazard_type} ({severity})")
                    elif is_stairway:
                        # Stair has no representation, try location-based coloring
                        logging.debug(f"Stair {element_id} has no representation, will try location-based coloring")
        
        # 2. Location-based coloring fallback (if ID failed and not an opening)
        # Try for stairs and other elements, but not voids/openings
        if not success and location and not is_opening:
            elements = self._find_elements_by_location(hazard_type, location, element_type)
            if elements:
                for elem in elements:
                    if self._apply_color_to_element(elem, color, hazard_type, severity):
                        success = True
                        if is_stairway:
                            logging.info(f"Colored stair {elem.id()} by location - {hazard_type} ({severity})")
                        else:
                            logging.info(f"Colored element {elem.id()} by location - {hazard_type} ({severity})")

        # 3. Create Markers for Openings/Voids and Building Edges
        # Check if this is a building edge (UnprotectedSidesAndEdges with Edge field)
        elem_ctx = hazard.get("ElementContext", {})
        is_building_edge = (hazard_type == "UnprotectedSidesAndEdges" and
                           elem_ctx and elem_ctx.get("Edge"))

        # Create markers for openings, building edges, OR failed stairways
        if should_create_marker or (not success and is_opening) or (not success and is_building_edge) or (not success and is_stairway):
             # Ensure we have a valid location
            if location and (location.get("X") != 0 or location.get("Y") != 0 or location.get("Z") != 0):
                marker = self._create_opening_marker(location, color, hazard_type, severity)
                if marker:
                    success = True
                    if is_building_edge:
                        logging.info(f"Created edge marker for {hazard_type} at {location}")
                    else:
                        logging.info(f"Created marker for {hazard_type} ({severity}) at {location}")
            else:
                logging.warning(f"Cannot create marker for {hazard_type}: No location found.")

        return success

    def _should_skip_severity(self, severity: str) -> bool:
        """Check if severity should be skipped based on config"""
        if self.config.MIN_SEVERITY_TO_COLOR is None:
            return False

        severity_order = ["Low", "Medium", "High", "Critical"]
        min_severity = self.config.MIN_SEVERITY_TO_COLOR

        if severity not in severity_order or min_severity not in severity_order:
            return False

        return severity_order.index(severity) < severity_order.index(min_severity)

    def _extract_element_id_from_string(self, text: str) -> Optional[str]:
        """Extract element ID from a string like 'Floor:Generic 150mm:339'"""
        import re
        # Look for pattern like ':number' at the end
        match = re.search(r':(\d+)$', text)
        if match:
            return match.group(1)
        return None

    def _find_element_by_id(self, element_id: Any) -> Optional[Any]:
        """Find IFC element by ID string, GlobalId, or integer"""
        try:
            # Handle integer input
            if isinstance(element_id, int):
                return self.ifc.by_id(element_id)

            # Handle string input
            elif isinstance(element_id, str):
                # Try numeric ID first (with or without # prefix)
                if element_id.startswith("#"):
                    try:
                        elem_id = int(element_id[1:])
                        return self.ifc.by_id(elem_id)
                    except ValueError:
                        pass

                # Try as plain integer
                try:
                    elem_id = int(element_id)
                    return self.ifc.by_id(elem_id)
                except ValueError:
                    pass

                # Try as GlobalId (GUID format like "1HdfZJUMf0EhQ4hSrvAATB")
                try:
                    return self.ifc.by_guid(element_id)
                except RuntimeError:
                    logging.debug(f"Could not find element by GlobalId: {element_id}")
                    return None

            return None

        except (ValueError, RuntimeError) as e:
            logging.debug(f"Could not find element by ID {element_id}: {e}")
            return None

    def _find_elements_by_location(self, hazard_type: str, location: Dict,
                                   element_type: str = None) -> List[Any]:
        """
        Find IFC elements near the hazard location

        Args:
            hazard_type: Type of hazard
            location: Location dictionary with X, Y, Z coordinates
            element_type: Expected element type

        Returns:
            List of matching IFC elements
        """
        candidates = []

        # Get expected element types for this hazard
        expected_types = self.config.HAZARD_ELEMENT_TYPES.get(hazard_type, [])
        if element_type and element_type not in expected_types:
            expected_types.append(element_type)

        # Search for elements of expected types
        for ifc_type in expected_types:
            try:
                elements = self.ifc.by_type(ifc_type)
                candidates.extend(elements)
            except:
                pass

        if not candidates:
            logging.warning(f"No candidate elements found for {hazard_type}")
            return []

        # Extract location coordinates
        try:
            target_x = float(location.get("X", 0))
            target_y = float(location.get("Y", 0))
            target_z = float(location.get("Z", 0))
            target_pos = np.array([target_x, target_y, target_z])
        except (ValueError, TypeError):
            logging.warning(f"Invalid location coordinates: {location}")
            return []

        # Find elements closest to the hazard location
        matches = []
        for elem in candidates:
            elem_pos = self._get_element_position(elem)
            if elem_pos is not None:
                distance = np.linalg.norm(elem_pos - target_pos)
                matches.append((elem, distance))

        # Sort by distance and return closest matches
        matches.sort(key=lambda x: x[1])

        # Return elements within reasonable distance (5 meters)
        threshold = 5000  # mm
        return [elem for elem, dist in matches if dist < threshold][:5]  # Max 5 elements

    def _get_element_position(self, element: Any) -> Optional[np.ndarray]:
        """Get the absolute world position of an IFC element"""
        try:
            # Method 1: Use ifcopenshell.util.placement (Best for absolute coords)
            if hasattr(ifcopenshell.util.placement, "get_local_placement"):
                matrix = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
                # The position is the translation part (last column)
                return np.array([matrix[0][3], matrix[1][3], matrix[2][3]])

            # Method 2: Fallback to local placement (legacy behavior, incorrect for deep hierarchies)
            if hasattr(element, 'ObjectPlacement') and element.ObjectPlacement:
                placement = element.ObjectPlacement
                if placement.is_a('IfcLocalPlacement'):
                    rel_placement = placement.RelativePlacement
                    if rel_placement and rel_placement.is_a('IfcAxis2Placement3D'):
                        location = rel_placement.Location
                        if location and hasattr(location, 'Coordinates'):
                            coords = location.Coordinates
                            return np.array([coords[0], coords[1], coords[2]])

        except Exception as e:
            logging.debug(f"Could not get position for element {element.id()}: {e}")

        return None



    def _apply_color_to_element(self, element: Any, color: Tuple[float, float, float],
                                hazard_type: str, severity: str) -> bool:
        """
        Apply color to an IFC element

        Args:
            element: IFC element to color
            color: RGB color tuple (0-1 scale)
            hazard_type: Type of hazard
            severity: Severity level

        Returns:
            True if successfully colored
        """
        try:
            elem_id = element.id()

            # Check if element already colored and if we should preserve it
            if elem_id in self.color_mapping and self.config.PRESERVE_EXISTING_COLORS:
                logging.debug(f"Preserving existing color for element {elem_id}")
                return False

            # Check if this hazard has higher priority than existing color
            if elem_id in self.color_mapping:
                existing_hazard = self.color_mapping[elem_id][0]
                existing_priority = self.config.HAZARD_PRIORITY.get(existing_hazard, 0)
                new_priority = self.config.HAZARD_PRIORITY.get(hazard_type, 0)

                if new_priority <= existing_priority:
                    logging.debug(f"Keeping higher priority color on element {elem_id}")
                    return False

            # Create or get style for this element
            style = self._create_surface_style(color)
            if not style:
                return False

            # Apply style to element (and its children if aggregate)
            success = self._assign_style_recursive(element, style)

            if success:
                self.colored_elements.append(elem_id)
                self.color_mapping[elem_id] = (hazard_type, severity, color)

            return success

        except Exception as e:
            logging.error(f"Error applying color to element {element.id()}: {e}")
            return False

    def _create_surface_style(self, color: Tuple[float, float, float], transparency: Optional[float] = None) -> Optional[Any]:
        """Create an IFC surface style with the given color"""
        try:
            # Create color RGB
            color_rgb = self.ifc.create_entity(
                "IfcColourRgb",
                Name=None,
                Red=float(color[0]),
                Green=float(color[1]),
                Blue=float(color[2])
            )

            # Determine transparency
            # If not provided, use config default
            # IF config.COLOR_TRANSPARENCY is opacity (1.0 = opaque), then transparency is 1 - val
            if transparency is None:
                transparency_val = 1.0 - self.config.COLOR_TRANSPARENCY
            else:
                transparency_val = transparency

            # Create rendering style
            rendering_style = self.ifc.create_entity(
                "IfcSurfaceStyleRendering",
                SurfaceColour=color_rgb,
                Transparency=float(transparency_val),
                ReflectanceMethod="NOTDEFINED"
            )

            # Create surface style
            surface_style = self.ifc.create_entity(
                "IfcSurfaceStyle",
                Name="HazardHighlight",
                Side="BOTH",
                Styles=[rendering_style]
            )

            return surface_style

        except Exception as e:
            logging.error(f"Error creating surface style: {e}")
            return None

    def _assign_style_recursive(self, element: Any, style: Any) -> bool:
        """Assign style to element and its decomposed parts (e.g. Stair -> Flights)"""
        success = False

        # 1. Try to color the element itself
        if self._assign_style_to_element(element, style):
            success = True

        # 2. Check for decomposition (e.g. IfcStair -> IfcStairFlight)
        # This handles aggregate elements like Stairs that contain flights/landings but have no geometry themselves
        if hasattr(element, 'IsDecomposedBy'):
            for rel in element.IsDecomposedBy:
                if hasattr(rel, 'RelatedObjects'):
                    for child in rel.RelatedObjects:
                        # IMPORTANT: Skip railings when coloring stairs
                        # Railings should NOT be colored even if they're children of unsafe stairs
                        # Only the stair flights and landings should be colored
                        if child.is_a('IfcRailing'):
                            logging.debug(f"Skipping railing child {child.id()} when coloring parent element")
                            continue

                        # Recursive call for non-railing children
                        if self._assign_style_recursive(child, style):
                            success = True

        return success

    def _assign_style_to_element(self, element: Any, style) -> bool:
        """Assign a style to an element's representation"""
        try:
            # Check if element has representation
            if not hasattr(element, 'Representation') or not element.Representation:
                # Silent return for debug - expected for parent containers
                return False

            representation = element.Representation

            # Iterate through representations
            if hasattr(representation, 'Representations'):
                for rep in representation.Representations:
                    # Get or create styled item
                    if hasattr(rep, 'Items'):
                        for item in rep.Items:
                            self._apply_style_to_item(item, style)

            return True

        except Exception as e:
            logging.error(f"Error assigning style to element: {e}")
            return False

    def _apply_style_to_item(self, item, style):
        """Apply style to a representation item"""
        try:
            # Check if item already has styled representation
            styled_item = None

            if hasattr(item, 'StyledByItem') and item.StyledByItem:
                styled_item = item.StyledByItem[0]
            else:
                # Create new styled item
                styled_item = self.ifc.create_entity(
                    "IfcStyledItem",
                    Item=item,
                    Styles=[style],
                    Name=None
                )

            # Update styles
            if styled_item and hasattr(styled_item, 'Styles'):
                # Replace existing styles
                styled_item.Styles = [style]

        except Exception as e:
            logging.debug(f"Could not apply style to item: {e}")

    def _create_opening_marker(self, location: Dict, color: Tuple[float, float, float],
                               hazard_type: str, severity: str) -> Optional[Any]:
        """
        Create a marker geometry at opening location

        Args:
            location: Location dictionary
            color: RGB color
            hazard_type: Type of hazard
            severity: Severity level

        Returns:
            Created marker element or None
        """
        try:
            # Extract coordinates
            x = float(location.get("X", 0))
            y = float(location.get("Y", 0))
            z = float(location.get("Z", 0))

            # Create a simple box marker
            marker = self._create_box_marker(x, y, z, self.config.MARKER_SIZE, color)

            if marker:
                self.created_markers.append({
                    "element": marker,
                    "hazard_type": hazard_type,
                    "severity": severity,
                    "location": (x, y, z)
                })

            return marker

        except Exception as e:
            logging.error(f"Error creating opening marker: {e}")
            return None

    def _create_box_marker(self, x: float, y: float, z: float,
                           size: float, color: Tuple[float, float, float]) -> Optional[Any]:
        """Create a simple box marker using IfcExtrudedAreaSolid for max compatibility"""
        try:
            # 1. Find correct 3D Model Context
            context = None
            for c in self.ifc.by_type("IfcGeometricRepresentationContext"):
                if c.ContextType == 'Model' and c.CoordinateSpaceDimension == 3:
                    context = c
                    break
            if not context:
                # Fallback to any context
                contexts = self.ifc.by_type("IfcGeometricRepresentationContext")
                if contexts:
                    context = contexts[0]
                else:
                    logging.error("No IfcGeometricRepresentationContext found in file!")
                    return None
            
            # 2. Create Geometry: Extruded Rectangle (More robust than IfcBlock)
            # Center of the box will be at (x,y,z)
            half_size = size / 2.0
            
            # Create rectangle profile
            rect_profile = self.ifc.create_entity("IfcRectangleProfileDef",
                ProfileType="AREA",
                ProfileName="MarkerProfile",
                XDim=float(size),
                YDim=float(size)
            )
            
            # Extrusion Position Placement (Base of extrusion)
            # Shift Z down by half_size to center vertical around the insertion point
            pt = self.ifc.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, -half_size))
            extrusion_pos = self.ifc.create_entity("IfcAxis2Placement3D", Location=pt)
            
            solid = self.ifc.create_entity("IfcExtrudedAreaSolid",
                SweptArea=rect_profile,
                Position=extrusion_pos,
                ExtrudedDirection=self.ifc.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
                Depth=float(size)
            )
            
            # 3. Create Representation
            shape_rep = self.ifc.create_entity("IfcShapeRepresentation",
                ContextOfItems=context,
                RepresentationIdentifier="Body",
                RepresentationType="SweptSolid",
                Items=[solid]
            )
            
            product_shape = self.ifc.create_entity("IfcProductDefinitionShape", Representations=[shape_rep])
            
            # 4. Create Proxy
            # Use unique GUID
            proxy = self.ifc.create_entity("IfcBuildingElementProxy", 
                GlobalId=ifcopenshell.guid.new(), 
                Name="HazardMarker"
            )
            proxy.Representation = product_shape
            
            # 5. Placement
            point = self.ifc.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y), float(z)))
            axis2placement = self.ifc.create_entity("IfcAxis2Placement3D", Location=point)
            placement = self.ifc.create_entity("IfcLocalPlacement", RelativePlacement=axis2placement)
            proxy.ObjectPlacement = placement
            
            # 6. Apply Style
            # Use 0.0 transparency for markers (solid opaque) to ensure maximum visibility
            style = self._create_surface_style(color, transparency=0.0) 
            if style:
                self._assign_style_to_element(proxy, style)
            
            # 7. Spatial Containment (CRITICAL FOR VISIBILITY)
            # Link proxy to the building so it appears in the spatial tree
            # Many viewers filter out elements not contained in the spatial structure
            try:
                # Try to find the building
                spatial_structure = None
                if self.ifc.by_type("IfcBuilding"):
                    spatial_structure = self.ifc.by_type("IfcBuilding")[0]
                elif self.ifc.by_type("IfcSite"):
                     spatial_structure = self.ifc.by_type("IfcSite")[0]
                     
                if spatial_structure:
                    # Check if a container relation already exists for this structure to avoid creating thousands of rels
                    # Ideally we should batch these, but for now we create one per marker or reuse if possible?
                    # Creating one RelContainedInSpatialStructure per element is valid but verbose.
                    # Let's create a new one to be safe and simple.
                    
                    self.ifc.create_entity(
                        "IfcRelContainedInSpatialStructure",
                        GlobalId=ifcopenshell.guid.new(),
                        RelatingStructure=spatial_structure,
                        RelatedElements=[proxy]
                    )
                    # logging.debug(f"Linked marker to spatial structure {spatial_structure.Name}")
                else:
                    logging.warning("No spatial structure (Building/Site) found to contain marker!")
                    
            except Exception as e_cont:
                logging.warning(f"Failed to link marker to spatial structure: {e_cont}")
                
            # logging.info(f"Created solid marker at ({x}, {y}, {z})")
            return proxy

        except Exception as e:
            logging.error(f"Error creating box marker: {e}")
            return None

    def get_coloring_statistics(self) -> Dict[str, Any]:
        """Get statistics about colored elements"""
        stats = {
            "total_colored_elements": len(self.colored_elements),
            "total_markers_created": len(self.created_markers),
            "hazard_type_breakdown": {},
            "severity_breakdown": {},
            "color_mapping": {}
        }

        # Count by hazard type and severity
        for elem_id, (hazard_type, severity, color) in self.color_mapping.items():
            stats["hazard_type_breakdown"][hazard_type] = \
                stats["hazard_type_breakdown"].get(hazard_type, 0) + 1
            stats["severity_breakdown"][severity] = \
                stats["severity_breakdown"].get(severity, 0) + 1

            # Store color mapping for report
            stats["color_mapping"][elem_id] = {
                "hazard_type": hazard_type,
                "severity": severity,
                "color_rgb": color
            }

        return stats
