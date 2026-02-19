#!/usr/bin/env python3
"""
create_master_rag.py
Creates a master RAG training dataset by combining outputs from all phases.
Auto-detects the latest run directories.
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def find_latest_run(base_path: Path, pattern: str = "run_*") -> Path:
    """Find the most recent run directory"""
    if not base_path.exists():
        return None
    run_dirs = sorted(base_path.glob(pattern))
    return run_dirs[-1] if run_dirs else None


def main():
    print("=" * 60)
    print("Creating Master RAG Training Dataset")
    print("=" * 60)

    # Auto-detect latest run directories
    phase1_base = Path("Phase_1_Hazard_Detection/hazard_results")
    phase2_base = Path("Phase_2_Hazard_Visualization/visualization_results")
    phase3_base = Path("Phase_3_Guardrail_Placement/outputs")

    phase1_run = find_latest_run(phase1_base)
    phase2_run = find_latest_run(phase2_base)
    phase3_run = find_latest_run(phase3_base)

    # Check if all runs exist
    missing = []
    if not phase1_run:
        missing.append("Phase 1 (run Phase_1_Hazard_Detection/detect_hazards.py first)")
    if not phase2_run:
        missing.append("Phase 2 (run Phase_2_Hazard_Visualization/visualize_hazards.py first)")
    if not phase3_run:
        missing.append("Phase 3 (run Phase_3_Guardrail_Placement/place_guardrails.py first)")

    if missing:
        print("\n[ERROR] Missing phase outputs:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease run all phases before creating master RAG dataset.")
        sys.exit(1)

    print(f"\nFound latest runs:")
    print(f"  Phase 1: {phase1_run}")
    print(f"  Phase 2: {phase2_run}")
    print(f"  Phase 3: {phase3_run}")

    # Load phase data
    phase1_llm = phase1_run / "llm_training_data.json"
    phase2_llm = phase2_run / "llm_training_data.json"
    phase3_llm = phase3_run / "llm_training_data.json"

    # Check for llm_training_data.json files
    missing_llm = []
    if not phase1_llm.exists():
        missing_llm.append(f"Phase 1: {phase1_llm}")
    if not phase2_llm.exists():
        missing_llm.append(f"Phase 2: {phase2_llm}")
    if not phase3_llm.exists():
        missing_llm.append(f"Phase 3: {phase3_llm}")

    if missing_llm:
        print("\n[WARNING] Missing llm_training_data.json files:")
        for m in missing_llm:
            print(f"  - {m}")
        print("\nContinuing with available data...")

    # Load available data
    phase1_data = {}
    phase2_data = {}
    phase3_data = {}

    if phase1_llm.exists():
        with open(phase1_llm, 'r', encoding='utf-8') as f:
            phase1_data = json.load(f)
        print(f"  Loaded Phase 1 data")

    if phase2_llm.exists():
        with open(phase2_llm, 'r', encoding='utf-8') as f:
            phase2_data = json.load(f)
        print(f"  Loaded Phase 2 data")

    if phase3_llm.exists():
        with open(phase3_llm, 'r', encoding='utf-8') as f:
            phase3_data = json.load(f)
        print(f"  Loaded Phase 3 data")

    # Load summary data for statistics
    hazard_count = 0
    component_count = 0
    building_model = "Unknown"

    summary_file = phase1_run / "run_summary.json"
    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
            hazard_count = summary.get('statistics', {}).get('total_hazards', 0)
            building_model = summary.get('ifc_file', 'Unknown')

    report_file = phase3_run / "report.json"
    if report_file.exists():
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
            component_count = report.get('total_components', 0)

    # Create master RAG training document
    master_rag_data = {
        "document_type": "BIM Safety Analysis System - Complete RAG Training Dataset",
        "generated_at": datetime.now().isoformat(),
        "project_overview": {
            "name": "4-Phase BIM Safety Analysis System",
            "purpose": "Automated detection, visualization, and mitigation of construction safety hazards in IFC building models",
            "building_model": building_model,
            "total_hazards": hazard_count,
            "total_guardrails": component_count,
            "regulatory_framework": ["OSHA 1926.502", "JGJ80-2016 (China)", "HKLD (Hong Kong)", "GB10000-88 (China)"]
        },
        "workflow_summary": {
            "phase_1": {
                "name": "Hazard Detection",
                "purpose": "Automated scanning of IFC models to identify construction safety hazards",
                "output": f"{hazard_count} hazards detected",
                "key_technologies": ["ifcopenshell", "NumPy spatial analysis", "Geometry extraction"]
            },
            "phase_2": {
                "name": "Hazard Visualization",
                "purpose": "Color-code detected hazards in IFC models for visual inspection",
                "output": f"Colored IFC file with visualized hazards",
                "key_technologies": ["IFC presentation styles", "3D marker placement", "Element color coding"]
            },
            "phase_3": {
                "name": "Guardrail Placement",
                "purpose": "Automatically generate OSHA-compliant guardrails for detected hazards",
                "output": f"{component_count} guardrail components",
                "key_technologies": ["SciPy convex hull", "Wall-aware placement", "OSHA compliance algorithms"]
            },
            "phase_4": {
                "name": "LLM Advisory",
                "purpose": "Intelligent safety analysis and recommendations using RAG-enhanced LLM",
                "technology": "OpenRouter API with DeepSeek model + sentence-transformers for RAG"
            }
        },
        "phases": {
            "phase_1": phase1_data,
            "phase_2": phase2_data,
            "phase_3": phase3_data
        },
        "knowledge_base": {
            "hazard_types_explained": {
                "FallFromHeight": {
                    "definition": "Risk of falling from elevated work areas above 2000mm (2m)",
                    "threshold": "2000mm",
                    "regulation": "OSHA 1926.501",
                    "common_locations": ["Slabs without guardrails", "Unprotected floor edges", "Elevated platforms"]
                },
                "UnprotectedSidesAndEdges": {
                    "definition": "Unprotected perimeter edges of floors/slabs above 1800mm",
                    "threshold": "1800mm",
                    "regulation": "OSHA 1926.502",
                    "common_locations": ["Floor slab perimeters", "Roof edges", "Mezzanines"]
                },
                "FloorOpening": {
                    "definition": "Holes or voids in floors larger than 500mm",
                    "threshold": "500mm diameter",
                    "regulation": "OSHA 1926.502(i)",
                    "common_locations": ["Stairs openings", "Elevator shafts", "Mechanical penetrations"]
                },
                "WallOpening": {
                    "definition": "Holes in walls at elevated heights",
                    "threshold": "500mm at height > 1800mm",
                    "regulation": "OSHA 1926.502",
                    "common_locations": ["Window openings", "Doorways to exterior", "Mechanical penetrations"]
                },
                "Stairway": {
                    "definition": "Stairs without adequate railings or protection",
                    "threshold": "760mm (30 inches) rise",
                    "regulation": "OSHA 1926.1052",
                    "common_locations": ["Stair flights", "Access stairs", "Temporary stairs"]
                }
            },
            "osha_guardrail_requirements": {
                "top_rail": "42 inches +/- 3 inches (1100mm)",
                "mid_rail": "21 inches (550mm, halfway between top rail and platform)",
                "toe_board": "Minimum 3.5 inches (100mm)",
                "post_spacing": "Maximum 8 feet (2000mm)",
                "strength": "Must withstand 200 pounds force"
            }
        },
        "q_and_a_training_examples": [
            {
                "question": f"How many hazards were detected in the {building_model} building model?",
                "answer": f"A total of {hazard_count} construction safety hazards were detected in this BIM model."
            },
            {
                "question": "What OSHA standards does the system follow?",
                "answer": "The system implements OSHA 1926.502 for fall protection systems, with guardrail top rail height of 1100mm (42 inches), mid rail at 550mm, and post spacing maximum of 2000mm. It also follows OSHA 1926.501 for fall hazard thresholds (2000mm for fall from height)."
            },
            {
                "question": "How does Phase 3 avoid placing guardrails where walls already exist?",
                "answer": "Phase 3 uses wall-aware exclusion with a 500mm adjacency tolerance. It detects existing walls near slab edges and prevents guardrail placement where walls already provide adequate protection, avoiding unnecessary clipping and collisions."
            },
            {
                "question": "What colors are used to visualize different hazard types in Phase 2?",
                "answer": "Phase 2 uses a color-coding scheme: Red for FallFromHeight and Stairway hazards (Critical), Yellow for UnprotectedSidesAndEdges (Critical), Orange for FloorOpening and RoofOpening (Critical), and Magenta for WallOpening (Critical)."
            },
            {
                "question": "How many guardrail components were generated?",
                "answer": f"Phase 3 generated {component_count} guardrail components following OSHA-compliant dimensions."
            }
        ],
        "file_outputs": {
            "phase_1": {
                "hazards_json": str(phase1_run / "hazards_detected.json"),
                "summary_json": str(phase1_run / "run_summary.json"),
                "llm_data": str(phase1_llm)
            },
            "phase_2": {
                "report_json": str(phase2_run / "visualization_report.json"),
                "llm_data": str(phase2_llm)
            },
            "phase_3": {
                "report_json": str(phase3_run / "report.json"),
                "llm_data": str(phase3_llm)
            }
        }
    }

    # Save master RAG document
    output_dir = Path("Phase_4_LLM_Advisory/llm_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    master_file = output_dir / "master_rag_training_data.json"

    with open(master_file, 'w', encoding='utf-8') as f:
        json.dump(master_rag_data, f, indent=2)

    print(f"\n[OK] Created Master RAG Training Data: {master_file}")
    print(f"  - Total data size: {len(json.dumps(master_rag_data)):,} characters")
    print(f"  - Hazards included: {hazard_count}")
    print(f"  - Guardrails included: {component_count}")
    print(f"  - Q&A examples: {len(master_rag_data['q_and_a_training_examples'])}")


if __name__ == "__main__":
    main()
