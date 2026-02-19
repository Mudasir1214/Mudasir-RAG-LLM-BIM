#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        PHASE 2 - HAZARD VISUALIZATION                        ║
║                  Color-codes detected hazards in IFC files                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

QUICK START:
    python visualize_hazards.py

CONFIGURE FILES (edit config.py):
    1. HAZARDS_JSON_PATH = path to hazards_detected.json from Phase 1
    2. SOURCE_IFC_PATH = path to your IFC building model

    ⚠️  IMPORTANT: Use the SAME IFC file that Phase 1 used for detection!

COMMAND LINE OPTIONS:
    python visualize_hazards.py --hazards path/to/hazards.json --ifc path/to/file.ifc
    python visualize_hazards.py --verbose  # Debug mode
"""

import os
import sys
import json
import logging
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from glob import glob

# Add parent directory to path to import from Phase 1/2 if needed
sys.path.insert(0, str(Path(__file__).parent))
project_root_path = Path(__file__).resolve().parents[1]

try:
    import ifcopenshell
except ImportError:
    print("ERROR: ifcopenshell not installed!")
    print("Install with: pip install ifcopenshell")
    sys.exit(1)

# Import local modules
import config
from ifc_colorizer import IfcColorizer
from report_generator import ReportGenerator


def setup_logging():
    """Setup logging configuration"""
    log_level = logging.DEBUG if config.VERBOSE else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def find_latest_hazards_file(pattern: str = None) -> Path:
    """
    Find the most recent hazards_detected.json file

    Args:
        pattern: Glob pattern to search (from config if None)

    Returns:
        Path to hazards file
    """
    if pattern is None:
        pattern = config.HAZARDS_JSON_PATH

    matches = []

    # If pattern is set, try to find it
    if pattern:
        # Expand pattern
        full_pattern = str(project_root_path / pattern)
        matches = glob(full_pattern)
    
    # If no matches found, try alternative locations
    if not matches:    
        # Try alternative locations
        alt_patterns = [
            "/output_data/hazard_identification_results/**/hazards_detected.json",
            "/01_Fall_Hazard_Identification/hazard_identification_results/**/hazards_detected.json",
            "/hazard_identification_results/**/hazards_detected.json",
            "/hazards_detected.json",
        ]

        for alt_pattern in alt_patterns:
            alt_pattern = os.path.join(str(project_root_path), alt_pattern.lstrip("/"))

            matches = glob(alt_pattern, recursive=True)
            if matches:
                break

    if not matches:
        raise FileNotFoundError(
            f"Could not find hazards_detected.json.\n"
            f"Please run Phase 1 first or specify the path with --hazards"
        )

    # Get most recent file
    latest = max(matches, key=os.path.getmtime)
    return Path(latest)


def load_hazards(hazards_path: Path) -> list:
    """
    Load hazards from JSON file

    Args:
        hazards_path: Path to hazards_detected.json

    Returns:
        List of hazard dictionaries
    """
    logging.info(f"Loading hazards from: {hazards_path}")

    with open(hazards_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle different JSON structures
    if isinstance(data, list):
        hazards = data
    elif isinstance(data, dict):
        if 'hazards' in data:
            hazards = data['hazards']
        elif 'detected_hazards' in data:
            hazards = data['detected_hazards']
        else:
            # Might be a single hazard
            hazards = [data]
    else:
        raise ValueError(f"Unexpected hazards file format: {type(data)}")

    logging.info(f"Loaded {len(hazards)} hazards")
    return hazards


def load_ifc_file(ifc_path: Path) -> ifcopenshell.file:
    """
    Load IFC file

    Args:
        ifc_path: Path to IFC file

    Returns:
        Loaded IFC file object
    """
    logging.info(f"Loading IFC file: {ifc_path}")

    if not ifc_path.exists():
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")

    ifc_file = ifcopenshell.open(str(ifc_path))
    logging.info(f"Loaded IFC file - Schema: {ifc_file.schema}")

    return ifc_file


def create_output_directory() -> Path:
    """Create timestamped output directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = project_root_path / config.OUTPUT_FOLDER / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Output directory: {output_dir}")
    return output_dir


def save_colored_ifc(ifc_file: ifcopenshell.file, output_dir: Path, original_name: str) -> Path:
    """
    Save the colored IFC file

    Args:
        ifc_file: Modified IFC file
        output_dir: Output directory
        original_name: Original IFC filename

    Returns:
        Path to saved file
    """
    # Create output filename
    base_name = Path(original_name).stem
    output_path = output_dir / f"{base_name}_colored.ifc"

    logging.info(f"Saving colored IFC to: {output_path}")

    # Save IFC file
    ifc_file.write(str(output_path))

    logging.info(f"Saved successfully: {output_path}")
    return output_path


def visualize_hazards(hazards_path: Path, ifc_path: Path, output_dir: Path) -> dict:
    """
    Main visualization function

    Args:
        hazards_path: Path to hazards JSON file
        ifc_path: Path to IFC file
        output_dir: Output directory

    Returns:
        Dictionary with results
    """
    results = {
        "success": False,
        "colored_ifc_path": None,
        "report_paths": [],
        "statistics": {},
        "errors": []
    }

    try:
        # Load hazards
        hazards = load_hazards(hazards_path)

        if not hazards:
            logging.warning("No hazards found in file!")
            results["errors"].append("No hazards found in input file")
            return results

        # Load IFC file
        ifc_file = load_ifc_file(ifc_path)

        # Create backup if configured
        if config.CREATE_BACKUP:
            backup_path = output_dir / f"{ifc_path.name}.backup"
            shutil.copy2(ifc_path, backup_path)
            logging.info(f"Created backup: {backup_path}")

        # Initialize colorizer
        colorizer = IfcColorizer(ifc_file, config)

        # Initialize report generator
        report_gen = ReportGenerator(config)
        report_gen.set_source_files(str(ifc_path), str(hazards_path))

        # Add known limitations
        report_gen.add_limitation(
            "IFC coloring is element-based: entire elements are colored, not specific edges or sub-regions"
        )
        report_gen.add_limitation(
            "Openings (voids) are complex to color directly; markers may be created instead"
        )
        report_gen.add_limitation(
            "Some IFC viewers may not display colors correctly - recommend using viewers like "
            "Solibri, BIMvision, or FreeCAD"
        )

        # Process each hazard
        logging.info(f"\nProcessing {len(hazards)} hazards...")
        print("\nColoring hazards:")
        print("-" * 60)

        for i, hazard in enumerate(hazards, 1):
            # Handle different JSON formats
            hazard_type = hazard.get("HazardType") or hazard.get("SpecificHazard", "Unknown")
            severity = hazard.get("Severity", "Unknown")
            element_id = hazard.get("ElementID", "N/A")

            # Try ElementContext if no direct ElementID
            if element_id == "N/A" and "ElementContext" in hazard:
                ctx = hazard["ElementContext"]
                
                # Check for direct ElementID in context
                if "ElementID" in ctx and ctx["ElementID"]:
                    element_id = ctx["ElementID"]
                # Legacy: Check for Opening key
                elif "Opening" in ctx:
                    element_id = ctx["Opening"]

            print(f"[{i}/{len(hazards)}] {hazard_type} ({severity}) - Element: {element_id}")

            # Color the hazard
            success = colorizer.color_hazard(hazard)

            # Record result
            colored_elem = element_id if success else None
            notes = "Successfully colored" if success else "Could not locate element in IFC"
            report_gen.add_hazard_result(hazard, success, colored_elem, notes)

            if not success:
                logging.warning(f"  ⚠ Could not color hazard: {hazard_type}")
                results["errors"].append(f"Failed to color {hazard_type} at element {element_id}")

        print("-" * 60)

        # Get statistics
        stats = colorizer.get_coloring_statistics()
        report_gen.set_statistics(stats)
        results["statistics"] = stats

        # Save colored IFC
        colored_ifc_path = save_colored_ifc(ifc_file, output_dir, ifc_path.name)
        results["colored_ifc_path"] = str(colored_ifc_path)

        # Generate reports
        report_paths = report_gen.generate_report(output_dir)
        results["report_paths"] = report_paths

        # Print summary
        report_gen.print_summary()

        results["success"] = True

        return results

    except Exception as e:
        logging.error(f"Error during visualization: {e}", exc_info=True)
        results["errors"].append(str(e))
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Phase 2 - Visualize detected hazards in IFC files with color coding"
    )

    parser.add_argument(
        "--hazards",
        type=str,
        help="Path to hazards_detected.json file (auto-detected if not specified)"
    )

    parser.add_argument(
        "--ifc",
        type=str,
        help="Path to source IFC file (uses config default if not specified)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output directory (uses config default if not specified)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        config.VERBOSE = True
    setup_logging()

    print("\n" + "=" * 70)
    print("PHASE 2 - HAZARD VISUALIZATION")
    print("=" * 70)
    print("Color-codes detected hazards based on severity")
    print()

    # Show configured paths from config.py
    print("Configured paths (from config.py):")
    print(f"  Hazards: {config.HAZARDS_JSON_PATH}")
    print(f"  IFC:     {config.SOURCE_IFC_PATH}")
    print()

    try:
        # Determine hazards file path
        if args.hazards:
            hazards_path = Path(args.hazards)
            if not hazards_path.exists():
                print(f"ERROR: Hazards file not found: {hazards_path}")
                return 1
        else:
            try:
                hazards_path = find_latest_hazards_file()
                print(f"[OK] Auto-detected hazards file: {hazards_path.name}")
            except FileNotFoundError as e:
                print(f"ERROR: {e}")
                return 1

        # Determine IFC file path
        if args.ifc:
            ifc_path = Path(args.ifc)
        elif config.SOURCE_IFC_PATH:
            ifc_path = project_root_path / config.SOURCE_IFC_PATH
        else: # Try to find IFC in input_data/ if not specified
            input_dir = project_root_path / "input_data"  # Default input directory
            ifc_files = list(input_dir.glob("*.ifc"))
            if not ifc_files:
                    print("ERROR: No IFC file found in input_data/")
                    print("Please specify IFC file with --ifc option or set SOURCE_IFC_PATH in config.py")
                    return 1

            # pick latest IFC instead of hardcoded name
            ifc_path = max(ifc_files, key=os.path.getmtime)
        print(f"[OK] Using IFC file: {ifc_path.name}")

        # Create output directory
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = create_output_directory()

        print(f"[OK] Output directory: {output_dir}")
        print()

        # Run visualization
        results = visualize_hazards(hazards_path, ifc_path, output_dir)

        # Print results
        print("\n" + "=" * 70)
        if results["success"]:
            print("[SUCCESS] VISUALIZATION COMPLETED SUCCESSFULLY")
            print("=" * 70)
            print(f"\nColored IFC file: {results['colored_ifc_path']}")
            print(f"\nReports generated:")
            for report_path in results["report_paths"]:
                print(f"  - {report_path}")

            print(f"\nStatistics:")
            stats = results.get("statistics", {})
            print(f"  - Total elements colored: {stats.get('total_colored_elements', 0)}")
            print(f"  - Markers created: {stats.get('total_markers_created', 0)}")

            if stats.get('severity_breakdown'):
                print(f"\n  Colored by severity:")
                for severity in ["Critical", "High", "Medium", "Low"]:
                    count = stats['severity_breakdown'].get(severity, 0)
                    if count > 0:
                        print(f"    {severity}: {count}")

        else:
            print("[FAILED] VISUALIZATION FAILED")
            print("=" * 70)
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  - {error}")

        print("\n" + "=" * 70)

        # Print viewing instructions
        print("\nVIEWING INSTRUCTIONS:")
        print("-" * 70)
        print("To view the colored IFC file, use one of these viewers:")
        print("  - Solibri Viewer (Recommended)")
        print("  - BIMvision")
        print("  - FreeCAD")
        print("  - IFC.js Online Viewer (https://ifcjs.github.io/web-ifc-viewer/example/example)")
        print()
        print("Note: Some viewers may not display colors. Ensure 'Show Styles' or")
        print("'Show Presentation' is enabled in your viewer settings.")
        print("-" * 70)
        print()

        return 0 if results["success"] else 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
