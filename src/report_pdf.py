"""
report_pdf.py - build the PDF report from the output of match_and_reconcile().

Run this file directly to produce demo_report.pdf from made-up data
(no confidential documents involved):

    python report_pdf.py
"""

from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

STATUS_COLORS = {
    "À VÉRIFIER": "#975a16",
    "NON-CONFORME": "#9b2c2c",
    "MANQUANT": "#c53030",
    "AJOUTÉ": "#c05621",
}
HEADER_BG = colors.HexColor("#edf2f7")
GRID = colors.HexColor("#cbd5e0")


def _location_text(ref) -> str:
    """'file.pdf<br/>p.1 (412.5, 318.0)' or '-' when there is no location."""
    if not ref:
        return "-"
    parts = []
    if ref.get("fichier"):
        parts.append(escape(str(ref["fichier"])))
    page, x, y = ref.get("page"), ref.get("x"), ref.get("y")
    if x is not None and y is not None:
        where = f"({x:.1f}, {y:.1f})"
        parts.append(f"p.{page} {where}" if page is not None else where)
    return "<br/>".join(parts) or "-"


def generate_pdf_report(reconciled_data: dict, output_pdf_path: str, coverage=None, associations=None) -> None:
    doc = SimpleDocTemplate(
        output_pdf_path, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36,
        title="Structural Reinforcement Verification Report",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=16,
                                 leading=20, textColor=colors.HexColor("#1a365d"))
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#4a5568'))
        canvas.drawString(36, 20, 'L2C - Verification des armatures')
        canvas.drawRightString(letter[0]-36, 20, f'Page {document.page}')
        canvas.restoreState()

    story = []
    story.append(Paragraph("Structural Reinforcement Verification Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now():%Y-%m-%d %H:%M}. "
                           "This report flags differences for review; the final decision "
                           "remains the engineer's.", small))
    story.append(Spacer(1, 12))

    if coverage is not None:
        annotations = sum(p['annotation_count'] for p in coverage)
        associated = sum(p['associated_count'] for p in coverage)
        unresolved = sum(p['unresolved_count'] for p in coverage)
        ocr_skipped = sum(p.get('ocr_skipped', False) for p in coverage)
        story.append(Paragraph(
            f"Extraction coverage: {len(coverage)} pages, {annotations} reinforcement annotations, "
            f"{associated} associated and {unresolved} unresolved. "
            f"{ocr_skipped} OCR candidate pages were not processed with OCR. "
            "Automatic association is partial. Zero discrepancies does not establish conformity. "
            "Unmatched elements require review before absence is confirmed.", small))
        story.append(Spacer(1, 10))

    if not reconciled_data:
        story.append(Paragraph("No data to report.", styles["Normal"]))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return

    # Summary by plan sheet 
    story.append(Paragraph("1. Summary by Plan Sheet", styles["Heading2"]))
    story.append(Spacer(1, 5))

    summary = [["Plan Sheet", "Conformities", "Non-Conformities", "of which Missing", "of which Added", "To review"]]
    totals = {"conforme": 0, "non_conforme": 0, "manquant": 0, "ajoute": 0, "a_verifier": 0}
    for sheet, stats in reconciled_data.items():
        summary.append([sheet, str(stats["conforme"]), str(stats["non_conforme"]),
                        str(stats["manquant"]), str(stats["ajoute"]), str(stats.get("a_verifier", 0))])
        for name in totals:
            totals[name] += stats.get(name, 0)
    summary.append(["TOTAL", str(totals["conforme"]), str(totals["non_conforme"]),
                    str(totals["manquant"]), str(totals["ajoute"]), str(totals["a_verifier"])])

    summary_table = Table([[Paragraph(escape(str(cell)), small) for cell in row] for row in summary],
                          colWidths=[80, 80, 100, 100, 100, 80], repeatRows=1)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 18))

    # Detailed discrepancy log, one table per sheet 
    for index, (sheet, stats) in enumerate(reconciled_data.items()):
        story.append(PageBreak())
        if index == 0:
            story.append(Paragraph("2. Detailed Discrepancy Log", styles["Heading2"]))
        story.append(Paragraph(f"Sheet {escape(str(sheet))}", styles["Heading3"]))
        story.append(Paragraph(
            f"Conformities: {stats['conforme']} | Non-conformities: {stats['non_conforme']} | "
            f"To review: {stats.get('a_verifier', 0)}", small))
        story.append(Spacer(1, 8))

        items = stats["discrepancies"]
        if not items:
            message = "No discrepancies detected."
            if coverage is not None and not stats['conforme']:
                message = "No verified element comparison available for this sheet. Review extraction coverage."
            story.append(Paragraph(message, styles["Normal"]))
            continue

        rows = [[Paragraph(label, small) for label in
                 ["Element", "Status", "Plan location", "Shop location", "Discrepancy details"]]]
        for item in items:
            color = STATUS_COLORS.get(item["status"], "#000000")
            issues = item.get("issues") or [item.get("detail", "")]
            rows.append([
                Paragraph(f"{escape(str(item['element']))}<br/>({escape(str(item['type']))})", small),
                Paragraph(f'<font color="{color}"><b>{escape(item["status"])}</b></font>', small),
                Paragraph(_location_text(item.get("plan")), small),
                Paragraph(_location_text(item.get("shop")), small),
                Paragraph("<br/>".join(escape(str(i)) for i in issues), small),
            ])

        table =Table(rows, colWidths=[90, 85, 85, 85, 195], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

    if coverage is not None:
        story.append(PageBreak())
        story.append(Paragraph("3. Page coverage and unresolved associations", styles['Heading2']))
        rows = [[Paragraph(label, small) for label in
                 ['Document / sheet', 'Page', 'Annotations', 'Associated', 'Unresolved', 'Text method']]]
        for p in coverage:
            rows.append([Paragraph(escape(f"{p['fichier']} / {p['feuillet']}"), small),
                         str(p['page']), str(p['annotation_count']), str(p['associated_count']),
                         str(p['unresolved_count']),
                         Paragraph('OCR skipped' if p.get('ocr_skipped') else p['text_method'], small)])
        table = Table(rows, colWidths=[235, 35, 65, 65, 70, 70], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), .5, GRID),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(table)
        unresolved = [e for e in associations or [] if e['status'] != 'associated']
        if unresolved:
            story.append(Spacer(1, 10))
            story.append(Paragraph('Unresolved annotation references (first 100; full list in associations.json)', small))
            rows = [[Paragraph(label, small) for label in ['Source location', 'Status', 'Annotation ID']]]
            for e in unresolved[:100]:
                rows.append([Paragraph(escape(f"{e['fichier']}, p.{e['page']} ({e['x']:.1f}, {e['y']:.1f})"), small),
                             Paragraph(escape(e['status']), small),
                             Paragraph(escape(e['annotation_id']), small)])
            table = Table(rows, colWidths=[290, 80, 170], repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), .5, GRID),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.append(table)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    from match import match_and_reconcile

    def bar(mark, dia, qty, length=None, spacing=None):
        return {"repere": mark, "diametre": dia, "quantite": qty,
                "espacement_mm": spacing, "longueur_mm": length}

    def rec(source, element, bars, x, y, page=1):
        return {"id": f"S-500_{element}_{source}", "source": source,
                "fichier": f"demo_{source}.pdf", "feuillet": "S-500", "page": page,
                "x": x, "y": y, "type_element": "colonne", "element": element,
                "armature": bars}

    demo_records = [
        rec("plan", "C-12", [bar("C12-1", "25M", 8, 3600)], 412.5, 318.0),
        rec("shop_drawing", "C-12", [bar("C12-1", "25M", 6, 3600)], 120.0, 85.5, page=2),
        rec("plan", "C-13", [bar("C13-1", "20M", 4, 3000)], 450.0, 320.0),
        rec("shop_drawing", "C 13", [bar("C13-1", "20M", 4, 3000)], 160.0, 90.0, page=2),
        rec("plan", "C-14", [bar("C14-1", "25M", 8, 3600)], 480.0, 322.0),
        rec("shop_drawing", "C-99", [bar("C99-1", "15M", 4, 2500)], 200.0, 95.0, page=2),
    ]

    generate_pdf_report(match_and_reconcile(demo_records), "demo_report.pdf")
    print("Wrote demo_report.pdf")
