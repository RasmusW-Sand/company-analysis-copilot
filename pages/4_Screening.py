import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from agents.screening_agent import (
    screen_universe, enrich_candidates, rank_by_ma_fit,
    fetch_dynamic_universe, _fetch_raw_universe,
)

st.set_page_config(
    page_title="Deal Screening — Company Analysis Copilot",
    page_icon="🔎",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-label { font-size: 12px; color: #6c757d; margin-bottom: 4px; }
    .metric-value { font-size: 22px; font-weight: 600; color: #212529; }
    .tag {
        display: inline-block;
        background: #e9ecef;
        border-radius: 4px;
        padding: 2px 10px;
        margin: 3px;
        font-size: 13px;
    }
    .pro { background: #d1fae5; color: #065f46; }
    .con { background: #fee2e2; color: #991b1b; }
    .risk { background: #fef3c7; color: #92400e; }
</style>
""", unsafe_allow_html=True)


# ── Signal-badge helper ───────────────────────────────────────────────────────

_BADGES: dict[str, tuple[str, str, str]] = {
    "lav_gjeld":        ("Lav gjeld",         "#d1fae5", "#065f46"),
    "høy_kontanter":    ("Høy kontantandel",   "#d1fae5", "#065f46"),
    "fallende_vekst":   ("Fallende vekst",     "#fef3c7", "#92400e"),
    "rabatt_vs_sektor": ("Rabatt vs sektor",   "#dbeafe", "#1e40af"),
    "liten_nok":        ("< 10 MRDNOK",        "#ede9fe", "#5b21b6"),
}


def _filter_hints(filters: dict) -> list[str]:
    """Returnerer liste over de filtrene som sannsynligvis er mest restriktive."""
    hints = []
    if filters.get("sektor"):
        hints.append(f'Sektor = "{filters["sektor"]}"')
    mc = filters.get("market_cap_max_mrdnok")
    if mc is not None and mc < 20:
        hints.append(f"Market cap ≤ {mc:.0f} MRDNOK")
    ev = filters.get("ev_ebitda_max")
    if ev is not None and ev < 10:
        hints.append(f"EV/EBITDA ≤ {ev:.0f}x")
    gj = filters.get("gjeld_ebitda_max")
    if gj is not None and gj < 3:
        hints.append(f"Gjeld/EBITDA ≤ {gj:.0f}x")
    mg = filters.get("ebitda_margin_min")
    if mg is not None and mg > 10:
        hints.append(f"EBITDA-margin ≥ {mg:.0f}%")
    return hints


def badge_html(flags: list[str]) -> str:
    spans = []
    for f in flags:
        label, bg, color = _BADGES.get(f, (f, "#e9ecef", "#495057"))
        spans.append(
            f'<span style="display:inline-block;background:{bg};color:{color};'
            f'border-radius:4px;padding:2px 10px;margin:2px 3px;font-size:12px;">'
            f'{label}</span>'
        )
    return "".join(spans)


# ── Header ────────────────────────────────────────────────────────────────────

st.title("Deal Screening")
st.caption("Identifiser nordiske oppkjøpskandidater")
st.divider()

# ── Layout ────────────────────────────────────────────────────────────────────

col_filters, col_results = st.columns([1, 2])

# ── Venstre: Filter-panel ─────────────────────────────────────────────────────

with col_filters:
    # ── Universe-statuskort ───────────────────────────────────────────────────
    uni = fetch_dynamic_universe()
    st.markdown("#### Universe-status")
    st.markdown(
        f'<div class="metric-card" style="margin-bottom:12px;">'
        f'<div class="metric-label">Kilde</div>'
        f'<div class="metric-value" style="font-size:14px;">{uni["source"]}</div>'
        f'<div class="metric-label" style="margin-top:6px;">'
        f'{uni["count"]} selskaper &nbsp;·&nbsp; Oppdatert {uni["fetched_at"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("Oppdater universe", use_container_width=True):
        old_count = uni["count"]
        fetch_dynamic_universe.cache_clear()
        _fetch_raw_universe.clear()
        uni_new   = fetch_dynamic_universe()
        diff      = uni_new["count"] - old_count
        diff_str  = f"+{diff}" if diff >= 0 else str(diff)
        st.success(f"Universe oppdatert: {uni_new['count']} selskaper ({diff_str} vs forrige)")
        st.rerun()

    st.markdown("#### Filtre")

    sektor = st.selectbox(
        "Sektor",
        ["Alle", "Energi", "Teknologi", "Finans", "Industri",
         "Helse", "Sjømat/Havbruk", "Shipping"],
    )

    land = st.multiselect(
        "Land",
        ["Norge", "Sverige", "Danmark", "Finland"],
        default=["Norge", "Sverige", "Danmark", "Finland"],
    )

    mc_max    = st.slider("Market cap maks (MRDNOK)", 0, 50, 15)
    ev_max    = st.slider("EV/EBITDA maks",           0, 30, 15)
    gjeld_max = st.slider("Gjeld/EBITDA maks",        0, 10,  4)
    margin_min = st.slider("EBITDA-margin min (%)",   0, 50,  0)

    context = st.text_area(
        "Kontekst (valgfritt)",
        placeholder="Beskriv hva slags oppkjøpsmål du leter etter...",
        height=100,
    )

    run_btn = st.button("Screen universe", type="primary", use_container_width=True)

# ── Høyre: Resultater ─────────────────────────────────────────────────────────

with col_results:

    if run_btn:
        filters = {
            "sektor":                  sektor if sektor != "Alle" else None,
            "land":                    land or None,
            "market_cap_max_mrdnok":   float(mc_max),
            "ev_ebitda_max":           float(ev_max),
            "gjeld_ebitda_max":        float(gjeld_max),
            "ebitda_margin_min":       float(margin_min),
        }

        progress    = st.progress(0)
        status_area = st.empty()

        # Steg 1: Screen
        _uni_count = fetch_dynamic_universe()["count"]
        status_area.write(f"Henter data for {_uni_count} selskaper...")
        screened = screen_universe(filters)
        progress.progress(33)

        if len(screened) == 0:
            progress.empty()
            status_area.empty()
            hints = _filter_hints(filters)
            hint_str = f" Mest restriktive: **{', '.join(hints)}**." if hints else ""
            st.warning(f"Ingen selskaper passerte filtrene.{hint_str}")
            st.caption("Tips: løsne på ett eller flere filterkriterier og prøv igjen.")
            st.session_state["screening_ranked"]   = []
            st.session_state["screening_screened"] = []

        elif len(screened) < 3:
            # Enrich, men hopp over AI-rangering
            status_area.write(f"{len(screened)} kandidat(er) passerte. Beriker...")
            enriched = enrich_candidates(screened)
            progress.progress(100)
            progress.empty()
            status_area.empty()

            for i, c in enumerate(enriched, 1):
                c.setdefault("rang", i)
                c.setdefault("ai_begrunnelse", "")

            st.session_state["screening_ranked"]   = enriched
            st.session_state["screening_screened"] = screened
            st.session_state["screening_too_few"]  = True

        else:
            st.session_state.pop("screening_too_few", None)

            # Steg 2: Enrich
            status_area.write(
                f"{len(screened)} kandidater passerte. Beriker topp 20..."
            )
            enriched = enrich_candidates(screened)
            progress.progress(66)

            # Steg 3: Rank
            status_area.write("AI rangerer shortlist...")
            ranked = rank_by_ma_fit(enriched, context)
            progress.progress(100)
            progress.empty()
            status_area.empty()

            st.session_state["screening_ranked"]   = ranked
            st.session_state["screening_screened"] = screened

    # ── Resultatkort ─────────────────────────────────────────────────────────

    ranked  = st.session_state.get("screening_ranked",   [])
    screened = st.session_state.get("screening_screened", [])

    if st.session_state.get("screening_too_few") and ranked:
        st.info(
            f"For få kandidater for AI-rangering — "
            f"viser alle {len(ranked)} som passerte filter."
        )

    if ranked:
        st.markdown(f"#### Shortlist — topp {len(ranked)} kandidater")

        for c in ranked:
            with st.container(border=True):

                # Rad 1: rang | info | knapp
                col_rang, col_info, col_btn = st.columns([1, 5, 2])

                with col_rang:
                    st.markdown(f"### #{c.get('rang', '?')}")

                with col_info:
                    st.markdown(
                        f"**{c['company_name']}** &nbsp; "
                        f"{c.get('flag', '')} {c.get('country', '')}"
                    )
                    st.caption(f"{c['ticker']} · {c.get('sector', '')}")

                with col_btn:
                    if st.button("Analyser →", key=f"analyse_{c['ticker']}"):
                        st.session_state["pending_ticker"] = c["ticker"]
                        st.switch_page("pages/2_Analyser.py")

                # Nøkkeltall
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    v = c.get("market_cap_mrdnok")
                    st.metric("Market cap", f"{v:.1f} MRD" if v else "N/A")
                with m2:
                    v = c.get("ev_ebitda")
                    st.metric("EV/EBITDA", f"{v:.1f}x" if v else "N/A")
                with m3:
                    v = c.get("ebitda_margin")
                    st.metric("EBITDA-margin", f"{v:.1f}%" if v else "N/A")
                with m4:
                    v = c.get("net_debt_ebitda")
                    st.metric("Gjeld/EBITDA", f"{v:.1f}x" if v else "N/A")

                # Signal-badges
                flags = c.get("signal_flags", [])
                if flags:
                    st.markdown(badge_html(flags), unsafe_allow_html=True)

                # AI-begrunnelse
                if c.get("ai_begrunnelse"):
                    st.markdown(f"_{c['ai_begrunnelse']}_")

        # ── Alle screened selskaper ───────────────────────────────────────────

        if screened:
            st.markdown("")
            with st.expander(f"Alle screenet selskaper ({len(screened)} totalt)"):
                rows = []
                for e in screened:
                    rows.append({
                        "Ticker":       e.get("ticker", ""),
                        "Selskap":      e.get("company_name", ""),
                        "Land":         f"{e.get('flag', '')} {e.get('country', '')}",
                        "Sektor":       e.get("sector", ""),
                        "MC (MRDNOK)":  e.get("market_cap_mrdnok"),
                        "EV/EBITDA":    e.get("ev_ebitda"),
                        "EV/Revenue":   e.get("ev_revenue"),
                        "EBITDA-%":     e.get("ebitda_margin"),
                        "Gjeld/EBITDA": e.get("net_debt_ebitda"),
                    })
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )
