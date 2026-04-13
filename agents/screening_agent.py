"""
Deal Screening Agent
Tre verktøy i sekvens: screen_universe → enrich_candidates → rank_by_ma_fit
"""

import json
import concurrent.futures
import streamlit as st
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as _dt
from functools import lru_cache
from anthropic import Anthropic

client = Anthropic()

# ── Universe ──────────────────────────────────────────────────────────────────

NORDIC_UNIVERSE: list[str] = [
    # Oslo Børs (57)
    "EQNR.OL",  "AKRBP.OL", "DNB.OL",    "TEL.OL",    "MOWI.OL",
    "KAHOT.OL", "BOUVET.OL","SUBC.OL",   "TGS.OL",    "KOG.OL",
    "SRBNK.OL", "SALM.OL",  "AUSS.OL",   "RECSI.OL",  "NORD.OL",
    "NHY.OL",   "YAR.OL",   "AKER.OL",   "AKSO.OL",   "SCHA.OL",
    "ORKLA.OL", "ENTRA.OL", "MPCC.OL",   "BDRILL.OL", "VAR.OL",
    "BAKKA.OL", "LSG.OL",   "HAFNI.OL",  "PGS.OL",    "NEL.OL",
    "FLNG.OL",  "AKVA.OL",  "BWO.OL",
    "ATEA.OL",  "DNO.OL",   "FRO.OL",    "GOGL.OL",   "SDRL.OL",
    "NAS.OL",   "VEI.OL",   "AFG.OL",    "BORR.OL",   "BWE.OL",
    "PANORO.OL","NRC.OL",   "CRAYN.OL",  "XXL.OL",    "ZAL.OL",
    "WIL.OL",  "AUTO.OL",   "TOM.OL",    "OKEA.OL",   "IDEX.OL",
    "THIN.OL",  "SEVAN.OL", "PARR.OL",
    # Sverige (32)
    "VOLV-B.ST","ERIC-B.ST","SEB-A.ST",  "SWED-A.ST", "SAND.ST",
    "SKF-B.ST", "HEXA-B.ST","ATCO-A.ST", "INVE-B.ST", "ESSITY-B.ST",
    "AZN.ST",   "HM-B.ST",
    "ABB.ST",   "ALFA.ST",  "ASSA-B.ST", "EVO.ST",    "SAAB-B.ST",
    "NIBE-B.ST","HUSQ-B.ST","BOLA.ST",   "SSAB-A.ST", "SCA-B.ST",
    "SKA-B.ST", "TEL2-B.ST","TELIA.ST",  "SINCH.ST",  "KINV-B.ST",
    "BETS-B.ST","ADDL.ST",  "HMS.ST",    "COOR.ST",   "CLAS-B.ST",
    # Danmark (19)
    "NOVO-B.CO","MAERSK-B.CO","DSV.CO",  "COLO-B.CO", "CARL-B.CO",
    "ORSTED.CO","DEMANT.CO", "GMAB.CO",  "RBREW.CO",
    "AMBU-B.CO","GN.CO",    "PNDORA.CO", "VWS.CO",    "TRYG.CO",
    "ALMB.CO",  "ROCK-B.CO","FLS.CO",    "NZYM-B.CO", "ISS.CO",
    # Finland (18)
    "NOKIA.HE", "NESTE.HE",  "SAMPO.HE", "OUT1V.HE",  "KNEBV.HE",
    "WRT1V.HE", "FORTUM.HE", "TIE1V.HE",
    "ELISA.HE", "UPM.HE",    "METSO.HE", "VALMT1V.HE","ORNBV.HE",
    "QTCOM.HE", "YIT1V.HE",  "FSKRS.HE", "KRA1V.HE",  "LASSILA.HE",
]

# ── Mappings ──────────────────────────────────────────────────────────────────

_SECTOR_OVERRIDES: dict[str, str] = {
    "MOWI.OL":     "Sjømat/Havbruk",
    "SALM.OL":     "Sjømat/Havbruk",
    "AUSS.OL":     "Sjømat/Havbruk",
    "RECSI.OL":    "Industri/Material",
    "BAKKA.OL":    "Sjømat/Havbruk",
    "LSG.OL":      "Sjømat/Havbruk",
    "AKVA.OL":     "Sjømat/Havbruk",
    "MPCC.OL":     "Shipping",
    "BDRILL.OL":   "Shipping",
    "HAFNI.OL":    "Shipping",
    "FLNG.OL":     "Shipping",
    "BWO.OL":      "Shipping",
    "AKSO.OL":     "Shipping",
    "SUBC.OL":     "Shipping",
    "MAERSK-B.CO": "Shipping",
    "FRO.OL":      "Shipping",
    "GOGL.OL":     "Shipping",
    "WIL.OL":      "Shipping",
    "PGS.OL":      "Energi",
    "SDRL.OL":     "Energi",
    "BORR.OL":     "Energi",
    "SEVAN.OL":    "Energi",
    "OKEA.OL":     "Energi",
    "TOM.OL":      "Teknologi",
    "AUTO.OL":     "Teknologi",
    "CRAYN.OL":    "Teknologi",
    "ZAL.OL":      "Teknologi",
    "IDEX.OL":     "Teknologi",
    "THIN.OL":     "Teknologi",
    "VEI.OL":      "Industri",
    "AFG.OL":      "Industri",
    "NRC.OL":      "Industri",
    "VWS.CO":      "Energi",
    "SAAB-B.ST":   "Industri",
}

_YFINANCE_SECTOR: dict[str, str] = {
    "Energy":                 "Energi",
    "Technology":             "Teknologi",
    "Financial Services":     "Finans",
    "Industrials":            "Industri",
    "Healthcare":             "Helse",
    "Consumer Defensive":     "Industri",
    "Consumer Cyclical":      "Industri",
    "Basic Materials":        "Industri",
    "Communication Services": "Teknologi",
    "Real Estate":            "Finans",
    "Utilities":              "Energi",
}

_COUNTRY: dict[str, str] = {
    ".OL": "Norge",
    ".ST": "Sverige",
    ".CO": "Danmark",
    ".HE": "Finland",
}
_FLAG: dict[str, str] = {
    "Norge":   "🇳🇴",
    "Sverige": "🇸🇪",
    "Danmark": "🇩🇰",
    "Finland": "🇫🇮",
}

# ── FX helpers ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _fx_to_nok(currency: str) -> float:
    """Live valutakurs til NOK. Samme logikk som pipeline/financials.py."""
    if currency == "NOK":
        return 1.0
    try:
        rate = yf.Ticker(f"{currency}NOK=X").fast_info.last_price
        if rate and rate > 0:
            return float(rate)
    except Exception:
        pass
    # EUR-bro fallback
    try:
        to_eur  = yf.Ticker(f"{currency}EUR=X").fast_info.last_price
        eur_nok = yf.Ticker("EURNOK=X").fast_info.last_price
        if to_eur and eur_nok:
            return float(to_eur * eur_nok)
    except Exception:
        pass
    return 1.0

# ── Numeriske helpers ─────────────────────────────────────────────────────────

def _safe(v) -> float | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    try:
        return round(float(v), 1)
    except Exception:
        return None


def _margin(ebitda, revenue) -> float | None:
    if not ebitda or not revenue:
        return None
    return round((ebitda / revenue) * 100, 1)


def _net_debt_ebitda(debt, cash, ebitda) -> float | None:
    if not ebitda or ebitda == 0:
        return None
    return round(((debt or 0) - (cash or 0)) / ebitda, 1)


def _country_of(ticker: str) -> str:
    for suffix, name in _COUNTRY.items():
        if ticker.endswith(suffix):
            return name
    return "Ukjent"


def _sector_of(ticker: str, yf_sector: str) -> str:
    if ticker in _SECTOR_OVERRIDES:
        return _SECTOR_OVERRIDES[ticker]
    return _YFINANCE_SECTOR.get(yf_sector, yf_sector or "Annet")

# ── Hent én ticker ────────────────────────────────────────────────────────────

def _fetch_one(ticker: str) -> dict | None:
    """Henter nøkkeltall for ett selskap via yfinance. Returnerer None ved feil."""
    try:
        info = yf.Ticker(ticker).info
        # Avvis tomme/delistede tickers
        if not info or not (info.get("regularMarketPrice") or info.get("currentPrice")
                            or info.get("marketCap")):
            return None

        currency = info.get("currency", "USD")
        fx       = _fx_to_nok(currency)

        mc  = info.get("marketCap")
        ev  = info.get("ebitda")
        rv  = info.get("totalRevenue")
        td  = info.get("totalDebt",  0) or 0
        ca  = info.get("totalCash",  0) or 0

        country = _country_of(ticker)

        return {
            "ticker":            ticker,
            "company_name":      info.get("shortName", ticker),
            "country":           country,
            "flag":              _FLAG.get(country, ""),
            "sector":            _sector_of(ticker, info.get("sector", "")),
            "industry":          info.get("industry", ""),
            "currency":          currency,
            "fx":                fx,
            "market_cap_mrdnok": round((mc * fx) / 1e9, 2) if mc else None,
            "market_cap_raw":    mc,
            "ev_ebitda":         _safe(info.get("enterpriseToEbitda")),
            "ev_revenue":        _safe(info.get("enterpriseToRevenue")),
            "ebitda_margin":     _margin(ev, rv),
            "net_debt_ebitda":   _net_debt_ebitda(td, ca, ev),
            "total_cash":        ca,
            "total_debt":        td,
            "ebitda_raw":        ev,
            "revenue_growth":    info.get("revenueGrowth"),
            "employees":         info.get("fullTimeEmployees"),
        }
    except Exception:
        return None

# ── Dynamisk univers-henting ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def fetch_dynamic_universe() -> dict:
    """
    Forsøker å hente live ticker-liste fra børsene via scraping.
    Returnerer dict med nøkler: tickers, source, count, fetched_at.

    Logikk:
      1. Prøv Oslo Børs scraping → Oslo Børs live
      2. Prøv Nasdaq Nordic Stockholm scraping → Nasdaq Nordic live
      3. Hvis begge feiler eller gir < 20 tickers → bruk NORDIC_UNIVERSE direkte
    Returnerer alltid minst like mange tickers som NORDIC_UNIVERSE.
    """
    scraped: list[str] = []
    source = ""

    # ── Kilde 1: Oslo Børs ───────────────────────────────────────────────────
    try:
        resp = requests.get(
            "https://www.oslobors.no/ob/shares",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.select("td.ob-ticker, td[data-ticker], span.ticker"):
            sym = tag.get_text(strip=True)
            if sym and 1 < len(sym) < 10:
                scraped.append(sym + ".OL")
        if len(scraped) >= 20:
            source = "Oslo Børs live"
    except Exception:
        pass

    # ── Kilde 2: Nasdaq Nordic Stockholm ─────────────────────────────────────
    if len(scraped) < 20:
        scraped.clear()
        try:
            resp = requests.get(
                "https://www.nasdaqomxnordic.com/shares/listed-companies/stockholm",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.select("td.symb, td[data-symbol]"):
                sym = tag.get_text(strip=True)
                if sym and 1 < len(sym) < 10:
                    scraped.append(sym + ".ST")
            if len(scraped) >= 20:
                source = "Nasdaq Nordic live"
        except Exception:
            pass

    # ── Fallback: hardkodet liste ─────────────────────────────────────────────
    # Skraping feilet eller ga for lite — bruk NORDIC_UNIVERSE som base
    if len(scraped) < 20 or len(scraped) > 500:
        tickers = list(NORDIC_UNIVERSE)
        source  = "Hardkodet liste"
    else:
        # Skraping lyktes — kombiner med hardkodet for å sikre full dekning
        tickers = list(dict.fromkeys(scraped + list(NORDIC_UNIVERSE)))

    return {
        "tickers":    tickers,
        "source":     source,
        "count":      len(tickers),
        "fetched_at": _dt.now().strftime("%H:%M %d.%m.%Y"),
    }


# ── Rå-univers-henting (cachet) ───────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_raw_universe() -> list[dict]:
    """
    Henter nøkkeltall for alle tickers i aktivt univers parallelt.
    Cachet i 30 minutter — det er dette som er den dyre operasjonen.
    Universet hentes fra fetch_dynamic_universe() (24-timers cache).
    """
    universe = fetch_dynamic_universe()["tickers"]
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {executor.submit(_fetch_one, t): t for t in universe}
        done, _ = concurrent.futures.wait(future_map, timeout=90)
        for future in done:
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception:
                pass
    return results

# ── Filter ────────────────────────────────────────────────────────────────────

def _passes(entry: dict, filters: dict) -> bool:
    sektor     = filters.get("sektor")
    land       = filters.get("land")
    mc_max     = filters.get("market_cap_max_mrdnok")
    ev_max     = filters.get("ev_ebitda_max")
    gjeld_max  = filters.get("gjeld_ebitda_max")
    margin_min = filters.get("ebitda_margin_min")

    if sektor:
        if entry.get("sector") != sektor:
            return False

    if land:
        if entry.get("country") not in land:
            return False

    if mc_max is not None:
        mc = entry.get("market_cap_mrdnok")
        if mc is None or mc > mc_max:
            return False

    if ev_max is not None:
        ev = entry.get("ev_ebitda")
        if ev is None or ev > ev_max:
            return False

    if gjeld_max is not None:
        gj = entry.get("net_debt_ebitda")
        if gj is not None and gj > gjeld_max:
            return False

    if margin_min and margin_min > 0:
        m = entry.get("ebitda_margin")
        if m is None or m < margin_min:
            return False

    return True

# ── Verktøy 1: screen_universe ────────────────────────────────────────────────

def screen_universe(filters: dict) -> list[dict]:
    """
    Filtrerer det nordiske universet.
    Rådata cachet i 30 min via _fetch_raw_universe().
    """
    universe = _fetch_raw_universe()
    filtered = [e for e in universe if _passes(e, filters)]
    filtered.sort(key=lambda x: x.get("ev_ebitda") or 999)
    return filtered

# ── Verktøy 2: enrich_candidates ─────────────────────────────────────────────

def enrich_candidates(candidates: list[dict]) -> list[dict]:
    """
    Beriker topp 20 kandidater med M&A-signal-flagg.
    Bruker allerede-hentet data fra screen_universe — ingen nye API-kall.
    """
    top20 = candidates[:20]

    # Sektor-median for EV/EBITDA (brukes til rabatt_vs_sektor-signal)
    sector_evs: dict[str, list[float]] = {}
    for c in top20:
        s  = c.get("sector", "")
        ev = c.get("ev_ebitda")
        if s and ev is not None:
            sector_evs.setdefault(s, []).append(ev)

    sector_median: dict[str, float] = {
        s: sorted(vals)[len(vals) // 2]
        for s, vals in sector_evs.items() if vals
    }

    enriched: list[dict] = []
    for c in top20:
        fx         = c.get("fx", 1.0)
        mc_raw     = c.get("market_cap_raw") or 0
        mc_nok     = mc_raw * fx
        cash       = c.get("total_cash") or 0
        cash_ratio = (cash * fx / mc_nok) if mc_nok > 0 else None

        ev_ebitda = c.get("ev_ebitda")
        sector    = c.get("sector", "")
        s_med     = sector_median.get(sector)

        flags: list[str] = []

        nd = c.get("net_debt_ebitda")
        if nd is not None and nd < 1.0:
            flags.append("lav_gjeld")

        if cash_ratio is not None and cash_ratio > 0.20:
            flags.append("høy_kontanter")

        rg = c.get("revenue_growth")
        if rg is not None and rg < 0:
            flags.append("fallende_vekst")

        if ev_ebitda is not None and s_med is not None and ev_ebitda < s_med * 0.80:
            flags.append("rabatt_vs_sektor")

        mc_mrd = c.get("market_cap_mrdnok")
        if mc_mrd is not None and mc_mrd < 10:
            flags.append("liten_nok")

        rg_pct = round(rg * 100, 1) if rg is not None else None

        enriched.append({**c, "revenue_growth_pct": rg_pct, "signal_flags": flags})

    return enriched

# ── Verktøy 3: rank_by_ma_fit ─────────────────────────────────────────────────

def rank_by_ma_fit(candidates: list[dict], context: str) -> list[dict]:
    """
    Bruker Claude til å rangere topp 10 kandidater etter M&A-egnethet.
    Faller tilbake på EV/EBITDA-sortering hvis API feiler.
    """
    top10 = candidates[:10]

    lines = []
    for i, c in enumerate(top10, 1):
        flag_str = ", ".join(c.get("signal_flags", [])) or "ingen"
        lines.append(
            f"{i}. {c['company_name']} ({c['ticker']}) "
            f"[{c.get('flag', '')} {c.get('country', '')}] — "
            f"MC: {c.get('market_cap_mrdnok')} MRDNOK | "
            f"EV/EBITDA: {c.get('ev_ebitda')}x | "
            f"EBITDA-margin: {c.get('ebitda_margin')}% | "
            f"Gjeld/EBITDA: {c.get('net_debt_ebitda')}x | "
            f"Signaler: {flag_str}"
        )

    context_line = f"\nKontekst fra bruker: {context.strip()}" if context.strip() else ""

    prompt = f"""Du er en erfaren M&A-analytiker med spesialkompetanse på nordiske markeder.

Ranger disse selskapene som oppkjøpskandidater.{context_line}

{chr(10).join(lines)}

Vurder for hvert selskap:
1. Verdsettelsesrabatt vs peers (lav EV/EBITDA er positivt)
2. Strategisk attraktivitet for en potensiell kjøper
3. Finansiell styrke og oppkjøpbarhet (lav gjeld, god likviditet)
4. Størrelse — er selskapet realistisk å kjøpe?

Svar KUN med dette JSON-formatet, ingen annen tekst:
{{
  "rangering": [
    {{"ticker": "TICKER.XX", "rang": 1, "begrunnelse": "Maks 1 setning."}}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.split("```")[0]

        print(f"[rank_by_ma_fit] raw Claude response:\n{raw}\n")

        # Forsøk 1: direkte parsing
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            # Forsøk 2: kutt ved siste komplette objekt
            # Finn siste "}" og avslutt arrayen der
            last_brace = raw.rfind("}")
            if last_brace != -1:
                truncated = raw[: last_brace + 1] + "]}"
                # Sørg for at vi har et gyldig array-innhold
                # Finn starten på "rangering"-arrayen
                array_start = truncated.find("[")
                if array_start != -1:
                    truncated = '{"rangering": ' + truncated[array_start:]
                data = json.loads(truncated)
                print(f"[rank_by_ma_fit] brukte avkuttet JSON-parsing")
            else:
                raise

        # Valider og filtrer objekter som mangler påkrevde felt
        raw_items = data.get("rangering", [])
        valid_items = [
            r for r in raw_items
            if r.get("ticker") and r.get("rang") is not None and "begrunnelse" in r
        ]
        rank_map = {r["ticker"]: r for r in valid_items}

        ranked = []
        for c in top10:
            r = rank_map.get(c["ticker"], {})
            ranked.append({
                **c,
                "rang":           r.get("rang", 99),
                "ai_begrunnelse": r.get("begrunnelse", ""),
            })
        ranked.sort(key=lambda x: x.get("rang", 99))
        return ranked

    except Exception as e:
        print(f"[rank_by_ma_fit] FEIL: {e} — sorterer på EV/EBITDA")
        try:
            import streamlit as _st
            _st.warning(f"AI rangering feilet ({type(e).__name__}: {e}) — viser EV/EBITDA-sortering uten begrunnelse.")
        except Exception:
            pass
        fallback = sorted(top10, key=lambda x: x.get("ev_ebitda") or 999)
        for i, c in enumerate(fallback, 1):
            c["rang"] = i
            c["ai_begrunnelse"] = ""
        return fallback

# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_screening(filters: dict, context: str) -> dict:
    """Kjører screen → enrich → rank i sekvens."""
    screened = screen_universe(filters)

    if len(screened) < 3:
        return {
            "status":   "too_few",
            "message":  f"Kun {len(screened)} selskaper passerte filtrene. Juster filtrene og prøv igjen.",
            "screened": screened,
            "ranked":   [],
        }

    enriched = enrich_candidates(screened)
    ranked   = rank_by_ma_fit(enriched, context)

    return {
        "status":   "ok",
        "screened": screened,
        "ranked":   ranked,
    }
