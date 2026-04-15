import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

if st.session_state.get("watchlist_updated"):
    st.session_state["watchlist_updated"] = False
    st.rerun()

from watchlist.store import load_watchlist

PROJ_ROOT = Path(__file__).parent
LOG_PATH  = PROJ_ROOT / "watchlist" / "monitor.log"

st.set_page_config(
    page_title="Watchlist",
    page_icon="📋",
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


# ── Log helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def read_log() -> str:
    if not LOG_PATH.exists():
        return ""
    return LOG_PATH.read_text(encoding="utf-8", errors="replace")


def _parse_ts(line: str) -> datetime | None:
    m = re.search(r'\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y %H:%M:%S")
        except ValueError:
            pass
    return None


def last_ok_run(log: str) -> datetime | None:
    result = None
    for line in log.splitlines():
        if "=== Monitor fullfort OK ===" in line:
            ts = _parse_ts(line)
            if ts:
                result = ts
    return result


def alerts_last_7d(log: str) -> int:
    """Teller kjøringer med triggere de siste 7 dagene."""
    cutoff = datetime.now() - timedelta(days=7)
    count  = 0
    current_ts: datetime | None = None
    for line in log.splitlines():
        if "=== Monitor startet ===" in line:
            current_ts = _parse_ts(line)
        elif current_ts and current_ts >= cutoff and "trigger(e) funnet" in line:
            count += 1
    return count


def next_earnings_entry(watchlist: list[dict]) -> tuple[str, str] | None:
    """Returnerer (selskapsnavn, dato-streng) for neste kommende rapport."""
    today     = date.today()
    best_name: str | None = None
    best_date: date | None = None
    for e in watchlist:
        raw = e.get("next_earnings_date")
        if not raw:
            continue
        try:
            d = date.fromisoformat(raw)
            if d >= today and (best_date is None or d < best_date):
                best_date = d
                best_name = e.get("company_name") or e.get("ticker", "")
        except ValueError:
            pass
    if best_name and best_date:
        return best_name, best_date.isoformat()
    return None


def watchlist_dataframe(watchlist: list[dict]) -> pd.DataFrame:
    today = date.today()
    rows = []
    for e in watchlist:
        ned = e.get("next_earnings_date")
        days_until = None
        if ned:
            try:
                days_until = (date.fromisoformat(ned) - today).days
            except ValueError:
                pass

        rows.append({
            "Selskap":       e.get("company_name", ""),
            "Ticker":        e.get("ticker", ""),
            "Lagt til":      (e.get("added_at") or "")[:10],
            "Terskel":       f"{e.get('price_threshold_pct', 5.0):.1f}%",
            "Baseline":      f"${e.get('baseline_price'):.2f}" if e.get("baseline_price") else "N/A",
            "Neste rapport": ned if ned else "N/A",
            "Siste sjekk":   (e.get("last_checked") or "")[:16].replace("T", " "),
            "_days_until":   days_until,
        })

    return pd.DataFrame(rows)


# ── UI ────────────────────────────────────────────────────────────────────────

# Load data
log       = read_log()
watchlist = load_watchlist()
last_run  = last_ok_run(log)
last_run_str = last_run.strftime("%d.%m.%Y %H:%M") if last_run else "Aldri kjørt"

# Header
st.title("Company Analysis Copilot")
st.caption(f"Nordisk M&A og investor analyse — siste kjøring: {last_run_str}")
st.divider()

# ── Metrics ───────────────────────────────────────────────────────────────────
st.markdown("#### Status")
c1, c2, c3, c4 = st.columns(4)


def card(col, label: str, value: str) -> None:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>""", unsafe_allow_html=True)


card(c1, "Selskaper i watchlist", str(len(watchlist)))
card(c2, "Varsler siste 7 dager", str(alerts_last_7d(log)))

ne = next_earnings_entry(watchlist)
if ne:
    card(c3, "Neste kvartalsrapport", f"{ne[0]}<br><small style='font-size:14px;font-weight:400;'>{ne[1]}</small>")
else:
    card(c3, "Neste kvartalsrapport", "N/A")

card(c4, "Siste monitor-kjøring", last_run_str)

st.divider()

# ── Watchlist table ───────────────────────────────────────────────────────────
st.markdown("#### Watchlist")
if watchlist:
    st.markdown(
        "<small style='color:#6c757d;'>"
        "<span style='color:#dc3545;'>&#9632;</span> Kvartalsrapport innen 2 dager &nbsp;&nbsp;"
        "<span style='color:#198754;'>&#9632;</span> Ingen umiddelbar hendelse"
        "</small>",
        unsafe_allow_html=True,
    )
    df = watchlist_dataframe(watchlist)

    def highlight_earnings(row):
        days = df.loc[row.name, "_days_until"]
        if days is not None and 0 <= days <= 2:
            return ["background-color: #fee2e2"] * len(row)
        return ["background-color: #f0fff4"] * len(row)

    display_df = df.drop(columns=["_days_until"])
    styled = display_df.style.apply(highlight_earnings, axis=1)

    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("Watchlisten er tom. Legg til selskaper via Analyser-siden.")

st.divider()

# ── Earnings Briefs ───────────────────────────────────────────────────────────
earnable = [e for e in watchlist if e.get("next_earnings_date")]
if earnable:
    st.markdown("#### Earnings Briefs")
    st.caption("Generer et profesjonelt briefing-dokument for kommende kvartalsrapporter.")

    for entry in earnable:
        ticker      = entry.get("ticker", "")
        company     = entry.get("company_name", ticker)
        report_date = entry.get("next_earnings_date", "")

        key_sum   = f"summary_{ticker}"
        key_dl    = f"dl_{ticker}"
        key_brief = f"brief_{ticker}"

        with st.expander(f"{company} ({ticker}) — rapporterer {report_date}"):
            if st.button("Generer Earnings Brief", key=key_brief, type="primary"):
                with st.spinner(f"Genererer earnings brief for {company}..."):
                    from agents.earnings_agent import EarningsAgent
                    agent             = EarningsAgent()
                    briefing, pdf_bytes = agent.prepare_report(ticker)
                st.session_state[key_sum] = briefing.get("executive_summary", "")
                st.session_state[key_dl]  = pdf_bytes

            if st.session_state.get(key_sum):
                st.markdown("**Executive Summary:**")
                st.info(st.session_state[key_sum])

            if st.session_state.get(key_dl):
                st.download_button(
                    label=f"Last ned {ticker}_earnings_brief.pdf",
                    data=st.session_state[key_dl],
                    file_name=f"{ticker}_earnings_brief.pdf",
                    mime="application/pdf",
                    key=f"dl_btn_{ticker}",
                )

    st.divider()

# ── Kjør monitor nå ───────────────────────────────────────────────────────────
st.markdown("#### Kjør monitor")

if st.button("Kjør monitor nå", type="primary"):
    st.cache_data.clear()
    output_area  = st.empty()
    full_output  = ""
    with st.spinner("Kjører overvåking..."):
        proc = subprocess.Popen(
            [sys.executable, "-m", "watchlist.monitor"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJ_ROOT),
        )
        for line in proc.stdout:
            full_output += line
            output_area.code(full_output, language="text")
        proc.wait()
    if proc.returncode == 0:
        st.success("Monitor fullfort OK.")
    else:
        st.error(f"Monitor avsluttet med feil (kode {proc.returncode}).")
    st.cache_data.clear()

st.divider()

# ── Monitor log expander ──────────────────────────────────────────────────────
with st.expander("Monitor log — siste 20 linjer"):
    if log:
        last_20 = "\n".join(log.splitlines()[-20:])
        st.code(last_20, language="text")
    else:
        st.info("Ingen logg funnet.")
