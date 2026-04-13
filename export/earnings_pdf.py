"""
Earnings Intelligence Brief — 3-siders ReportLab PDF.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# Gjenbruk fargepalett fra eksisterende pdf_export.py
from export.pdf_export import (
    NAVY, BLUE, LIGHT, GREEN, GREEN_BG,
    RED, RED_BG, AMBER_BG, AMBER, GRAY, LGRAY, BLACK,
)

WHITE = colors.white
PAGE_W = A4[0]


# ── Sidetall-footer (callback for alle sider) ─────────────────────────────────

def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY)
    page_num = canvas.getPageNumber()
    canvas.drawString(1.8 * cm, 0.9 * cm, f"Side {page_num}")
    canvas.drawCentredString(
        PAGE_W / 2, 0.9 * cm,
        "Earnings Intelligence Brief — Company Analysis Copilot",
    )
    canvas.drawRightString(
        PAGE_W - 1.8 * cm, 0.9 * cm,
        datetime.now().strftime("%d.%m.%Y"),
    )
    canvas.restoreState()


# ── Hoved-funksjon ────────────────────────────────────────────────────────────

def generate_earnings_pdf(ticker: str, data: dict, briefing: dict) -> bytes:
    """
    Genererer 3-siders earnings briefing PDF.
    Returnerer PDF som bytes.
    Krasjer ikke på manglende data — viser 'N/A' / 'Data ikke tilgjengelig'.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,   # plass til footer
    )

    styles = _build_styles()
    story  = []

    # ── SIDE 1: Executive Brief ───────────────────────────────────────────────
    story += _page1(ticker, data, briefing, styles)

    # ── SIDE 2: Analyse ───────────────────────────────────────────────────────
    story.append(PageBreak())
    story += _page2(briefing, data, styles)

    # ── SIDE 3: M&A-perspektiv og analytiker-oversikt ─────────────────────────
    story.append(PageBreak())
    story += _page3(briefing, data, styles)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


# ── Side 1 ────────────────────────────────────────────────────────────────────

def _page1(ticker: str, data: dict, briefing: dict, styles: dict) -> list:
    out = []
    company = data.get("company_name") or ticker

    # ── Header-boks (NAVY bakgrunn, hvit tekst) ───────────────────────────────
    report_date = data.get("next_earnings") or "Ukjent dato"
    now_str     = datetime.now().strftime("%d.%m.%Y %H:%M")

    header_data = [
        [Paragraph(f"{company} ({ticker})", styles["header_title"])],
        [Paragraph("Earnings Preview", styles["header_sub"])],
        [Paragraph(
            f"Rapporterer: {report_date} &nbsp;&nbsp;·&nbsp;&nbsp; Generert: {now_str}",
            styles["header_meta"],
        )],
    ]
    header_table = Table(header_data, colWidths=[PAGE_W - 3.6 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    out.append(header_table)
    out.append(Spacer(1, 0.4 * cm))

    # ── Executive Summary-boks ────────────────────────────────────────────────
    summary = briefing.get("executive_summary") or "Data ikke tilgjengelig"
    out.append(Paragraph("Executive Summary", styles["section"]))
    summary_table = Table(
        [[Paragraph(summary, styles["body"])]],
        colWidths=[PAGE_W - 3.6 * cm],
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("BOX",           (0, 0), (-1, -1), 0.5, BLUE),
    ]))
    out.append(summary_table)
    out.append(Spacer(1, 0.4 * cm))

    # ── Konsensus-rad (4 metric-kort) ─────────────────────────────────────────
    cv        = briefing.get("consensus_view") or {}
    sentiment = (cv.get("sentiment") or "neutral").lower()
    sent_bg   = GREEN_BG if "bull" in sentiment else (RED_BG if "bear" in sentiment else AMBER_BG)
    sent_fg   = GREEN    if "bull" in sentiment else (RED    if "bear" in sentiment else AMBER)

    rev_est = cv.get("revenue_estimate") or "N/A"
    eps_est = cv.get("eps_estimate")     or "N/A"

    pt       = data.get("price_targets") or {}
    mean_tgt = f"{pt['mean']:.2f}" if pt.get("mean") else "N/A"
    currency = data.get("currency", "")

    col_w = (PAGE_W - 3.6 * cm) / 4

    consensus_data = [[
        _metric_cell("Omsetningsestimat", rev_est,          styles, WHITE),
        _metric_cell("EPS-estimat",       eps_est,          styles, WHITE),
        _metric_cell(f"Kursmål ({currency})", mean_tgt,     styles, WHITE),
        _metric_cell("Sentiment",         sentiment.capitalize(), styles, sent_bg, sent_fg),
    ]]
    consensus_table = Table(consensus_data, colWidths=[col_w] * 4)
    consensus_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, GRAY),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, LGRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    out.append(Paragraph("Analytiker-konsensus", styles["section"]))
    out.append(consensus_table)
    out.append(Spacer(1, 0.4 * cm))

    # ── Kursprestasjon ────────────────────────────────────────────────────────
    r30 = data.get("price_30d_return")
    r90 = data.get("price_90d_return")

    def _ret_str(v):
        if v is None:
            return "N/A"
        arrow = "▲" if v >= 0 else "▼"
        return f"{arrow} {abs(v):.1f}%"

    out.append(Paragraph("Kursprestasjon", styles["section"]))
    perf_data = [[
        _metric_cell("30 dager", _ret_str(r30), styles, GREEN_BG if (r30 or 0) >= 0 else RED_BG),
        _metric_cell("90 dager", _ret_str(r90), styles, GREEN_BG if (r90 or 0) >= 0 else RED_BG),
    ]]
    perf_table = Table(perf_data, colWidths=[(PAGE_W - 3.6 * cm) / 2] * 2)
    perf_table.setStyle(TableStyle([
        ("BOX",       (0, 0), (-1, -1), 0.5, GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LGRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    out.append(perf_table)

    # ── Key concern ───────────────────────────────────────────────────────────
    key_concern = cv.get("key_concern")
    if key_concern:
        out.append(Spacer(1, 0.3 * cm))
        out.append(Paragraph("Hovedbekymring blant analytikere", styles["section"]))
        out.append(Paragraph(key_concern, styles["body"]))

    # ── Kilder konsultert (web search) ────────────────────────────────────────
    sources = briefing.get("sources_consulted")
    if sources:
        out.append(Spacer(1, 0.3 * cm))
        sources_text = "  ·  ".join(str(s) for s in sources if s)
        out.append(Paragraph(
            f"Kilder konsultert: {sources_text}",
            styles["sources"],
        ))

    return out


# ── Side 2 ────────────────────────────────────────────────────────────────────

def _page2(briefing: dict, data: dict, styles: dict) -> list:
    out = []

    # ── Beat/Miss-historikk ───────────────────────────────────────────────────
    out.append(Paragraph("Historisk beat/miss — siste 4 kvartaler", styles["section"]))
    history = data.get("earnings_history") or []

    if history:
        header = [
            Paragraph("Kvartal",       styles["table_header"]),
            Paragraph("EPS est.",      styles["table_header"]),
            Paragraph("EPS faktisk",   styles["table_header"]),
            Paragraph("Avvik %",       styles["table_header"]),
            Paragraph("Beat/Miss",     styles["table_header"]),
        ]
        rows = [header]
        row_colors = []
        for h in history:
            eps_e = h.get("eps_estimate")
            eps_a = h.get("eps_actual")
            beat  = (eps_a or 0) > (eps_e or 0)
            surp  = h.get("surprise_pct")
            row_colors.append(GREEN_BG if beat else RED_BG)
            rows.append([
                Paragraph(h.get("quarter") or "?",    styles["table_cell"]),
                Paragraph(_fmt_v(eps_e),               styles["table_cell"]),
                Paragraph(_fmt_v(eps_a),               styles["table_cell"]),
                Paragraph(_fmt_v(surp),                styles["table_cell"]),
                Paragraph("Beat ✓" if beat else "Miss ✗", styles["table_cell"]),
            ])
        col_w = (PAGE_W - 3.6 * cm) / 5
        hist_table = Table(rows, colWidths=[col_w] * 5)
        style_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, BLUE),
        ]
        for i, bg in enumerate(row_colors, start=1):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        hist_table.setStyle(TableStyle(style_cmds))
        out.append(hist_table)
    else:
        out.append(Paragraph("Beat/miss-historikk ikke tilgjengelig for denne tickeren.", styles["na"]))

    out.append(Spacer(1, 0.4 * cm))

    # ── Historisk finansiell trend ────────────────────────────────────────────
    hp = briefing.get("historical_performance") or {}
    beat_rate = hp.get("beat_rate")
    trend     = hp.get("trend")
    lq_sum    = hp.get("last_quarter_summary")

    if any([beat_rate, trend, lq_sum]):
        out.append(Paragraph("Historisk prestasjon", styles["section"]))
        if beat_rate:
            out.append(Paragraph(f"Beat-rate: {beat_rate}", styles["body"]))
        if trend:
            out.append(Paragraph(f"Veksttend: {trend}", styles["body"]))
        if lq_sum:
            out.append(Paragraph(f"Forrige kvartal: {lq_sum}", styles["body"]))
        out.append(Spacer(1, 0.3 * cm))

    # ── Hva å se etter ────────────────────────────────────────────────────────
    out.append(Paragraph("Hva å se etter i rapporten", styles["section"]))
    watch = briefing.get("what_to_watch") or ["Data ikke tilgjengelig"]
    markers = ["①", "②", "③", "④", "⑤"]
    for i, item in enumerate(watch):
        marker = markers[i] if i < len(markers) else f"{i+1}."
        out.append(Paragraph(f"{marker}  {item}", styles["numbered"]))
        out.append(Spacer(1, 0.1 * cm))
    out.append(Spacer(1, 0.3 * cm))

    # ── Nøkkelrisikoer ────────────────────────────────────────────────────────
    out.append(Paragraph("Nøkkelrisikoer", styles["section"]))
    risks = briefing.get("key_risks") or ["Data ikke tilgjengelig"]
    for risk in risks:
        risk_table = Table(
            [[Paragraph(f"⚠  {risk}", styles["risk_text"])]],
            colWidths=[PAGE_W - 3.6 * cm],
        )
        risk_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), AMBER_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ]))
        out.append(risk_table)
        out.append(Spacer(1, 0.15 * cm))
    out.append(Spacer(1, 0.3 * cm))

    # ── Spørsmål til ledelsen ─────────────────────────────────────────────────
    out.append(Paragraph("Spørsmål til ledelsen", styles["section"]))
    questions = briefing.get("questions_for_management") or ["Data ikke tilgjengelig"]
    for i, q in enumerate(questions, 1):
        out.append(Paragraph(f"{i}.  {q}", styles["question"]))
        out.append(Spacer(1, 0.1 * cm))

    return out


# ── Side 3 ────────────────────────────────────────────────────────────────────

def _page3(briefing: dict, data: dict, styles: dict) -> list:
    out = []

    # ── M&A Angle ─────────────────────────────────────────────────────────────
    out.append(Paragraph("M&A-perspektiv", styles["section"]))
    ma_text = briefing.get("ma_angle") or "Data ikke tilgjengelig"
    ma_table = Table(
        [[Paragraph(ma_text, styles["body"])]],
        colWidths=[PAGE_W - 3.6 * cm],
    )
    ma_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
        ("BOX",           (0, 0), (-1, -1), 1.0, NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    out.append(ma_table)
    out.append(Spacer(1, 0.5 * cm))

    # ── Analytiker-anbefalinger ───────────────────────────────────────────────
    out.append(Paragraph("Analytiker-anbefalinger (siste 5)", styles["section"]))
    recs = data.get("recommendations") or []

    if recs:
        header = [
            Paragraph("Dato",         styles["table_header"]),
            Paragraph("Firma",        styles["table_header"]),
            Paragraph("Anbefaling",   styles["table_header"]),
            Paragraph("Kursmål",      styles["table_header"]),
        ]
        col_ws = [2.5 * cm, 5.5 * cm, 4.0 * cm, 3.0 * cm]
        rows = [header]
        row_colors = []
        for r in recs:
            grade  = (r.get("to_grade") or r.get("action") or "").lower()
            action = (r.get("action") or "").lower()
            is_pos = any(k in grade or k in action for k in ("buy", "outperform", "upgrade", "overweight", "positive"))
            is_neg = any(k in grade or k in action for k in ("sell", "underperform", "downgrade", "underweight", "negative"))
            row_colors.append(GREEN_BG if is_pos else (RED_BG if is_neg else LGRAY))
            rows.append([
                Paragraph(str(r.get("date") or "")[:10],   styles["table_cell"]),
                Paragraph(str(r.get("firm") or "—"),        styles["table_cell"]),
                Paragraph(str(r.get("to_grade") or r.get("action") or "—"), styles["table_cell"]),
                Paragraph(str(r.get("price_target") or "—"), styles["table_cell"]),
            ])
        rec_table = Table(rows, colWidths=col_ws)
        style_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, BLUE),
        ]
        for i, bg in enumerate(row_colors, start=1):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        rec_table.setStyle(TableStyle(style_cmds))
        out.append(rec_table)
    else:
        out.append(Paragraph("Analytiker-anbefalinger ikke tilgjengelig for denne tickeren.", styles["na"]))

    out.append(Spacer(1, 0.5 * cm))
    out.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    out.append(Spacer(1, 0.2 * cm))
    out.append(Paragraph(
        "Dette dokumentet er generert automatisk og er kun til informasjonsformål. "
        "Det er ikke finansiell rådgivning.",
        styles["disclaimer"],
    ))

    return out


# ── Helpers ───────────────────────────────────────────────────────────────────

def _metric_cell(label: str, value: str, styles: dict, bg=None, fg=None) -> list:
    """Returnerer en nøstet liste for én metric-celle."""
    val_style = styles["metric_value"]
    if fg:
        val_style = ParagraphStyle(
            "metric_value_colored",
            parent=val_style,
            textColor=fg,
        )
    cell = [
        Paragraph(label, styles["metric_label"]),
        Paragraph(str(value), val_style),
    ]
    inner = Table([[c] for c in cell])
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg or WHITE),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    return inner


def _fmt_v(v) -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


# ── Styles ────────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    return {
        "header_title": ParagraphStyle(
            "header_title",
            fontSize=16, fontName="Helvetica-Bold",
            textColor=WHITE, spaceAfter=4,
        ),
        "header_sub": ParagraphStyle(
            "header_sub",
            fontSize=11, fontName="Helvetica",
            textColor=colors.HexColor("#b0c4de"), spaceAfter=4,
        ),
        "header_meta": ParagraphStyle(
            "header_meta",
            fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#8aa8c8"),
        ),
        "section": ParagraphStyle(
            "section",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=BLUE, spaceBefore=4, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=8, fontName="Helvetica",
            textColor=BLACK, leading=12,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            fontSize=7, fontName="Helvetica",
            textColor=GRAY, alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "metric_value",
            fontSize=10, fontName="Helvetica-Bold",
            textColor=BLACK, alignment=TA_CENTER,
        ),
        "numbered": ParagraphStyle(
            "numbered",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=NAVY, leading=13, leftIndent=4,
        ),
        "question": ParagraphStyle(
            "question",
            fontSize=8, fontName="Helvetica-Oblique",
            textColor=BLACK, leading=12, leftIndent=10,
        ),
        "risk_text": ParagraphStyle(
            "risk_text",
            fontSize=8, fontName="Helvetica",
            textColor=AMBER, leading=12,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=WHITE,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontSize=8, fontName="Helvetica",
            textColor=BLACK,
        ),
        "na": ParagraphStyle(
            "na",
            fontSize=8, fontName="Helvetica-Oblique",
            textColor=GRAY,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            fontSize=7, fontName="Helvetica",
            textColor=GRAY, alignment=TA_CENTER,
        ),
        "sources": ParagraphStyle(
            "sources",
            fontSize=7, fontName="Helvetica-Oblique",
            textColor=GRAY, leading=10,
        ),
    }
