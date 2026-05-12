import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv
load_dotenv()

from export.pdf_export import generate_pdf
from pipeline.snapshot import SnapshotBuilder
from models import CompanySnapshot

st.set_page_config(
    page_title="Analyser — Company Analysis Copilot",
    page_icon="🔍",
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


# ── Header ───────────────────────────────────────────────────────────────────
st.title("Company Analysis Copilot")
st.caption("Nordisk M&A og investor analyse — ticker, årsrapport eller nettside")

# Hent eventuell ticker sendt fra Screening-siden, og nullstill den med én gang
_pending = st.session_state.pop("pending_ticker", None)

# ── Input ────────────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([4, 1])
with col_input:
    user_input = st.text_input(
        label="Input",
        value=_pending or "",
        placeholder="f.eks. EQNR.OL, eller lim inn URL til IR-side",
        label_visibility="collapsed"
    )
with col_btn:
    analyse_btn  = st.button("Analyser", type="primary", use_container_width=True)
    force_reload = st.button("Tving ny analyse", type="secondary", use_container_width=True)

# Auto-trigger hvis siden ble åpnet fra Screening
if _pending and not analyse_btn:
    analyse_btn = True
    user_input  = _pending

# PDF-upload
uploaded_pdf = st.file_uploader(
    "Eller last opp årsrapport (PDF)",
    type=["pdf"],
    label_visibility="collapsed"
)

# ── Pipeline ─────────────────────────────────────────────────────────────────
if analyse_btn and (user_input or uploaded_pdf):

    # Håndter PDF-upload
    if uploaded_pdf:
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_pdf.read())
            tmp_path = tmp.name
        input_value = tmp_path
    else:
        input_value = user_input

    with st.spinner("Analyserer..."):
        try:
            from watchlist.store import save_snapshot_cache, load_snapshot_cache

            cached = None if force_reload else load_snapshot_cache(input_value)
            if cached:
                st.info("Hentet fra cache — trykk 'Tving ny analyse' for ferske data")
                snapshot = cached
            else:
                builder  = SnapshotBuilder()
                snapshot = builder.build(input_value)
                save_snapshot_cache(snapshot)

            # Rydd opp temp-fil
            if uploaded_pdf:
                os.unlink(tmp_path)

            # Lagre i session state så siden ikke re-kjører
            st.session_state["snapshot"] = snapshot

        except Exception as e:
            st.error(f"Feil under analyse: {e}")
            st.stop()

# ── Dashboard ────────────────────────────────────────────────────────────────
snapshot: CompanySnapshot = st.session_state.get("snapshot")

if snapshot:
    st.divider()

    # Selskapsnavn og metadata
    st.subheader(snapshot.company_name)
    meta_cols = st.columns(3)
    with meta_cols[0]:
        st.caption(f"Ticker: {snapshot.ticker or 'N/A'}")
    with meta_cols[1]:
        st.caption(f"Hovedkontor: {snapshot.headquarters}")
    with meta_cols[2]:
        st.caption(f"Grunnlagt: {snapshot.founded or 'N/A'}")

    st.write(snapshot.business_description)
    st.divider()

    # ── Rad 1: Nøkkeltall ────────────────────────────────────────────────────
    st.markdown("#### Nøkkeltall")
    m1, m2, m3, m4, m5 = st.columns(5)

    def metric(col, label, value, suffix=""):
        with col:
            if value is not None:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value:,.1f}{suffix}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">N/A</div>
                </div>""", unsafe_allow_html=True)

    metric(m1, "Market cap (MNOK)", snapshot.market_cap_mnok)
    metric(m2, "EV/EBITDA", snapshot.ev_ebitda, "x")
    metric(m3, "EBITDA-margin", snapshot.ebitda_margin, "%")
    metric(m4, "Netto gjeld/EBITDA", snapshot.net_debt_ebitda, "x")
    metric(m5, "Omsetning CAGR 3y", snapshot.revenue_cagr_3y, "%")

    st.divider()

    # ── Rad 2: Geo + Peer comparison ─────────────────────────────────────────
    col_geo, col_peer = st.columns([1, 2])

    with col_geo:
        st.markdown("#### Geografisk eksponering")
        if snapshot.geographic_exposure:
            geo_data = {
                k: v for k, v in snapshot.geographic_exposure.items()
                if v > 0
            }
            fig_geo = go.Figure(go.Pie(
                labels=list(geo_data.keys()),
                values=list(geo_data.values()),
                hole=0.45,
                textinfo="label+percent",
                textfont_size=12,
                marker_colors=px.colors.qualitative.Set2,
            ))
            fig_geo.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=240,
            )
            st.plotly_chart(fig_geo, width='stretch')

    with col_peer:
        st.markdown("#### Peer comparison — EV/EBITDA")
        if snapshot.peer_multiples:
            # Legg til selskapet selv øverst
            all_peers = [{
                "ticker": snapshot.ticker or snapshot.company_name,
                "name":   snapshot.company_name,
                "ev_ebitda": snapshot.ev_ebitda,
            }] + [
                {"ticker": p.ticker, "name": p.name, "ev_ebitda": p.ev_ebitda}
                for p in snapshot.peer_multiples
                if p.ev_ebitda is not None
            ]

            labels  = [p["ticker"] for p in all_peers]
            values  = [p["ev_ebitda"] or 0 for p in all_peers]
            colors  = ["#3b82f6"] + ["#94a3b8"] * (len(labels) - 1)

            fig_peer = go.Figure(go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                text=[f"{v:.1f}x" if v else "N/A" for v in values],
                textposition="outside",
            ))
            fig_peer.update_layout(
                yaxis_title="EV/EBITDA",
                margin=dict(t=30, b=10, l=10, r=10),
                height=240,
                plot_bgcolor="white",
                yaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig_peer, width='stretch')

    st.divider()

    # ── Rad 3: Inntektsdrivere, risikoer, why/why not ────────────────────────
    col_l, col_m, col_r = st.columns(3)

    with col_l:
        st.markdown("#### Inntektsdrivere")
        for driver in (snapshot.revenue_drivers or []):
            st.markdown(f'<span class="tag">{driver}</span>',
                       unsafe_allow_html=True)

    with col_m:
        st.markdown("#### Nøkkelrisikoer")
        for risk in (snapshot.key_risks or []):
            st.markdown(f'<span class="tag risk">{risk}</span>',
                       unsafe_allow_html=True)

    with col_r:
        st.markdown("#### Investor-vurdering")
        st.markdown(
            f'<div class="tag pro" style="display:block;margin-bottom:8px;">'
            f'+ {snapshot.why_interesting}</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="tag con" style="display:block;">'
            f'- {snapshot.why_not_interesting}</div>',
            unsafe_allow_html=True
        )

    st.divider()

    st.markdown("#### Eksport")
    if st.button("Last ned 1-side PDF", type="secondary"):
        with st.spinner("Genererer PDF..."):
            pdf_bytes = generate_pdf(snapshot)
            st.download_button(
                label="Klikk for å laste ned",
                data=pdf_bytes,
                file_name=f"{snapshot.ticker or snapshot.company_name}_snapshot.pdf",
                mime="application/pdf",
            )

    from watchlist.store import add_to_watchlist, is_in_watchlist

    st.divider()
    st.markdown("#### Watchlist")

    if snapshot.ticker:
        if is_in_watchlist(snapshot.ticker):
            st.success(f"{snapshot.ticker} er allerede i watchlisten din")
            if st.button("Fjern fra watchlist"):
                from watchlist.store import remove_from_watchlist
                remove_from_watchlist(snapshot.ticker)
                st.rerun()
        else:
            threshold = st.slider(
                "Varsle ved kursendring større enn",
                min_value=1.0,
                max_value=20.0,
                value=5.0,
                step=0.5,
                format="%.1f%%"
            )
            if st.button("Legg til i watchlist", type="primary"):
                add_to_watchlist(snapshot, price_threshold_pct=threshold)
                st.session_state["watchlist_updated"] = True
                st.success(f"{snapshot.ticker} lagt til i watchlisten!")
                st.rerun()
