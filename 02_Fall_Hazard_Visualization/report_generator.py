"""
Report Generator Module
Creates detailed reports of hazard visualization results
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class ReportGenerator:
    """Generates comprehensive reports for hazard visualization"""

    def __init__(self, config):
        """Initialize report generator with configuration"""
        self.config = config
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "source_ifc": "",
            "hazards_file": "",
            "total_hazards": 0,
            "colored_hazards": 0,
            "failed_hazards": 0,
            "hazard_details": [],
            "statistics": {},
            "limitations": []
        }

    def set_source_files(self, ifc_path: str, hazards_path: str):
        """Set source file paths"""
        self.report_data["source_ifc"] = ifc_path
        self.report_data["hazards_file"] = hazards_path

    def add_hazard_result(self, hazard: Dict[str, Any], success: bool,
                         colored_element_id: str = None, notes: str = ""):
        """
        Add a hazard coloring result to the report

        Args:
            hazard: Original hazard dictionary
            success: Whether coloring was successful
            colored_element_id: ID of colored element (if successful)
            notes: Additional notes about the coloring
        """
        hazard_entry = {
            "hazard_type": hazard.get("HazardType", "Unknown"),
            "severity": hazard.get("Severity", "Unknown"),
            "element_id": hazard.get("ElementID"),
            "element_type": hazard.get("ElementType"),
            "location": hazard.get("Location", {}),
            "success": success,
            "colored_element_id": colored_element_id,
            "notes": notes,
            "color": self._get_color_for_severity(hazard.get("Severity", "Unknown"))
        }

        self.report_data["hazard_details"].append(hazard_entry)
        self.report_data["total_hazards"] += 1

        if success:
            self.report_data["colored_hazards"] += 1
        else:
            self.report_data["failed_hazards"] += 1

    def set_statistics(self, stats: Dict[str, Any]):
        """Set coloring statistics from colorizer"""
        self.report_data["statistics"] = stats

    def add_limitation(self, limitation: str):
        """Add a limitation note"""
        if limitation not in self.report_data["limitations"]:
            self.report_data["limitations"].append(limitation)

    def generate_report(self, output_dir: Path) -> List[str]:
        """
        Generate report files

        Args:
            output_dir: Directory to save reports

        Returns:
            List of generated file paths
        """
        generated_files = []

        # Generate JSON report
        if self.config.REPORT_FORMAT in ["json", "both"]:
            json_path = output_dir / "visualization_report.json"
            self._generate_json_report(json_path)
            generated_files.append(str(json_path))

        # Generate text report
        if self.config.REPORT_FORMAT in ["txt", "both"]:
            txt_path = output_dir / "visualization_report.txt"
            self._generate_text_report(txt_path)
            generated_files.append(str(txt_path))

        return generated_files

    def _generate_json_report(self, output_path: Path):
        """Generate JSON format report"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.report_data, f, indent=2, ensure_ascii=False)

    def _generate_text_report(self, output_path: Path):
        """Generate human-readable text report"""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("PHASE 2 - HAZARD VISUALIZATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {self.report_data['timestamp']}")
        lines.append(f"Source IFC: {self.report_data['source_ifc']}")
        lines.append(f"Hazards File: {self.report_data['hazards_file']}")
        lines.append("")

        # Summary
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Hazards Detected: {self.report_data['total_hazards']}")
        lines.append(f"Successfully Colored: {self.report_data['colored_hazards']}")
        lines.append(f"Failed to Color: {self.report_data['failed_hazards']}")

        if self.report_data['total_hazards'] > 0:
            success_rate = (self.report_data['colored_hazards'] / self.report_data['total_hazards']) * 100
            lines.append(f"Success Rate: {success_rate:.1f}%")

        lines.append("")

        # Statistics
        if self.config.INCLUDE_STATISTICS and self.report_data['statistics']:
            lines.append("-" * 80)
            lines.append("STATISTICS")
            lines.append("-" * 80)

            stats = self.report_data['statistics']

            lines.append(f"Total Elements Colored: {stats.get('total_colored_elements', 0)}")
            lines.append(f"Markers Created: {stats.get('total_markers_created', 0)}")
            lines.append("")

            # Breakdown by hazard type
            if stats.get('hazard_type_breakdown'):
                lines.append("Colored Elements by Hazard Type:")
                for hazard_type, count in sorted(stats['hazard_type_breakdown'].items()):
                    lines.append(f"  - {hazard_type}: {count}")
                lines.append("")

            # Breakdown by severity
            if stats.get('severity_breakdown'):
                lines.append("Colored Elements by Severity:")
                severity_order = ["Critical", "High", "Medium", "Low"]
                for severity in severity_order:
                    count = stats['severity_breakdown'].get(severity, 0)
                    if count > 0:
                        color = self._get_color_for_severity(severity)
                        lines.append(f"  - {severity}: {count} (Color: RGB{color})")
                lines.append("")

        # Color Legend
        lines.append("-" * 80)
        lines.append("COLOR LEGEND")
        lines.append("-" * 80)
        for severity in ["Critical", "High", "Medium", "Low"]:
            color = self.config.SEVERITY_COLORS.get(severity)
            if color:
                rgb_255 = tuple(int(c * 255) for c in color)
                lines.append(f"{severity:10s} - RGB{color} (RGB255: {rgb_255})")
        lines.append("")

        # Summary table
        if self.config.GENERATE_SUMMARY_TABLE:
            lines.append("-" * 80)
            lines.append("COLORED HAZARDS SUMMARY")
            lines.append("-" * 80)
            lines.append(f"{'Hazard Type':<25} {'Severity':<12} {'Element ID':<15} {'Status':<10}")
            lines.append("-" * 80)

            for detail in self.report_data['hazard_details']:
                if detail['success']:
                    hazard_type = detail['hazard_type'][:24]
                    severity = detail['severity'][:11]
                    elem_id = str(detail['colored_element_id'] or detail['element_id'] or 'N/A')[:14]
                    status = "[OK] Colored"

                    lines.append(f"{hazard_type:<25} {severity:<12} {elem_id:<15} {status:<10}")

            lines.append("")

        # Detailed element information
        if self.config.INCLUDE_ELEMENT_DETAILS:
            lines.append("-" * 80)
            lines.append("DETAILED HAZARD INFORMATION")
            lines.append("-" * 80)

            for i, detail in enumerate(self.report_data['hazard_details'], 1):
                lines.append(f"\n[{i}] {detail['hazard_type']} - {detail['severity']}")
                lines.append(f"    Element Type: {detail.get('element_type', 'Unknown')}")
                lines.append(f"    Element ID: {detail.get('element_id', 'N/A')}")

                loc = detail.get('location', {})
                if loc:
                    lines.append(f"    Location: X={loc.get('X', 0):.2f}, Y={loc.get('Y', 0):.2f}, Z={loc.get('Z', 0):.2f}")

                lines.append(f"    Status: {'[OK] Successfully Colored' if detail['success'] else '[FAILED] Failed to Color'}")

                if detail.get('colored_element_id'):
                    lines.append(f"    Colored Element: {detail['colored_element_id']}")

                if detail.get('notes'):
                    lines.append(f"    Notes: {detail['notes']}")

                color = detail.get('color')
                if color:
                    rgb_255 = tuple(int(c * 255) for c in color)
                    lines.append(f"    Applied Color: RGB{color} (RGB255: {rgb_255})")

            lines.append("")

        # Limitations
        if self.report_data['limitations']:
            lines.append("-" * 80)
            lines.append("LIMITATIONS AND NOTES")
            lines.append("-" * 80)
            for limitation in self.report_data['limitations']:
                lines.append(f"- {limitation}")
            lines.append("")

        # Technical details
        lines.append("-" * 80)
        lines.append("TECHNICAL INFORMATION")
        lines.append("-" * 80)
        lines.append("IFC Color Coding Method: Element-based styling using IfcSurfaceStyle")
        lines.append(f"Highlight Mode: {self.config.HIGHLIGHT_MODE}")
        lines.append(f"Opening Markers: {'Enabled' if self.config.CREATE_OPENING_MARKERS else 'Disabled'}")
        lines.append(f"Color Transparency: {self.config.COLOR_TRANSPARENCY}")
        lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def _get_color_for_severity(self, severity: str) -> tuple:
        """Get RGB color tuple for a severity level"""
        return self.config.SEVERITY_COLORS.get(severity, self.config.SEVERITY_COLORS["Unknown"])

    def print_summary(self):
        """Print a quick summary to console"""
        print("\n" + "=" * 60)
        print("VISUALIZATION SUMMARY")
        print("=" * 60)
        print(f"Total Hazards: {self.report_data['total_hazards']}")
        print(f"Successfully Colored: {self.report_data['colored_hazards']}")
        print(f"Failed: {self.report_data['failed_hazards']}")

        if self.report_data['total_hazards'] > 0:
            success_rate = (self.report_data['colored_hazards'] / self.report_data['total_hazards']) * 100
            print(f"Success Rate: {success_rate:.1f}%")

        print("=" * 60 + "\n")
