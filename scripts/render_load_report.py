"""Render an honest PDF report from measured scripts/load_test.py JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from worldcup.config import ROOT


def render(results: dict, output: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    stages = results.get("stages", [])
    status = results.get("status", "unknown")
    if not stages and status != "preflight_failed":
        raise ValueError("No measured stages or recorded preflight failure found")
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(output), pagesize=(21 * cm, 29.7 * cm), rightMargin=2 * cm, leftMargin=2 * cm)
    story = [
        Paragraph("World Cup 2030 - Rapport de charge", styles["Title"]),
        Paragraph(f"Exécution du {escape(results.get('started_at', 'date inconnue'))} au {escape(results.get('finished_at', 'fin non enregistrée'))}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
        Paragraph("Environnement", styles["Heading2"]),
        Paragraph(f"Plateforme : {escape(str(results['host']['platform']))}; Python : {escape(str(results['host']['python']))}; CPU logiques : {results['host']['cpu_count']}.", styles["Normal"]),
        Paragraph(f"Kafka : {escape(results['configuration']['kafka_bootstrap_servers'])}; stream : {escape(results['configuration']['stream_id'])}; durée par palier : {results['configuration']['duration_seconds']} s.", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Protocole", styles["Heading2"]),
        Paragraph("Pour chaque palier, le producteur vise un débit fixe. Le compteur Redis mesure les événements dont le micro-lot Spark a terminé l'écriture. Le débit soutenu est ce compteur divisé par la durée du producteur ; le délai de vidange est observé séparément.", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Débit mesuré" if stages else "Mesures indisponibles", styles["Heading2"]),
    ]
    if stages:
        table_data = [["Cible/s", "Émis", "Traités au terme", "Traités après délai", "Traités/s soutenus", "Atteint"]]
        for stage in stages:
            table_data.append(
                [
                    f"{stage['rate_requested']:,}",
                    f"{stage['producer']['sent']:,}" if stage.get("producer") else "?",
                    f"{stage['processed_at_producer_finish']:,}",
                    f"{stage['processed_after_drain']:,}",
                    f"{stage['sustained_processed_per_second']:,.0f}",
                    "Oui" if stage["meets_requested_rate"] else "Non",
                ]
            )
        table = Table(table_data, repeatRows=1, hAlign="LEFT", colWidths=[2.2 * cm, 2.2 * cm, 3 * cm, 3 * cm, 3 * cm, 2 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b4e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#a7bec8")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4f5")]),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([table, Spacer(1, 0.5 * cm)])
    else:
        story.extend([Paragraph("Aucun palier de charge n'a été exécuté. Le précontrôle a échoué avant la production de messages.", styles["Normal"]), Spacer(1, 0.3 * cm)])
        story.append(Paragraph(f"Cause : {escape(results.get('preflight_error', 'non précisée'))}", styles["Normal"]))
    target = next((stage for stage in stages if stage["rate_requested"] == 50000), None)
    conclusion = "Cible 50 000/s non testée ; aucune performance n'est revendiquée." if target is None else (
        "Cible 50 000/s atteinte selon les compteurs du pipeline." if target["meets_requested_rate"] else "Cible 50 000/s non atteinte sur cet environnement."
    )
    story.extend([Paragraph("Conclusion", styles["Heading2"]), Paragraph(conclusion, styles["Normal"])])
    story.extend([Spacer(1, 0.3 * cm), Paragraph("Limites de mesure", styles["Heading2"])])
    for limitation in results.get("limitations", []):
        story.append(Paragraph(escape(limitation), styles["Normal"]))
    document.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JSON produced by scripts/load_test.py")
    parser.add_argument("--output", type=Path, default=ROOT / "load_testing_report.pdf")
    args = parser.parse_args()
    render(json.loads(args.results.read_text(encoding="utf-8")), args.output)
    print(args.output)


if __name__ == "__main__":
    main()
