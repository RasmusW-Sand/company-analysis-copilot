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
    update_baseline
)
from watchlist.notifier import send_alert


client = Anthropic()


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

        # Sjekk kurs
        price_alert = check_price_movement(entry)
        if price_alert:
            all_alerts.append(price_alert)
            # Oppdater baseline etter varsel
            try:
                new_price = float(yf.Ticker(ticker).fast_info.last_price)
                update_baseline(ticker, new_price)
            except Exception:
                pass

        # Sjekk nyheter via Claude
        news_alert = check_news(entry)
        if news_alert:
            all_alerts.append(news_alert)

        # Sjekk kommende kvartalsrapport
        earnings_alert = check_earnings_upcoming(entry)
        if earnings_alert:
            all_alerts.append(earnings_alert)

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