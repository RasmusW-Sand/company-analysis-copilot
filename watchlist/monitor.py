import os
import sys
from datetime import date
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import yfinance as yf
from anthropic import Anthropic
from watchlist.store import (
    load_watchlist, update_last_checked,
    update_baseline, update_brief_sent,
)
from watchlist.notifier import send_alert


client = Anthropic()


def fetch_price_anchors(ticker: str) -> tuple[float | None, float | None]:
    """Returnerer (forrige_close, dagens_åpning) for en ticker."""
    try:
        info = yf.Ticker(ticker).fast_info
        prev_close = float(info.previous_close) if info.previous_close else None
        today_open = float(info.open) if info.open else None
        return prev_close, today_open
    except Exception as e:
        print(f"Feil ved henting av open/close for {ticker}: {e}")
        return None, None


def check_overnight_gap(entry: dict, prev_close: float, today_open: float) -> dict | None:
    """Sjekker om kursen har hoppet over terskelen fra forrige close til dagens åpning."""
    threshold = entry.get("price_threshold_pct", 5.0)
    change    = ((today_open - prev_close) / prev_close) * 100
    if abs(change) >= threshold:
        direction = "opp" if change > 0 else "ned"
        return {
            "ticker":  entry.get("ticker"),
            "company": entry.get("company_name", entry.get("ticker")),
            "trigger": f"Overnight gap {direction} {abs(change):.1f}%",
            "detail":  f"Forrige close {prev_close:.2f} → åpning {today_open:.2f}",
        }
    return None


def check_price_movement(entry: dict) -> dict | None:
    """Sjekker om kursen har beveget seg mer enn terskelen."""
    ticker    = entry.get("ticker")
    baseline  = entry.get("baseline_price")
    threshold = entry.get("price_threshold_pct", 5.0)

    if not ticker or not baseline:
        return None

    try:
        current = float(yf.Ticker(ticker).fast_info.last_price)
        change  = ((current - baseline) / baseline) * 100

        if abs(change) >= threshold:
            direction = "opp" if change > 0 else "ned"
            return {
                "ticker":  ticker,
                "company": entry.get("company_name", ticker),
                "trigger": f"Kursendring {direction} {abs(change):.1f}%",
                "detail":  f"Fra {baseline:.2f} → {current:.2f}",
            }
    except Exception as e:
        print(f"Feil ved prissjekk for {ticker}: {e}")

    return None


def check_news(entry: dict) -> dict | None:
    """
    Bruker Claude som agent til å vurdere om siste nyheter
    er vesentlige nok til å varsle om.
    """
    ticker  = entry.get("ticker")
    company = entry.get("company_name", ticker)

    try:
        news = yf.Ticker(ticker).news[:5]
        if not news:
            return None

        headlines = "\n".join([
            f"- {n.get('title', '')} ({n.get('source', '')})"
            for n in news
        ])

        # Claude vurderer om nyhetene er vesentlige
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Du er en M&A-analytiker. Vurder om disse nyhetene om {company} 
er vesentlige nok til å varsle en investor eller analytiker om.

Nyheter:
{headlines}

Svar KUN med dette JSON-formatet:
{{"varsle": true/false, "begrunnelse": "kort forklaring"}}

Varsle hvis: oppkjøp, fusjon, vesentlig kontraktsgevinst, 
lederskifte, profit warning, eller annen kursbevegende hendelse.
Ikke varsle for: rutinemessige oppdateringer, mindre nyheter."""
            }]
        )

        import json
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())

        if result.get("varsle"):
            return {
                "ticker":  ticker,
                "company": company,
                "trigger": "Vesentlig nyhet",
                "detail":  result.get("begrunnelse", ""),
            }

    except Exception as e:
        print(f"Feil ved nyhetssjekk for {ticker}: {e}")

    return None


def check_earnings_upcoming(entry: dict) -> dict | None:
    """Sjekker om selskapet rapporterer i dag eller i morgen."""
    raw = entry.get("next_earnings_date")
    if not raw:
        return None
    try:
        earnings_date = date.fromisoformat(raw)
        today = date.today()
        days_until = (earnings_date - today).days
        if 0 <= days_until <= 1:
            label = "i dag" if days_until == 0 else "i morgen"
            return {
                "ticker":  entry.get("ticker"),
                "company": entry.get("company_name", entry.get("ticker")),
                "trigger": f"Kvartalsrapport {label}",
                "detail":  f"Rapporteringsdato: {earnings_date.isoformat()}",
            }
    except (ValueError, TypeError):
        pass
    return None


def check_and_send_earnings_brief(entry: dict) -> bool:
    """
    Sender earnings brief hvis selskapet rapporterer i morgen.
    Sjekker last_brief_sent for å unngå duplikater samme dag.
    Returnerer True hvis brief ble sendt.
    """
    raw = entry.get("next_earnings_date")
    if not raw:
        return False

    try:
        earnings_date = date.fromisoformat(raw)
        today         = date.today()

        if (earnings_date - today).days != 1:
            return False

        # Duplikat-sjekk: allerede sendt i dag?
        last_sent = entry.get("last_brief_sent")
        if last_sent:
            try:
                if date.fromisoformat(last_sent) == today:
                    print(f"  -> Brief allerede sendt i dag for {entry.get('ticker')}")
                    return False
            except ValueError:
                pass

        ticker       = entry.get("ticker")
        company_name = entry.get("company_name", ticker)
        print(f"  -> Genererer earnings brief for {ticker}...")

        from agents.earnings_agent import EarningsAgent
        from watchlist.notifier import send_earnings_brief

        agent             = EarningsAgent()
        briefing, pdf_bytes = agent.prepare_report(ticker)

        send_earnings_brief(
            ticker=ticker,
            company_name=company_name,
            report_date=raw,
            pdf_bytes=pdf_bytes,
            executive_summary=briefing.get("executive_summary", ""),
        )
        update_brief_sent(ticker, today.isoformat())
        return True

    except Exception as e:
        print(f"Feil ved generering av earnings brief for {entry.get('ticker')}: {e}")
        return False


def run_monitor() -> None:
    """
    Kjører gjennom hele watchlisten og sender
    samlet varsel hvis noe har utløst en trigger.
    """
    watchlist = load_watchlist()

    if not watchlist:
        print("Watchlist er tom.")
        return

    print(f"Sjekker {len(watchlist)} selskaper...")
    all_alerts = []

    for entry in watchlist:
        ticker = entry.get("ticker")
        print(f"  -> {ticker}")

        # Oppdater baseline til mest ferske ankerpris (åpning > forrige close)
        prev_close, today_open = fetch_price_anchors(ticker)
        anchor = today_open or prev_close
        if anchor:
            entry["baseline_price"] = anchor
            update_baseline(ticker, anchor)

        # Sjekk overnight gap (forrige close → dagens åpning)
        if prev_close and today_open:
            gap_alert = check_overnight_gap(entry, prev_close, today_open)
            if gap_alert:
                all_alerts.append(gap_alert)

        # Sjekk intradag kursbevegelse fra åpningspris
        price_alert = check_price_movement(entry)
        if price_alert:
            all_alerts.append(price_alert)

        # Sjekk nyheter via Claude
        news_alert = check_news(entry)
        if news_alert:
            all_alerts.append(news_alert)

        # Sjekk kommende kvartalsrapport
        earnings_alert = check_earnings_upcoming(entry)
        if earnings_alert:
            all_alerts.append(earnings_alert)

        # Send earnings brief kvelden før rapport
        brief_sent = check_and_send_earnings_brief(entry)
        if brief_sent:
            all_alerts.append({
                "ticker":  ticker,
                "company": entry.get("company_name", ticker),
                "trigger": "Earnings brief sendt",
                "detail":  f"Rapporterer {entry.get('next_earnings_date')}",
            })

        update_last_checked(ticker)

    if all_alerts:
        print(f"\n{len(all_alerts)} trigger(e) funnet — sender varsel...")
        send_alert(
            subject=f"Watchlist-varsel: {len(all_alerts)} oppdatering(er)",
            alerts=all_alerts,
        )
    else:
        print("\nIngen vesentlige endringer funnet.")


if __name__ == "__main__":
    run_monitor()