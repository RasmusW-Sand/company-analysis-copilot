from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
from models import CompanySnapshot
import io


# ── Fargepalett ──────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#0f2d4a")
BLUE    = colors.HexColor("#1a5f9e")
LIGHT   = colors.HexColor("#e8f0f7")
GREEN   = colors.HexColor("#065f46")
GREEN_BG= colors.HexColor("#d1fae5")
RED     = colors.HexColor("#991b1b")
RED_BG  = colors.HexColor("#fee2e2")
AMBER_BG= colors.HexColor("#fef3c7")
AMBER   = colors.HexColor("#92400e")
GRAY    = colors.HexColor("#6c757d")
LGRAY   = colors.HexColor("#f8f9fa")
BLACK   = colors.HexColor("#212529")


def generate_pdf(snapshot: CompanySnapshot) -> bytes:
    """
    Genererer en 1-side company snapshot PDF.
    Returnerer PDF som bytes — klar for Streamlit download-knapp.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8*cm,
        rightMargin=1.8*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = _build_styles()
    story  = []

    # ── Header ───────────────────────────────────────────────────────────────
    story += _header(snapshot, styles)
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY))
    story.append(Spacer(1, 0.3*cm))

    # ── Business description ──────────────────────────────────────────────────
    story.append(Paragraph("Business description", styles["section"]))
    story.append(Paragraph(
        snapshot.business_description or "N/A", styles["body"]
    ))
    story.append(Spacer(1, 0.4*cm))

    # ── To kolonner: nøkkeltall + geo ─────────────────────────────────────────
    story.append(_metrics_and_geo_table(snapshot, styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Inntektsdrivere + risikoer ────────────────────────────────────────────
    story.append(_drivers_and_risks_table(snapshot, styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Peer comparison ───────────────────────────────────────────────────────
    if snapshot.peer_multiples:
        story.append(Paragraph("Peer comparison", styles["section"]))
        story.append(_peer_table(snapshot, styles))
        story.append(Spacer(1, 0.4*cm))

    # ── Why interesting / not interesting ────────────────────────────────────
    story.append(_investment_view(snapshot, styles))
    story.append(Spacer(1, 0.3*cm))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        f"Generert {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        "Company Analysis Copilot · Kun til informasjonsformål",
        styles["footer"]
    ))

    doc.build(story)
    return buffer.getvalue()


# ── Byggeklosser ─────────────────────────────────────────────────────────────

def _header(snapshot: CompanySnapshot, styles: dict) -> list:
    """Selskapsnavn, ticker, og metadata i toppen."""
    ticker_str = f" ({snapshot.ticker})" if snapshot.ticker else ""
    hq_str     = snapshot.headquarters or ""
    founded_str = f"  ·  Est. {snapshot.founded}" if snapshot.founded else ""

    return [
        Paragraph(
            f"{snapshot.company_name}{ticker_str}",
            styles["title"]
        ),
        Paragraph(
            f"{hq_str}{founded_str}",
            styles["subtitle"]
        ),
    ]


def _metrics_and_geo_table(snapshot: CompanySnapshot, styles: dict) -> Table:

    def fmt_mnok(v):
        if v is None or v == 0: return "N/A"
        if v >= 1000: return f"{v/1000:,.1f} MRDNOK"
        return f"{v:,.0f} MNOK"

    def fmt_x(v):
        return f"{v:.1f}x" if v is not None else "N/A"

    def fmt_pct(v):
        return f"{v:.1f}%" if v is not None else "N/A"

    # Bygg én flat tabell med 4 kolonner: label | verdi | label | verdi
    geo = snapshot.geographic_exposure or {}
    geo_sorted = [
        (k, v) for k, v in
        sorted(geo.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]

    metrics = [
        ("Market cap",         fmt_mnok(snapshot.market_cap_mnok)),
        ("Omsetning TTM",      fmt_mnok(snapshot.revenue_ttm_mnok)),
        ("EV/EBITDA",          fmt_x(snapshot.ev_ebitda)),
        ("EBITDA-margin",      fmt_pct(snapshot.ebitda_margin)),
        ("Netto gjeld/EBITDA", fmt_x(snapshot.net_debt_ebitda)),
        ("CAGR 3y",            fmt_pct(snapshot.revenue_cagr_3y)),
    ]

    # Fyll opp korteste liste
    while len(geo_sorted) < len(metrics):
        geo_sorted.append(("", ""))
    while len(metrics) < len(geo_sorted):
        metrics.append(("", ""))

    # Header-rad
    rows = [[
        Paragraph("Nøkkeltall", styles["section"]),
        "",
        Paragraph("Geografisk eksponering", styles["section"]),
        "",
    ]]

    # Datarad per linje
    for (mlabel, mval), (glabel, gandel) in zip(metrics, geo_sorted):
        if isinstance(gandel, float) and gandel > 0:
            bar = "■" * int(gandel * 10) + "□" * (10 - int(gandel * 10))
            geo_val = f"{bar}  {gandel*100:.0f}%"
        else:
            geo_val = ""

        rows.append([
            Paragraph(mlabel, styles["metric_label"]) if mlabel else "",
            Paragraph(mval,   styles["metric_value"]) if mval   else "",
            Paragraph(glabel, styles["metric_label"]) if glabel else "",
            Paragraph(geo_val,styles["geo_bar"])      if geo_val else "",
        ])

    # Total bredde: 16cm — fordelt på 4 kolonner
    table = Table(rows, colWidths=[4.0*cm, 3.5*cm, 3.5*cm, 5.0*cm])
    table.setStyle(TableStyle([
        ("SPAN",          (0, 0), (1, 0)),
        ("SPAN",          (2, 0), (3, 0)),
        ("LINEBELOW",     (0, 0), (1, 0),  0.5, BLUE),
        ("LINEBELOW",     (2, 0), (3, 0),  0.5, BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LGRAY]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _drivers_and_risks_table(snapshot: CompanySnapshot, styles: dict) -> Table:
    """Inntektsdrivere til venstre, risikoer til høyre."""

    left_col = [Paragraph("Inntektsdrivere", styles["section"])]
    for item in (snapshot.revenue_drivers or []):
        left_col.append(Paragraph(f"• {item}", styles["bullet"]))

    right_col = [Paragraph("Nøkkelrisikoer", styles["section"])]
    for item in (snapshot.key_risks or []):
        right_col.append(Paragraph(f"• {item}", styles["bullet_risk"]))

    # Fyll opp korteste kolonne så de er like lange
    while len(left_col) < len(right_col):
        left_col.append(Spacer(1, 0.1*cm))
    while len(right_col) < len(left_col):
        right_col.append(Spacer(1, 0.1*cm))

    table = Table(
        [[left_col, right_col]],
        colWidths=[8.2*cm, 7.4*cm]
    )
    table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _peer_table(snapshot: CompanySnapshot, styles: dict) -> Table:
    """Peer comparison tabell med multippeldata."""

    header = [
        Paragraph("Ticker", styles["table_header"]),
        Paragraph("Navn", styles["table_header"]),
        Paragraph("EV/EBITDA", styles["table_header"]),
        Paragraph("EBITDA-margin", styles["table_header"]),
    ]

    rows = [header]

    # Selskapet selv øverst
    rows.append([
        Paragraph(snapshot.ticker or "—", styles["table_highlight"]),
        Paragraph(snapshot.company_name, styles["table_highlight"]),
        Paragraph(
            f"{snapshot.ev_ebitda:.1f}x" if snapshot.ev_ebitda else "N/A",
            styles["table_highlight"]
        ),
        Paragraph(
            f"{snapshot.ebitda_margin:.1f}%" if snapshot.ebitda_margin else "N/A",
            styles["table_highlight"]
        ),
    ])

    for p in snapshot.peer_multiples:
        rows.append([
            Paragraph(p.ticker, styles["table_cell"]),
            Paragraph(p.name or "—", styles["table_cell"]),
            Paragraph(
                f"{p.ev_ebitda:.1f}x" if p.ev_ebitda else "N/A",
                styles["table_cell"]
            ),
            Paragraph(
                f"{p.ebitda_margin:.1f}%" if p.ebitda_margin else "N/A",
                styles["table_cell"]
            ),
        ])

    table = Table(rows, colWidths=[2.5*cm, 6.5*cm, 3*cm, 3.5*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("BACKGROUND",    (0, 1), (-1, 1),  LIGHT),
        ("ROWBACKGROUNDS",(0, 2), (-1, -1), [colors.white, LGRAY]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, BLUE),
    ]))
    return table


def _investment_view(snapshot: CompanySnapshot, styles: dict) -> Table:
    """Why interesting / why not interesting side om side."""

    left_content = [
        Paragraph("Hvorfor interessant", styles["pro_header"]),
        Paragraph(snapshot.why_interesting or "N/A", styles["body"]),
    ]
    right_content = [
        Paragraph("Hvorfor ikke interessant", styles["con_header"]),
        Paragraph(snapshot.why_not_interesting or "N/A", styles["body"]),
    ]

    table = Table(
        [[left_content, right_content]],
        colWidths=[8.2*cm, 7.4*cm]
    )
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, 0), GREEN_BG),
        ("BACKGROUND",  (1, 0), (1, 0), RED_BG),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",(0, 0), (-1, -1), 10),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0,0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return table


# ── Styles ────────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "title",
            fontSize=18, fontName="Helvetica-Bold",
            textColor=NAVY, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontSize=9, fontName="Helvetica",
            textColor=GRAY, spaceAfter=4,
        ),
        "section": ParagraphStyle(
            "section",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=BLUE, spaceBefore=2, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=8, fontName="Helvetica",
            textColor=BLACK, leading=12,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            fontSize=8, fontName="Helvetica",
            textColor=GRAY,
        ),
        "metric_value": ParagraphStyle(
            "metric_value",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=BLACK, alignment=TA_RIGHT,
        ),
        "geo_bar": ParagraphStyle(
            "geo_bar",
            fontSize=7, fontName="Helvetica",
            textColor=BLUE,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontSize=8, fontName="Helvetica",
            textColor=BLACK, leading=12,
            leftIndent=6, spaceAfter=2,
        ),
        "bullet_risk": ParagraphStyle(
            "bullet_risk",
            fontSize=8, fontName="Helvetica",
            textColor=AMBER, leading=12,
            leftIndent=6, spaceAfter=2,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontSize=8, fontName="Helvetica",
            textColor=BLACK,
        ),
        "table_highlight": ParagraphStyle(
            "table_highlight",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=NAVY,
        ),
        "pro_header": ParagraphStyle(
            "pro_header",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=GREEN, spaceAfter=4,
        ),
        "con_header": ParagraphStyle(
            "con_header",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=RED, spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontSize=7, fontName="Helvetica",
            textColor=GRAY, alignment=TA_CENTER,
        ),
    }