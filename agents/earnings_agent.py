"""
Earnings Prep Agent
Henter data, genererer analyse med Claude via agentic tool-use loop, og produserer PDF-briefing.
"""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
from anthropic import Anthropic


SYSTEM_PROMPT = """Du er en erfaren senior M&A- og equity-analytiker med spesialkompetanse
på nordiske og internasjonale markeder. Du skal lage en profesjonell earnings briefing
for et selskap som snart rapporterer kvartalsresultat.

Du har tilgang til følgende verktøy:

- get_financial_data(ticker): Henter finansdata fra yfinance — estimater, historikk,
  kursmål, anbefalinger og kvartalstall. Kall dette først.
- get_peer_multiples(tickers): Henter EV/EBITDA og P/E for sammenlignbare selskaper.
  Bruk dette for å kontekstualisere verdivurderingen.
- web_search: Søk etter ferske nyheter, analytiker-kommentarer, sektorutsikter og
  makroøkonomiske faktorer som er relevante for rapporten.
- write_briefing_section(section, content): Skriv én seksjon av briefingen. Kall dette
  for hver seksjon etter hvert som du analyserer dataene.

Arbeidsflyt:
1. Hent finansdata med get_financial_data
2. Søk etter fersk markedskontekst med web_search (minst 2-3 søk)
3. Hent peer-multipler hvis relevant
4. Skriv briefingen seksjon for seksjon med write_briefing_section

Seksjonene du MÅ skrive: executive_summary, consensus_view, historical_performance,
what_to_watch, key_risks, ma_angle, questions_for_management.

Svar på norsk i alle seksjoner."""


class EarningsAgent:

    def __init__(self):
        self.client = Anthropic()

    # ── Datahenting ───────────────────────────────────────────────────────────

    def fetch_earnings_data(self, ticker: str) -> dict:
        """
        Henter all nødvendig data for earnings briefing via yfinance.
        Alle kall er i individuelle try/except — returnerer None for felt
        som feiler, krasjer aldri på manglende data.
        """
        t = yf.Ticker(ticker)

        # ── Grunninfo ─────────────────────────────────────────────────────────
        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass

        company_name = info.get("shortName") or info.get("longName") or ticker
        currency     = info.get("currency", "USD")

        # ── Estimater: EPS ────────────────────────────────────────────────────
        earnings_estimate = None
        try:
            df = t.earnings_estimate
            if df is not None and not df.empty:
                earnings_estimate = []
                for period, row in df.iterrows():
                    earnings_estimate.append({
                        "period":       str(period),
                        "avg_estimate": _safe_float(row.get("avg")),
                        "low":          _safe_float(row.get("low")),
                        "high":         _safe_float(row.get("high")),
                        "n_analysts":   _safe_int(row.get("numberOfAnalysts")),
                    })
        except Exception:
            pass

        # ── Estimater: Revenue ────────────────────────────────────────────────
        revenue_estimate = None
        try:
            df = t.revenue_estimate
            if df is not None and not df.empty:
                revenue_estimate = []
                for period, row in df.iterrows():
                    revenue_estimate.append({
                        "period":       str(period),
                        "avg_estimate": _safe_float(row.get("avg")),
                        "low":          _safe_float(row.get("low")),
                        "high":         _safe_float(row.get("high")),
                        "n_analysts":   _safe_int(row.get("numberOfAnalysts")),
                    })
        except Exception:
            pass

        # ── Kursmål ───────────────────────────────────────────────────────────
        price_targets = None
        try:
            pt = t.analyst_price_targets
            if pt and isinstance(pt, dict) and pt.get("mean"):
                price_targets = {
                    "low":     _safe_float(pt.get("low")),
                    "mean":    _safe_float(pt.get("mean")),
                    "high":    _safe_float(pt.get("high")),
                    "current": _safe_float(pt.get("current")),
                }
        except Exception:
            pass

        recommendation = info.get("recommendationKey")

        # ── Kvartalsvise finanstall (siste 4 kv.) ─────────────────────────────
        quarterly_financials = None
        try:
            df = t.quarterly_financials
            if df is not None and not df.empty:
                quarterly_financials = []
                cols = list(df.columns[:4])  # siste 4 kvartaler
                for col in cols:
                    quarter_data = {
                        "date":        str(col)[:10],
                        "revenue":     _safe_float(df.loc["Total Revenue", col]) if "Total Revenue" in df.index else None,
                        "gross_profit":_safe_float(df.loc["Gross Profit", col]) if "Gross Profit" in df.index else None,
                        "ebitda":      _safe_float(df.loc["EBITDA", col]) if "EBITDA" in df.index else None,
                        "net_income":  _safe_float(df.loc["Net Income", col]) if "Net Income" in df.index else None,
                    }
                    quarterly_financials.append(quarter_data)
        except Exception:
            pass

        # ── Beat/Miss-historikk ───────────────────────────────────────────────
        earnings_history = None
        try:
            df = t.earnings_history
            if df is not None and not df.empty:
                earnings_history = []
                for _, row in df.tail(4).iterrows():
                    earnings_history.append({
                        "quarter":      str(row.get("period", "")),
                        "eps_estimate": _safe_float(row.get("epsEstimate")),
                        "eps_actual":   _safe_float(row.get("epsActual")),
                        "surprise_pct": _safe_float(row.get("epsDifference")),
                    })
        except Exception:
            pass

        # ── Kursprestasjon ────────────────────────────────────────────────────
        price_30d_return = None
        price_90d_return = None
        try:
            hist = t.history(period="3mo")
            if hist is not None and len(hist) >= 2:
                last_price = float(hist["Close"].iloc[-1])
                # 30 dager tilbake (~21 handelsdager)
                idx_30 = max(0, len(hist) - 22)
                price_30 = float(hist["Close"].iloc[idx_30])
                price_30d_return = round(((last_price - price_30) / price_30) * 100, 2)
                # 90 dager = hele perioden
                price_90 = float(hist["Close"].iloc[0])
                price_90d_return = round(((last_price - price_90) / price_90) * 100, 2)
        except Exception:
            pass

        # ── Analytiker-anbefalinger (siste 5) ─────────────────────────────────
        recommendations = None
        try:
            df = t.recommendations
            if df is not None and not df.empty:
                recommendations = []
                for _, row in df.head(5).iterrows():
                    recommendations.append({
                        "date":     str(row.name)[:10] if hasattr(row, "name") else "",
                        "firm":     str(row.get("Firm", row.get("firm", ""))),
                        "action":   str(row.get("Action", row.get("action", ""))),
                        "to_grade": str(row.get("To Grade", row.get("toGrade", ""))),
                    })
        except Exception:
            pass

        # ── Guidance ─────────────────────────────────────────────────────────
        guidance_low  = info.get("revenueGuidanceLow")
        guidance_high = info.get("revenueGuidanceHigh")

        # ── Neste rapporteringsdato ───────────────────────────────────────────
        next_earnings = None
        try:
            ed = info.get("earningsDate")
            if ed:
                # earningsDate kan være en liste
                if isinstance(ed, list):
                    next_earnings = str(ed[0])[:10]
                else:
                    next_earnings = str(ed)[:10]
        except Exception:
            pass

        return {
            "ticker":               ticker,
            "company_name":         company_name,
            "currency":             currency,
            "next_earnings":        next_earnings,
            "earnings_estimate":    earnings_estimate,
            "revenue_estimate":     revenue_estimate,
            "price_targets":        price_targets,
            "recommendation":       recommendation,
            "quarterly_financials": quarterly_financials,
            "earnings_history":     earnings_history,
            "price_30d_return":     price_30d_return,
            "price_90d_return":     price_90d_return,
            "recommendations":      recommendations,
            "guidance_low":         guidance_low,
            "guidance_high":        guidance_high,
        }

    def get_peer_multiples(self, tickers: list[str]) -> dict:
        """Henter EV/EBITDA og P/E for en liste av sammenlignbare selskaper."""
        results = {}
        for t in tickers:
            try:
                info = yf.Ticker(t).info or {}
                results[t] = {
                    "company":  info.get("shortName", t),
                    "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
                    "pe_ratio":  _safe_float(info.get("trailingPE")),
                }
            except Exception as e:
                results[t] = {"error": str(e)}
        return results

    # ── Agentic tool-use loop ─────────────────────────────────────────────────

    def run_agent(self, ticker: str) -> tuple[dict, dict]:
        """
        Kjører en agentic tool-use loop der Claude driver hele analyseflyten.
        Returnerer (briefing_dict, data_dict).
        """
        briefing     = {}
        fetched_data = {}

        tools = [
            {
                "name": "get_financial_data",
                "description": (
                    "Henter finansdata for en ticker fra yfinance: EPS-estimater, "
                    "omsetningsestimater, kursmål, analytiker-anbefalinger, "
                    "kvartalsvise finanstall og beat/miss-historikk."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Ticker-symbol, f.eks. EQNR.OL eller CVX"}
                    },
                    "required": ["ticker"],
                },
            },
            {
                "name": "get_peer_multiples",
                "description": (
                    "Henter EV/EBITDA og P/E for en liste av sammenlignbare selskaper. "
                    "Bruk dette for å kontekstualisere verdivurderingen av hovedselskapet."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste med ticker-symboler for peer-selskaper",
                        }
                    },
                    "required": ["tickers"],
                },
            },
            {
                "type": "web_search_20250305",
                "name": "web_search",
            },
            {
                "name": "write_briefing_section",
                "description": (
                    "Skriv én seksjon av earnings briefingen. Kall dette én gang per seksjon "
                    "etter at du har analysert relevante data. Alle 7 seksjoner må skrives."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "enum": [
                                "executive_summary",
                                "consensus_view",
                                "historical_performance",
                                "what_to_watch",
                                "key_risks",
                                "ma_angle",
                                "questions_for_management",
                                "sources_consulted",
                            ],
                            "description": "Navnet på seksjonen som skal skrives",
                        },
                        "content": {
                            "description": (
                                "Innholdet i seksjonen. Bruk streng for tekstfelter, "
                                "liste for what_to_watch/key_risks/questions_for_management, "
                                "og objekt for consensus_view og historical_performance."
                            ),
                        },
                    },
                    "required": ["section", "content"],
                },
            },
        ]

        messages = [
            {
                "role": "user",
                "content": f"Lag en komplett earnings briefing for {ticker}.",
            }
        ]

        MAX_ITERATIONS = 25
        iteration = 0
        while True:
            iteration += 1
            print(f"[EarningsAgent] Iterasjon {iteration}")

            if iteration > MAX_ITERATIONS:
                print(f"[EarningsAgent] Maks iterasjoner ({MAX_ITERATIONS}) nådd — avbryter loop")
                break

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                # Forsøk å hente supplerende JSON fra siste tekstblokk
                for block in reversed(response.content):
                    if hasattr(block, "text") and block.text.strip():
                        try:
                            raw = block.text.strip()
                            if "```" in raw:
                                raw = raw.split("```")[1]
                                if raw.startswith("json"):
                                    raw = raw[4:]
                                raw = raw.split("```")[0]
                            parsed = json.loads(raw.strip())
                            briefing.update(parsed)
                        except Exception:
                            pass
                        break
                return briefing if briefing else self._fallback_briefing(ticker), fetched_data

            elif response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"[EarningsAgent] Tool call: {block.name}({json.dumps(block.input, ensure_ascii=False)})")
                        result = self._execute_tool(block.name, block.input, briefing, fetched_data)
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     json.dumps(result, ensure_ascii=False),
                        })
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
            else:
                print(f"[EarningsAgent] Uventet stop_reason '{response.stop_reason}' — avbryter loop")
                break

        return briefing if briefing else self._fallback_briefing(ticker), fetched_data

    def _execute_tool(self, name: str, inputs: dict, briefing: dict, fetched_data: dict) -> dict:
        """Dispatcher for klient-side verktøy. web_search håndteres nativt av Anthropic."""
        if name == "get_financial_data":
            data = self.fetch_earnings_data(inputs["ticker"])
            fetched_data.update(data)
            return data

        if name == "get_peer_multiples":
            return self.get_peer_multiples(inputs["tickers"])

        if name == "write_briefing_section":
            briefing[inputs["section"]] = inputs["content"]
            return {"ok": True, "section": inputs["section"]}

        return {"error": f"Ukjent verktøy: {name}"}

    # ── Claude-analyse (beholdt, brukes ikke lenger) ─────────────────────────

    def generate_briefing(self, ticker: str, data: dict) -> dict:
        """
        Sender innsamlet data til Claude og ber om strukturert JSON-analyse.
        Faller tilbake på _fallback_briefing() ved feil.
        """
        company   = data.get("company_name", ticker)
        currency  = data.get("currency", "USD")

        # Bygg kompakt tekst-oppsummering av data
        lines = [f"Selskap: {company} ({ticker})  |  Valuta: {currency}"]

        if data.get("next_earnings"):
            lines.append(f"Rapporteringsdato: {data['next_earnings']}")

        if data.get("revenue_estimate"):
            est = data["revenue_estimate"][0]
            lines.append(
                f"Omsetningsestimat (neste kvartal): {_fmt(est.get('avg_estimate'))} "
                f"[{_fmt(est.get('low'))} – {_fmt(est.get('high'))}], "
                f"{est.get('n_analysts') or '?'} analytikere"
            )

        if data.get("earnings_estimate"):
            est = data["earnings_estimate"][0]
            lines.append(
                f"EPS-estimat (neste kvartal): {_fmt(est.get('avg_estimate'))} "
                f"[{_fmt(est.get('low'))} – {_fmt(est.get('high'))}]"
            )

        if data.get("price_targets"):
            pt = data["price_targets"]
            lines.append(
                f"Kursmål: Gj.snitt {_fmt(pt.get('mean'))}, "
                f"Lav {_fmt(pt.get('low'))}, Høy {_fmt(pt.get('high'))}"
            )

        if data.get("recommendation"):
            lines.append(f"Analytiker-konsensus: {data['recommendation']}")

        if data.get("price_30d_return") is not None:
            lines.append(f"Kursutvikling: +{data['price_30d_return']:.1f}% siste 30 dager, "
                         f"+{data.get('price_90d_return', 0):.1f}% siste 90 dager")

        if data.get("earnings_history"):
            hist_lines = []
            for h in data["earnings_history"]:
                beat = "Beat" if (h.get("eps_actual") or 0) > (h.get("eps_estimate") or 0) else "Miss"
                hist_lines.append(
                    f"{h.get('quarter', '?')}: EPS est {_fmt(h.get('eps_estimate'))} / "
                    f"faktisk {_fmt(h.get('eps_actual'))} → {beat}"
                )
            lines.append("EPS-historikk (siste 4 kv.):\n  " + "\n  ".join(hist_lines))

        if data.get("quarterly_financials"):
            fin_lines = []
            for q in data["quarterly_financials"]:
                rev = q.get("revenue")
                ni  = q.get("net_income")
                fin_lines.append(
                    f"{q.get('date', '?')}: Omsetning {_fmt_large(rev)}, "
                    f"Nettoresultat {_fmt_large(ni)}"
                )
            lines.append("Kvartalsvise finanstall:\n  " + "\n  ".join(fin_lines))

        if data.get("guidance_low") or data.get("guidance_high"):
            lines.append(
                f"Selskapets guidance: {_fmt_large(data.get('guidance_low'))} – "
                f"{_fmt_large(data.get('guidance_high'))}"
            )

        data_text = "\n".join(lines)

        next_e = data.get("next_earnings") or ""
        try:
            from datetime import datetime as _dt
            ed = _dt.strptime(next_e[:10], "%Y-%m-%d")
            q_num  = (ed.month - 1) // 3 + 1
            q_year = ed.year
        except Exception:
            q_num, q_year = "?", "?"

        sector_hint = f"{company} sector outlook {q_year}"

        prompt = f"""Du er en erfaren M&A- og equity-analytiker med spesialkompetanse på
nordiske og internasjonale markeder.

Før du analyserer finansdataen nedenfor, bruk web search til å søke etter:
1. "{company} Q{q_num} {q_year} earnings preview"
2. "{sector_hint}" — f.eks. "oil market outlook {q_year}"
3. Eventuelle geopolitiske eller makroøkonomiske hendelser som påvirker sektoren akkurat nå
4. Nylige analytiker-kommentarer om {company}

Integrer det du finner i analysen — ikke ignorer informasjon bare fordi den ikke finnes
i finansdataen nedenfor.

Her er finansdata for {company} ({ticker}) foran kommende kvartalsrapport:

{data_text}

Generer en profesjonell earnings briefing. Svar KUN med dette JSON-formatet,
ingen annen tekst:
{{
  "executive_summary": "3-4 setninger om hva som er viktigst å følge med på — inkluder fersk markedskontekst",
  "consensus_view": {{
    "revenue_estimate": "oppsummering av omsetningsestimater",
    "eps_estimate": "oppsummering av EPS-estimater",
    "sentiment": "bullish/neutral/bearish",
    "key_concern": "hovedbekymring blant analytikere"
  }},
  "historical_performance": {{
    "beat_rate": "X av siste 4 kvartaler",
    "trend": "akselererende/stabil/decelererende vekst",
    "last_quarter_summary": "kort oppsummering av forrige kvartal"
  }},
  "what_to_watch": [
    "Spesifikk ting 1 å følge nøye i rapporten",
    "Spesifikk ting 2",
    "Spesifikk ting 3"
  ],
  "key_risks": [
    "Risiko 1 for dette kvartalet",
    "Risiko 2"
  ],
  "ma_angle": "Er det noe i denne rapporten som kan påvirke M&A-attraktivitet? 2 setninger.",
  "questions_for_management": [
    "Spørsmål 1 du ville stilt på earnings call",
    "Spørsmål 2",
    "Spørsmål 3"
  ],
  "sources_consulted": [
    "Kort beskrivelse av kilde 1 du søkte opp",
    "Kilde 2",
    "Kilde 3"
  ]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{"role": "user", "content": prompt}],
            )

            full_response = ""
            for block in response.content:
                if block.type == "text":
                    full_response += block.text

            raw = full_response.strip()

            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.split("```")[0]

            try:
                return json.loads(raw.strip())
            except json.JSONDecodeError:
                last_brace = raw.rfind("}")
                if last_brace != -1:
                    truncated = raw[: last_brace + 1]
                    return json.loads(truncated)
                raise

        except Exception as e:
            print(f"[EarningsAgent] generate_briefing feilet ({e}) — bruker fallback")
            return self._fallback_briefing(ticker)

    def _fallback_briefing(self, ticker: str) -> dict:
        na = "Data ikke tilgjengelig"
        return {
            "executive_summary": f"Earnings briefing for {ticker} — data ikke tilgjengelig.",
            "consensus_view": {
                "revenue_estimate": na,
                "eps_estimate":     na,
                "sentiment":        "neutral",
                "key_concern":      na,
            },
            "historical_performance": {
                "beat_rate":            na,
                "trend":                na,
                "last_quarter_summary": na,
            },
            "what_to_watch":            [na],
            "key_risks":                [na],
            "ma_angle":                 na,
            "questions_for_management": [na],
        }

    # ── Koordinator ───────────────────────────────────────────────────────────

    def prepare_report(self, ticker: str) -> tuple[dict, bytes]:
        """
        Koordinerer hele flyten: kjør agentic loop → lag PDF.
        Returnerer (briefing_dict, pdf_bytes).
        """
        try:
            briefing, data = self.run_agent(ticker)
        except Exception as e:
            print(f"[EarningsAgent] run_agent feilet ({e}) — bruker fallback")
            briefing = self._fallback_briefing(ticker)
            data     = {}

        # Sikkerhetsnett: hent rådata hvis Claude aldri kalte get_financial_data
        if not data:
            data = self.fetch_earnings_data(ticker)

        from export.earnings_pdf import generate_earnings_pdf
        pdf_bytes = generate_earnings_pdf(ticker, data, briefing)

        return briefing, pdf_bytes


# ── Numeriske helpers ─────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else round(f, 4)   # NaN-sjekk
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.2f}"


def _fmt_large(v) -> str:
    """Formatterer store tall (milliarder/millioner)."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
        if abs(v) >= 1e9:
            return f"{v/1e9:.2f}B"
        if abs(v) >= 1e6:
            return f"{v/1e6:.1f}M"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return "N/A"
