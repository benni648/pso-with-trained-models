"""
Report Service — generates traffic analysis reports.

Supports multiple formats: JSON, CSV, PDF.
Reports are stored in the reports/ directory.
"""

import os
import csv
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class ReportGenerator:
    """
    Generates and manages traffic analysis reports.

    Usage:
        generator = ReportGenerator()
        path = generator.generate_traffic_report(
            title="Weekly Report",
            predictions=[],
            optimizations=[],
            statistics={},
            format="json"
        )
    """

    def __init__(self):
        """Initialize report generator."""
        try:
            from config.config import config
            self.reports_dir = config.REPORTS_DIR
        except (ImportError, AttributeError):
            self.reports_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "reports"
            )

        os.makedirs(self.reports_dir, exist_ok=True)
        logger.info(f"ReportGenerator initialized — reports dir: {self.reports_dir}")

    def generate_traffic_report(
        self,
        title: str = "Traffic Report",
        predictions: List = None,
        optimizations: List = None,
        statistics: Dict = None,
        format: str = "json",
    ) -> str:
        """
        Generate a traffic analysis report.

        Parameters
        ----------
        title : str
            Report title.
        predictions : list
            List of prediction records.
        optimizations : list
            List of optimization records.
        statistics : dict
            Summary statistics.
        format : str
            Output format: "json", "csv", or "pdf".

        Returns
        -------
        str
            Path to the generated report file.
        """
        predictions = predictions or []
        optimizations = optimizations or []
        statistics = statistics or {}

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace(" ", "_").replace("/", "_")[:50]
        filename = f"{safe_title}_{timestamp}.{format}"
        filepath = os.path.join(self.reports_dir, filename)

        report_data = {
            "title": title,
            "generated_at": datetime.utcnow().isoformat(),
            "format": format,
            "statistics": statistics,
            "predictions_count": len(predictions),
            "optimizations_count": len(optimizations),
            "predictions": predictions[:100],  # Limit to 100 records
            "optimizations": optimizations[:100],
        }

        if format == "json":
            self._write_json(filepath, report_data)
        elif format == "csv":
            self._write_csv(filepath, report_data)
        elif format == "pdf":
            self._write_pdf(filepath, report_data)
        else:
            # Default to JSON
            filepath = filepath.rsplit(".", 1)[0] + ".json"
            self._write_json(filepath, report_data)

        logger.info(f"Report generated: {filepath}")
        return filepath

    def get_recent_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent reports from the reports directory.

        Parameters
        ----------
        limit : int
            Maximum number of reports to return.

        Returns
        -------
        list
            List of report metadata dicts.
        """
        reports = []

        if not os.path.exists(self.reports_dir):
            return reports

        files = sorted(
            os.listdir(self.reports_dir),
            key=lambda f: os.path.getmtime(os.path.join(self.reports_dir, f)),
            reverse=True,
        )

        for filename in files[:limit]:
            filepath = os.path.join(self.reports_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                reports.append({
                    "filename": filename,
                    "size_bytes": stat.st_size,
                    "format": filename.rsplit(".", 1)[-1] if "." in filename else "unknown",
                    "generated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return reports

    def _write_json(self, filepath: str, data: Dict):
        """Write report as JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _write_csv(self, filepath: str, data: Dict):
        """Write report as CSV."""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header section
            writer.writerow(["Title", data["title"]])
            writer.writerow(["Generated", data["generated_at"]])
            writer.writerow([])

            # Predictions
            if data["predictions"]:
                writer.writerow(["=== Predictions ==="])
                if isinstance(data["predictions"][0], dict):
                    headers = list(data["predictions"][0].keys())
                    writer.writerow(headers)
                    for pred in data["predictions"]:
                        writer.writerow([pred.get(h, "") for h in headers])
                writer.writerow([])

            # Optimizations
            if data["optimizations"]:
                writer.writerow(["=== Optimizations ==="])
                if isinstance(data["optimizations"][0], dict):
                    headers = list(data["optimizations"][0].keys())
                    writer.writerow(headers)
                    for opt in data["optimizations"]:
                        writer.writerow([opt.get(h, "") for h in headers])

    def _write_pdf(self, filepath: str, data: Dict):
        """Write report as PDF using reportlab."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(filepath, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Title
            story.append(Paragraph(data["title"], styles["Title"]))
            story.append(Spacer(1, 12))

            # Metadata
            story.append(Paragraph(f"Generated: {data['generated_at']}", styles["Normal"]))
            story.append(Paragraph(f"Predictions: {data['predictions_count']}", styles["Normal"]))
            story.append(Paragraph(f"Optimizations: {data['optimizations_count']}", styles["Normal"]))
            story.append(Spacer(1, 12))

            # Statistics
            if data["statistics"]:
                story.append(Paragraph("Statistics", styles["Heading2"]))
                for key, value in data["statistics"].items():
                    story.append(Paragraph(f"{key}: {value}", styles["Normal"]))

            doc.build(story)

        except ImportError:
            logger.warning("reportlab not installed — falling back to JSON for PDF report")
            json_path = filepath.rsplit(".", 1)[0] + ".json"
            self._write_json(json_path, data)
