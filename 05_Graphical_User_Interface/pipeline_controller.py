"""
Pipeline Controller for BIM Safety Analysis System
Orchestrates execution of all 4 phases programmatically
"""

import os
import sys
import json
import shutil
import re
import logging
import importlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable


class PipelineController:
    """Controls execution of all 4 phases of the BIM safety analysis pipeline"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.resolve()
        self.gui_dir = Path(__file__).parent.resolve()
        self.session_dir = None
        self.results = {}
        self.original_dir = Path.cwd()

        logging.info(f"Pipeline Controller initialized")
        logging.info(f"Root directory: {self.root_dir}")

    def create_session(self, ifc_file: Path) -> Path:
        """
        Create timestamped session directory

        Args:
            ifc_file: Path to IFC file

        Returns:
            Path to session directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.gui_dir / "outputs" / f"session_{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Copy IFC file to session
        session_ifc = session_dir / ifc_file.name
        shutil.copy(ifc_file, session_ifc)

        self.session_dir = session_dir
        logging.info(f"Session created: {session_dir}")

        # Initialize results dict
        self.results = {
            "session_dir": session_dir,
            "ifc_file": session_ifc,
            "ifc_filename": ifc_file.name
        }

        return session_dir

    def run_phase1(self, callback: Optional[Callable] = None) -> Dict:
        """
        Run Phase 1: Hazard Detection

        Args:
            callback: Optional progress callback function

        Returns:
            Dict with phase results
        """
        logging.info("="*60)
        logging.info("Starting Phase 1: Hazard Identification")
        logging.info("="*60)

        phase1_dir = self.root_dir / "01_Fall_Hazard_Identification"
        input_data_dir = self.root_dir / "input_data"
        output_dir = self.root_dir / "output_data/hazard_identification_results"
        ifc_file = self.results["ifc_file"]

        try:
            # Copy IFC file to Phase 1 directory
            input_ifc = input_data_dir / ifc_file.name
            shutil.copy(ifc_file, input_ifc)
            logging.info(f"Copied IFC to Phase 1: {input_ifc}")

            # Update config.py
            self._update_phase1_config(ifc_file.name)

            # Change to Phase 1 directory
            os.chdir(phase1_dir)
            logging.info(f"Changed directory to: {phase1_dir}")

            # Clear any previously imported modules
            for mod in ['detect_hazards', 'config']:
                if mod in sys.modules:
                    del sys.modules[mod]

            # Add to path and import
            if str(phase1_dir) not in sys.path:
                sys.path.insert(0, str(phase1_dir))

            if callback:
                callback(0.3, "Detecting hazards...")

            # Import and run detection
            import detect_hazards

            if callback:
                callback(0.5, "Running hazard detection...")

            # Call the main pipeline function
            detection_results = detect_hazards.run_pipeline()

            if not detection_results:
                raise Exception("Phase 1 detection returned no results")

            if callback:
                callback(0.8, "Reading results...")

            # Find latest output
            output_dir = self._find_latest_run(output_dir)

            if not output_dir:
                raise Exception("No output directory found after Phase 1 execution")

            # Read results
            hazards_file = output_dir / "hazards_detected.json"
            summary_file = output_dir / "run_summary.json"

            if not hazards_file.exists() or not summary_file.exists():
                raise Exception(f"Missing output files in {output_dir}")

            with open(summary_file) as f:
                summary = json.load(f)

            # Copy to session directory
            session_phase1 = self.session_dir / "phase1_outputs"
            if session_phase1.exists():
                shutil.rmtree(session_phase1)
            shutil.copytree(output_dir, session_phase1)

            logging.info(f"Phase 1 complete: {summary['statistics']['total_hazards']} hazards detected")

            result = {
                "success": True,
                "output_dir": session_phase1,
                "hazards_file": session_phase1 / "hazards_detected.json",
                "summary_file": session_phase1 / "run_summary.json",
                "hazard_count": summary["statistics"]["total_hazards"],
                "errors": []
            }

            self.results["phase1"] = result

            # Ensure llm_training_data.json exists in session directory
            self._ensure_phase1_llm_data(session_phase1)

            return result

        except Exception as e:
            logging.error(f"Phase 1 failed: {str(e)}")
            return {
                "success": False,
                "errors": [str(e)]
            }
        finally:
            os.chdir(self.original_dir)

    def run_phase2(self, callback: Optional[Callable] = None) -> Dict:
        """
        Run Phase 2: Hazard Visualization

        Returns:
            Dict with phase results
        """
        logging.info("="*60)
        logging.info("Starting Phase 2: Hazard Visualization")
        logging.info("="*60)

        phase2_dir = self.root_dir / "02_Fall_Hazard_Visualization"
        ifc_file = self.results["ifc_file"]
        hazards_file = self.results["phase1"]["hazards_file"]

        try:
            os.chdir(phase2_dir)

            # Add to path
            if str(phase2_dir) not in sys.path:
                sys.path.insert(0, str(phase2_dir))

            # Clear cached modules to avoid conflicts between phases
            if 'visualize_hazards' in sys.modules:
                del sys.modules['visualize_hazards']
            if 'config' in sys.modules:
                del sys.modules['config']
            if 'ifc_colorizer' in sys.modules:
                del sys.modules['ifc_colorizer']
            if 'report_generator' in sys.modules:
                del sys.modules['report_generator']

            if callback:
                callback(0.2, "Loading visualization module...")

            # Import visualization module
            from visualize_hazards import visualize_hazards

            # Create output directory
            output_dir = self.session_dir / "phase2_outputs"
            output_dir.mkdir(exist_ok=True)

            if callback:
                callback(0.4, "Visualizing hazards...")

            # Run visualization
            result = visualize_hazards(
                hazards_path=hazards_file,
                ifc_path=ifc_file,
                output_dir=output_dir
            )

            logging.info(f"Phase 2 complete: {result.get('colored_hazards', 0)} hazards visualized")

            # Convert Path objects to strings if needed
            if 'colored_ifc_path' in result and isinstance(result['colored_ifc_path'], Path):
                result['colored_ifc'] = result.pop('colored_ifc_path')

            result['output_dir'] = output_dir
            self.results["phase2"] = result

            # Ensure llm_training_data.json exists
            self._ensure_phase2_llm_data(output_dir, result)

            return result

        except Exception as e:
            logging.error(f"Phase 2 failed: {str(e)}")
            return {
                "success": False,
                "errors": [str(e)]
            }
        finally:
            os.chdir(self.original_dir)

    def run_phase3(self, callback: Optional[Callable] = None) -> Dict:
        """
        Run Phase 3: Guardrail Placement

        Returns:
            Dict with phase results
        """
        logging.info("="*60)
        logging.info("Starting Phase 3: Guardrail Placement")
        logging.info("="*60)

        phase3_dir = self.root_dir / "03_Fall_Hazard_Prevention_and_Control"
        output_dir = self.root_dir / "output_data/hazard_prevention_and_control_results"

        ifc_file = self.results["ifc_file"]

        try:
            # Copy IFC file
            phase3_ifc = phase3_dir / ifc_file.name
            shutil.copy(ifc_file, phase3_ifc)

            # Update config
            self._update_phase3_config(ifc_file.name)

            os.chdir(phase3_dir)
            logging.info(f"Changed to Phase 3 directory: {phase3_dir}")

            # Ensure phase3_dir is at the START of sys.path (remove if exists, then insert at 0)
            phase3_str = str(phase3_dir)
            if phase3_str in sys.path:
                sys.path.remove(phase3_str)
            sys.path.insert(0, phase3_str)

            # Clear ALL potentially conflicting cached modules
            modules_to_clear = ['place_guardrails', 'config', 'ifcopenshell', 'ifcopenshell.geom', 'ifcopenshell.guid']
            for mod in list(sys.modules.keys()):
                if mod in modules_to_clear or mod.startswith('ifcopenshell'):
                    # Skip ifcopenshell - it should stay loaded
                    if mod.startswith('ifcopenshell'):
                        continue
                    del sys.modules[mod]

            if callback:
                callback(0.3, "Placing guardrails...")

            logging.info("Importing place_guardrails module...")
            # Import module
            import place_guardrails

            if callback:
                callback(0.5, "Generating guardrails...")

            logging.info("Calling place_guardrails.main()...")
            # Call the main function
            try:
                exit_code = place_guardrails.main()
            except Exception as main_error:
                logging.error(f"place_guardrails.main() raised exception: {main_error}")
                import traceback
                logging.error(traceback.format_exc())
                raise

            if exit_code != 0:
                raise Exception("Phase 3 guardrail placement returned error")

            if callback:
                callback(0.8, "Reading results...")

            # Find output
            output_dir = self._find_latest_run(output_dir)

            if not output_dir:
                raise Exception("No output directory found after Phase 3 execution")

            # Read report
            report_file = output_dir / "report.json"
            if not report_file.exists():
                raise Exception(f"Missing report.json in {output_dir}")

            with open(report_file) as f:
                report = json.load(f)

            # Copy to session
            session_phase3 = self.session_dir / "phase3_outputs"
            if session_phase3.exists():
                shutil.rmtree(session_phase3)
            shutil.copytree(output_dir, session_phase3)

            logging.info(f"Phase 3 complete: {report['total_components']} guardrail components generated")

            result = {
                "success": True,
                "output_dir": session_phase3,
                "guardrail_ifc": session_phase3 / f"{ifc_file.stem}_UNIFIED_GUARDRAILS.ifc",
                "report_file": session_phase3 / "report.json",
                "component_count": report["total_components"],
                "errors": []
            }

            self.results["phase3"] = result

            # Ensure llm_training_data.json exists
            self._ensure_phase3_llm_data(session_phase3)

            return result

        except Exception as e:
            logging.error(f"Phase 3 failed: {str(e)}")
            return {
                "success": False,
                "errors": [str(e)]
            }
        finally:
            os.chdir(self.original_dir)

    def create_master_rag(self, callback: Optional[Callable] = None) -> Optional[Path]:
        """
        Create master RAG dataset from all phase outputs

        Returns:
            Path to master_rag_training_data.json or None if failed
        """
        logging.info("="*60)
        logging.info("Creating Master RAG Dataset")
        logging.info("="*60)

        try:
            # Read llm_training_data.json from each phase
            phase1_llm = self.session_dir / "phase1_outputs" / "llm_training_data.json"
            phase2_llm = self.session_dir / "phase2_outputs" / "llm_training_data.json"
            phase3_llm = self.session_dir / "phase3_outputs" / "llm_training_data.json"

            # Log which files exist
            logging.info(f"Checking for LLM training data files:")
            logging.info(f"  Phase 1: {phase1_llm.exists()} - {phase1_llm}")
            logging.info(f"  Phase 2: {phase2_llm.exists()} - {phase2_llm}")
            logging.info(f"  Phase 3: {phase3_llm.exists()} - {phase3_llm}")

            # Check which files are missing
            missing_files = []
            if not phase1_llm.exists():
                missing_files.append("Phase 1")
                # Log what files ARE in phase1_outputs
                phase1_dir = self.session_dir / "phase1_outputs"
                if phase1_dir.exists():
                    files = [f.name for f in phase1_dir.iterdir()]
                    logging.warning(f"Phase 1 outputs contains: {files}")
            if not phase2_llm.exists():
                missing_files.append("Phase 2")
                phase2_dir = self.session_dir / "phase2_outputs"
                if phase2_dir.exists():
                    files = [f.name for f in phase2_dir.iterdir()]
                    logging.warning(f"Phase 2 outputs contains: {files}")
            if not phase3_llm.exists():
                missing_files.append("Phase 3")
                phase3_dir = self.session_dir / "phase3_outputs"
                if phase3_dir.exists():
                    files = [f.name for f in phase3_dir.iterdir()]
                    logging.warning(f"Phase 3 outputs contains: {files}")

            if missing_files:
                logging.error(f"Missing llm_training_data.json files from: {', '.join(missing_files)}")
                logging.error("Creating simplified master RAG without missing phase data...")
                # Continue anyway with available data
                p1_data = {}
                p2_data = {}
                p3_data = {}

                if phase1_llm.exists():
                    with open(phase1_llm) as f:
                        p1_data = json.load(f)
                if phase2_llm.exists():
                    with open(phase2_llm) as f:
                        p2_data = json.load(f)
                if phase3_llm.exists():
                    with open(phase3_llm) as f:
                        p3_data = json.load(f)
            else:

                if callback:
                    callback(0.3, "Loading phase data...")

                with open(phase1_llm) as f:
                    p1_data = json.load(f)
                with open(phase2_llm) as f:
                    p2_data = json.load(f)
                with open(phase3_llm) as f:
                    p3_data = json.load(f)

            if callback:
                callback(0.6, "Creating master dataset...")

            # Create master document
            master_data = {
                "document_type": "BIM Safety Analysis - GUI Session",
                "generated_at": datetime.now().isoformat(),
                "session_id": self.session_dir.name,

                "project_overview": {
                    "name": "BIM Safety Analysis System",
                    "building_model": self.results["ifc_filename"],
                    "total_hazards": self.results["phase1"]["hazard_count"],
                    "guardrail_components": self.results["phase3"]["component_count"]
                },

                "workflow_summary": {
                    "phase_1": {
                        "name": "Hazard Detection",
                        "purpose": "Automated scanning of IFC models to identify construction safety hazards",
                        "output": f"{self.results['phase1']['hazard_count']} hazards detected",
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
                        "output": f"{self.results['phase3']['component_count']} guardrail components",
                        "key_technologies": ["Mesh topology extraction", "Wall-aware placement", "OSHA compliance algorithms"]
                    },
                    "phase_4": {
                        "name": "LLM Advisory",
                        "purpose": "Intelligent safety analysis and recommendations using RAG-enhanced LLM",
                        "technology": "OpenRouter API with DeepSeek model + sentence-transformers for RAG"
                    }
                },

                "phases": {
                    "phase_1": p1_data,
                    "phase_2": p2_data,
                    "phase_3": p3_data
                },

                "knowledge_base": self._get_knowledge_base(),

                "q_and_a_training_examples": self._get_qa_examples(),

                "file_outputs": {
                    "phase_1": {
                        "hazards_json": str(self.results["phase1"]["hazards_file"]),
                        "summary_json": str(self.results["phase1"]["summary_file"])
                    },
                    "phase_2": {
                        "colored_ifc": str(self.results["phase2"].get("colored_ifc", "")),
                        "report_json": str(self.session_dir / "phase2_outputs" / "visualization_report.json")
                    },
                    "phase_3": {
                        "guardrail_ifc": str(self.results["phase3"]["guardrail_ifc"]),
                        "report_json": str(self.results["phase3"]["report_file"])
                    }
                }
            }

            # Save to session directory
            master_file = self.session_dir / "master_rag_training_data.json"
            with open(master_file, 'w') as f:
                json.dump(master_data, f, indent=2)

            logging.info(f"Master RAG dataset created: {master_file}")
            logging.info(f"File size: {master_file.stat().st_size / 1024:.1f} KB")

            return master_file

        except Exception as e:
            logging.error(f"Failed to create master RAG: {str(e)}")
            return None

    def _get_knowledge_base(self) -> Dict:
        """Get knowledge base for RAG dataset"""
        return {
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
                "top_rail": "42 inches ± 3 inches (1100mm)",
                "mid_rail": "21 inches (550mm, halfway between top rail and platform)",
                "toe_board": "Minimum 3.5 inches (100mm)",
                "post_spacing": "Maximum 8 feet (2000mm)",
                "strength": "Must withstand 200 pounds force"
            }
        }

    def _get_qa_examples(self) -> list:
        """Get Q&A training examples"""
        hazard_count = self.results["phase1"]["hazard_count"]
        component_count = self.results["phase3"]["component_count"]

        return [
            {
                "question": f"How many hazards were detected in the {self.results['ifc_filename']} building model?",
                "answer": f"A total of {hazard_count} construction safety hazards were detected in this BIM model."
            },
            {
                "question": "What OSHA standards does the system follow?",
                "answer": "The system implements OSHA 1926.502 for fall protection systems, with guardrail top rail height of 1100mm (42 inches), mid rail at 550mm, and post spacing maximum of 2000mm."
            },
            {
                "question": "How many guardrail components were generated?",
                "answer": f"Phase 3 generated {component_count} guardrail components following OSHA-compliant dimensions."
            }
        ]

    def _update_phase1_config(self, ifc_filename: str):
        """Programmatically update Phase 1 config.py"""
        config_file = self.root_dir / "01_Fall_Hazard_Identification" / "config.py"

        with open(config_file, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # Replace IFC_FILENAME
        config_content = re.sub(
            r'IFC_FILENAME = ".*?"',
            f'IFC_FILENAME = "{ifc_filename}"',
            config_content
        )

        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)

        logging.info(f"Updated Phase 1 config: IFC_FILENAME = {ifc_filename}")

    def _update_phase3_config(self, ifc_filename: str):
        """Programmatically update Phase 3 config.py"""
        config_file = self.root_dir / "03_Fall_Hazard_Prevention_and_Control" / "config.py"

        with open(config_file, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # Update SOURCE_IFC_PATH to use local copy (IFC is copied to Phase 3 directory)
        ifc_path = ifc_filename  # Local file in Phase 3 directory
        config_content = re.sub(
            r'SOURCE_IFC_PATH = ".*?"',
            f'SOURCE_IFC_PATH = "{ifc_path}"',
            config_content
        )

        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)

        logging.info(f"Updated Phase 3 config: SOURCE_IFC_PATH = {ifc_path}")

    def _find_latest_run(self, output_base: Path) -> Optional[Path]:
        """Find most recent run_YYYYMMDD_HHMMSS directory"""
        if not output_base.exists():
            return None

        run_dirs = sorted(output_base.glob("run_*"))
        return run_dirs[-1] if run_dirs else None

    def get_session_summary(self) -> Dict:
        """Get summary of current session results"""
        if not self.results:
            return {}

        summary = {
            "session_dir": str(self.session_dir),
            "ifc_file": self.results.get("ifc_filename", ""),
            "phases_completed": []
        }

        if "phase1" in self.results and self.results["phase1"]["success"]:
            summary["phases_completed"].append("Phase 1: Hazard Detection")
            summary["hazard_count"] = self.results["phase1"]["hazard_count"]

        if "phase2" in self.results and self.results["phase2"]["success"]:
            summary["phases_completed"].append("Phase 2: Hazard Visualization")

        if "phase3" in self.results and self.results["phase3"]["success"]:
            summary["phases_completed"].append("Phase 3: Guardrail Placement")
            summary["component_count"] = self.results["phase3"]["component_count"]

        return summary

    def _ensure_phase1_llm_data(self, output_dir: Path):
        """Ensure Phase 1 has llm_training_data.json (copy if exists or skip)"""
        llm_file = output_dir / "llm_training_data.json"
        if llm_file.exists():
            logging.info("Phase 1 llm_training_data.json already exists")
        else:
            logging.warning("Phase 1 llm_training_data.json not found - will be created during master RAG")

    def _ensure_phase2_llm_data(self, output_dir: Path, result: Dict):
        """Create minimal Phase 2 llm_training_data.json if missing"""
        llm_file = output_dir / "llm_training_data.json"
        if not llm_file.exists():
            logging.info("Creating Phase 2 llm_training_data.json")
            llm_data = {
                "phase": "Phase 2: Hazard Visualization",
                "description": "Color-coded visualization of detected hazards in IFC model",
                "colored_hazards": result.get("colored_hazards", 0),
                "success_rate": result.get("success_rate", 0)
            }
            with open(llm_file, 'w') as f:
                json.dump(llm_data, f, indent=2)
            logging.info(f"Created {llm_file}")

    def _ensure_phase3_llm_data(self, output_dir: Path):
        """Create minimal Phase 3 llm_training_data.json if missing"""
        llm_file = output_dir / "llm_training_data.json"
        if not llm_file.exists():
            logging.info("Creating Phase 3 llm_training_data.json")
            report_file = output_dir / "report.json"
            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)
                llm_data = {
                    "phase": "Phase 3: Guardrail Placement",
                    "description": "OSHA-compliant guardrail generation for detected hazards",
                    "total_components": report.get("total_components", 0),
                    "guardrail_types": report.get("summary", {})
                }
            else:
                llm_data = {
                    "phase": "Phase 3: Guardrail Placement",
                    "description": "OSHA-compliant guardrail generation"
                }
            with open(llm_file, 'w') as f:
                json.dump(llm_data, f, indent=2)
            logging.info(f"Created {llm_file}")
