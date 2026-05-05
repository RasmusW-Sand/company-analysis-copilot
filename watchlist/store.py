import json
import os
from datetime import datetime, date, timedelta, timezone
from models import CompanySnapshot
import pickle
from pathlib import Path

CACHE_PATH = "watchlist/snapshot_cache"

WATCHLIST_PATH = "watchlist/watchlist.json"


def load_watchlist() -> list[dict]:
    if not os.path.exists(WATCHLIST_PATH):
        return []
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_watchlist(watchlist: list[dict]) -> None:
    os.makedirs("watchlist", exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, indent=2, ensure_ascii=False)


def add_to_watchlist(
    snapshot: CompanySnapshot,
    price_threshold_pct: float = 5.0,
) -> None:
    """
    Legger til et selskap i watchlist.
    Lagrer nåværende pris som baseline for fremtidige sammenlikninger.
    """
    import yfinance as yf

    watchlist = load_watchlist()

    # Sjekk om selskapet allerede er i watchlist
    existing = [w for w in watchlist if w.get("ticker") == snapshot.ticker]
    if existing:
        return

    # Hent nåværende pris som baseline
    current_price = None
    currency = None
    if snapshot.ticker:
        try:
            info = yf.Ticker(snapshot.ticker).fast_info
            current_price = float(info.last_price)
            currency = info.currency
        except Exception:
            pass

    # Hent neste rapporteringsdato
    next_earnings = None
    if snapshot.ticker:
        try:
            df = yf.Ticker(snapshot.ticker).earnings_dates
            if df is not None and not df.empty:
                today = datetime.now(timezone.utc).date()
                future = [d.date() for d in df.index if d.date() >= today]
                if future:
                    next_earnings = min(future).isoformat()
        except Exception:
            pass

    entry = {
        "ticker":              snapshot.ticker,
        "company_name":        snapshot.company_name,
        "added_at":            datetime.now().isoformat(),
        "last_checked":        datetime.now().isoformat(),
        "baseline_price":      current_price,
        "currency":            currency,
        "price_threshold_pct": price_threshold_pct,
        "last_ev_ebitda":      snapshot.ev_ebitda,
        "headquarters":        snapshot.headquarters,
        "next_earnings_date":  next_earnings,
    }

    watchlist.append(entry)
    save_watchlist(watchlist)


def get_upcoming_earnings(days_ahead: int = 2) -> list[dict]:
    """Returnerer selskaper som rapporterer innen days_ahead dager."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    result = []
    for entry in load_watchlist():
        raw = entry.get("next_earnings_date")
        if not raw:
            continue
        try:
            earnings_date = date.fromisoformat(raw)
            if today <= earnings_date <= cutoff:
                result.append(entry)
        except ValueError:
            pass
    return result


def remove_from_watchlist(ticker: str) -> None:
    watchlist = load_watchlist()
    watchlist = [w for w in watchlist if w.get("ticker") != ticker]
    save_watchlist(watchlist)


def update_last_checked(ticker: str) -> None:
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("ticker") == ticker:
            entry["last_checked"] = datetime.now().isoformat()
    save_watchlist(watchlist)


def update_baseline(ticker: str, new_price: float) -> None:
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("ticker") == ticker:
            entry["baseline_price"] = new_price
            entry["last_checked"]   = datetime.now().isoformat()
    save_watchlist(watchlist)


_SUFFIX_CURRENCY = {
    ".OL": "NOK",  # Oslo Børs
    ".ST": "SEK",  # Stockholm
    ".CO": "DKK",  # Copenhagen
    ".HE": "EUR",  # Helsinki
}


def backfill_currencies() -> None:
    """Fetches and stores missing currency fields for existing watchlist entries."""
    import yfinance as yf
    watchlist = load_watchlist()
    changed = False
    for entry in watchlist:
        if entry.get("currency"):
            continue
        ticker = entry.get("ticker")
        if not ticker:
            continue
        # Try yfinance first
        currency = None
        try:
            currency = yf.Ticker(ticker).fast_info.currency or None
        except Exception:
            pass
        # Fall back to exchange suffix
        if not currency:
            for suffix, code in _SUFFIX_CURRENCY.items():
                if ticker.upper().endswith(suffix.upper()):
                    currency = code
                    break
        # Default to USD for plain tickers (e.g. CVX, SDRL)
        if not currency:
            currency = "USD"
        entry["currency"] = currency
        changed = True
    if changed:
        save_watchlist(watchlist)


def is_in_watchlist(ticker: str) -> bool:
    return any(w.get("ticker") == ticker for w in load_watchlist())


def update_brief_sent(ticker: str, date_str: str) -> None:
    """Lagrer datoen earnings brief ble sendt for en ticker."""
    watchlist = load_watchlist()
    for entry in watchlist:
        if entry.get("ticker") == ticker:
            entry["last_brief_sent"] = date_str
    save_watchlist(watchlist)

def save_snapshot_cache(snapshot) -> None:
    os.makedirs(CACHE_PATH, exist_ok=True)
    key = (snapshot.ticker or snapshot.company_name.replace(" ", "_")).replace(".", "_")
    with open(f"{CACHE_PATH}/{key}.pkl", "wb") as f:
        pickle.dump(snapshot, f)


def load_snapshot_cache(key: str):
    clean_key = key.replace(".", "_")
    path = Path(f"{CACHE_PATH}/{clean_key}.pkl")
    if not path.exists():
        return None
    age_hours = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    if age_hours > 24:
        return None
    with open(path, "rb") as f:
        return pickle.load(f)