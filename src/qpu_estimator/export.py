"""Export utilities for QPU-Estimator reports."""

import csv
import io
from typing import Any

from .models import EstimationReport


class ReportExporter:
    """Export estimation reports to various formats."""

    @staticmethod
    def to_latex_table(reports: list[EstimationReport], caption: str = "QPU Estimation Results") -> str:
        """Generate a LaTeX table from estimation reports."""
        if not reports:
            return "% No reports to export"

        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{" + caption + r"}",
            r"\begin{tabular}{lcccccc}",
            r"\toprule",
            r"Backend & Depth & Time (ms) & Shots & Fidelity & Credits & SWAPs \\",
            r"\midrule",
        ]

        for report in reports:
            lines.append(
                f"{report.backend_name} & "
                f"{report.transpiled_depth} & "
                f"{report.estimated_execution_time_ms:.3f} & "
                f"{report.optimal_shots} & "
                f"{report.estimated_fidelity:.4f} & "
                f"{report.estimated_credits:.4f} & "
                f"{report.swap_count} \\\\"
            )

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])

        return "\n".join(lines)

    @staticmethod
    def to_csv(reports: list[EstimationReport]) -> str:
        """Generate CSV from estimation reports."""
        if not reports:
            return ""

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "backend", "qubits", "original_depth", "transpiled_depth",
            "execution_time_ms", "shots", "fidelity", "credits", "swaps",
        ])

        for report in reports:
            writer.writerow([
                report.backend_name,
                report.circuit_profile.num_qubits,
                report.circuit_profile.depth,
                report.transpiled_depth,
                f"{report.estimated_execution_time_ms:.6f}",
                report.optimal_shots,
                f"{report.estimated_fidelity:.6f}",
                f"{report.estimated_credits:.6f}",
                report.swap_count,
            ])

        return output.getvalue()

    @staticmethod
    def to_markdown(reports: list[EstimationReport]) -> str:
        """Generate Markdown table from estimation reports."""
        if not reports:
            return "_No reports to export_"

        lines = [
            "| Backend | Depth | Time (ms) | Shots | Fidelity | Credits | SWAPs |",
            "|---------|-------|-----------|-------|----------|---------|-------|",
        ]

        for report in reports:
            lines.append(
                f"| {report.backend_name} | "
                f"{report.transpiled_depth} | "
                f"{report.estimated_execution_time_ms:.3f} | "
                f"{report.optimal_shots} | "
                f"{report.estimated_fidelity:.4f} | "
                f"{report.estimated_credits:.4f} | "
                f"{report.swap_count} |"
            )

        return "\n".join(lines)
