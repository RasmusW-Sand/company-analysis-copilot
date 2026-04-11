import sys
import re
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

PROJ_ROOT    = Path(__file__).parent.parent
LOG_PATH     = PROJ_ROOT / "watchlist" / "monitor.log"
ARCHIVE_PATH = PROJ_ROOT / "watchlist" / "monitor_archive.log"

st.set_page_config(
    page_title="Agent Log — Company Analysis Copilot",
    page_icon="📜",
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


def parse_runs(log: str) -> list[dict]:
    """
    Splitter loggen i individuelle kjøringer.
    Hver kjøring er avgrenset av 'Monitor startet' og enten 'fullfort OK' eller 'FEIL'.
    Kjøringer uten innhold filtreres bort.
    """
    runs: list[dict] = []
    current: dict | None = None
    body_lines: list[str] = []

    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if "=== Monitor startet ===" in line:
            current    = {
                "start_line": line,
                "start_ts":   _parse_ts(line),
                "status":     "KJORER",
                "end_line":   None,
                "body":       [],
            }
            body_lines = []

        elif current is not None:
            if "=== Monitor fullfort OK ===" in line:
                current["status"]   = "OK"
                current["end_line"] = line
                current["body"]     = body_lines[:]
                runs.append(current)
                current    = None
                body_lines = []

            elif "FEIL:" in line and "avsluttet med kode" in line:
                current["status"]   = "FEIL"
                current["end_line"] = line
                current["body"]     = body_lines[:]
                runs.append(current)
                current    = None
                body_lines = []

            else:
                body_lines.append(line)

    # Ufullstendig kjøring (krasjet uten FEIL-linje)
    if current is not None:
        current["body"] = body_lines
        runs.append(current)

    # Filtrer bort tomme kjøringer
    return [r for r in runs if r["body"]]


# ── UI ────────────────────────────────────────────────────────────────────────

col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("Company Analysis Copilot")
    st.caption("Agent Log — historikk over overvåkingskjøringer")
with col_btn:
    st.markdown("<div style='padding-top:24px;'></div>", unsafe_allow_html=True)
    if st.button("Tøm log", type="secondary", use_container_width=True):
        if LOG_PATH.exists():
            existing = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            with open(ARCHIVE_PATH, "a", encoding="utf-8") as af:
                af.write(existing)
            LOG_PATH.write_text("", encoding="utf-8")
        st.cache_data.clear()
        st.success("Log arkivert til monitor_archive.log og tømt.")
        st.rerun()

st.divider()

log  = read_log()
runs = parse_runs(log)

if not runs:
    st.info("Ingen loggede kjøringer funnet.")
else:
    ok_count   = sum(1 for r in runs if r["status"] == "OK")
    err_count  = sum(1 for r in runs if r["status"] == "FEIL")
    st.markdown(
        f"**{len(runs)} kjøring(er) totalt** &nbsp;·&nbsp; "
        f"🟢 {ok_count} OK &nbsp;·&nbsp; "
        f"🔴 {err_count} feil",
        unsafe_allow_html=True,
    )
    st.markdown("")

    for run in reversed(runs):  # Nyeste øverst
        ts     = run["start_ts"]
        ts_str = ts.strftime("%d.%m.%Y %H:%M") if ts else "Ukjent tid"
        status = run["status"]

        if status == "OK":
            icon = "🟢"
        elif status == "FEIL":
            icon = "🔴"
        else:
            icon = "🟡"

        # Finn triggere i kjøringens output
        triggers = [l for l in run["body"] if "trigger(e) funnet" in l or "Varsel sendt" in l]
        trigger_note = f" — {triggers[0]}" if triggers else ""

        label = f"{icon} {ts_str}{trigger_note}"

        with st.expander(label):
            for line in run["body"]:
                st.text(line)
            if run["end_line"]:
                st.text(run["end_line"])
