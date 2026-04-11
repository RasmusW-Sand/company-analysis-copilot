import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def send_alert(subject: str, alerts: list[dict]) -> None:
    """
    Sender e-postvarsel med en liste av triggers som har gått av.
    alerts = [{"ticker": ..., "company": ..., "trigger": ..., "detail": ...}]
    """
    email_from    = os.getenv("EMAIL_FROM")
    email_to      = os.getenv("EMAIL_TO")
    email_password= os.getenv("EMAIL_PASSWORD")

    if not all([email_from, email_to, email_password]):
        print("E-post ikke konfigurert — sjekk .env")
        return

    # Bygg HTML-epost
    html = _build_html(alerts)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_from
    msg["To"]      = email_to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_from, email_password)
            server.sendmail(email_from, email_to, msg.as_string())
        print(f"Varsel sendt til {email_to}")
    except Exception as e:
        print(f"Kunne ikke sende e-post: {e}")


def _build_html(alerts: list[dict]) -> str:
    rows = ""
    for a in alerts:
        rows += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #eee;font-weight:600;">
                {a['ticker']}
            </td>
            <td style="padding:10px;border-bottom:1px solid #eee;">
                {a['company']}
            </td>
            <td style="padding:10px;border-bottom:1px solid #eee;color:#b45309;">
                {a['trigger']}
            </td>
            <td style="padding:10px;border-bottom:1px solid #eee;">
                {a['detail']}
            </td>
        </tr>
        """

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#212529;">
        <h2 style="color:#0f2d4a;">Company Analysis Copilot — Watchlist-varsel</h2>
        <p>{datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#0f2d4a;color:white;">
                    <th style="padding:10px;text-align:left;">Ticker</th>
                    <th style="padding:10px;text-align:left;">Selskap</th>
                    <th style="padding:10px;text-align:left;">Trigger</th>
                    <th style="padding:10px;text-align:left;">Detalj</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="color:#6c757d;font-size:12px;margin-top:20px;">
            Company Analysis Copilot · Kun til informasjonsformål
        </p>
    </body></html>
    """