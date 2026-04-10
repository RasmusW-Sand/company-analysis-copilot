import re
import pathlib
import requests
from bs4 import BeautifulSoup


class InputRouter:
    """
    Tar inn det brukeren gir — ticker, URL, eller PDF-filsti —
    og returnerer (input_type, raw_text) som extractor kan jobbe med.
    """

    def route(self, user_input: str) -> tuple[str, str]:
        """
        Returnerer ("ticker" | "url" | "pdf", råtekst).
        Kaster ValueError hvis input ikke kan tolkes.
        """
        cleaned = user_input.strip()

        if self._is_pdf(cleaned):
            return "pdf", self._extract_pdf(cleaned)

        if self._is_url(cleaned):
            return "url", self._scrape_url(cleaned)

        if self._is_ticker(cleaned):
            return "ticker", self._ticker_to_text(cleaned)

        raise ValueError(
            f"Klarte ikke tolke input: '{cleaned}'. "
            "Forventet ticker (f.eks. EQNR), URL, eller sti til PDF."
        )

    # ── Type-deteksjon ───────────────────────────────────────

    def _is_pdf(self, s: str) -> bool:
        return s.lower().endswith(".pdf") and pathlib.Path(s).exists()

    def _is_url(self, s: str) -> bool:
        return re.match(r"https?://", s) is not None

    def _is_ticker(self, s: str) -> bool:
        # Ticker: 1-6 store bokstaver, ev. med .OL / .ST / .HE / .CO suffix
        return bool(re.match(r"^[A-Z]{1,6}(\.(OL|ST|HE|CO))?$", s.upper()))

    # ── Ekstraksjon per type ─────────────────────────────────

    def _extract_pdf(self, path: str) -> str:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("Installer pdfplumber: pip install pdfplumber")

        text_parts = []
        with pdfplumber.open(path) as pdf:
            # Les maks 30 sider — nok for de fleste årsrapporter
            for page in pdf.pages[:30]:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            raise ValueError(f"Kunne ikke ekstrahere tekst fra PDF: {path}")

        # Begrens til ~12 000 tokens for å holde oss innenfor kontekstvindu
        return full_text[:48000]

    def _scrape_url(self, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        # Prøv original URL først
        urls_to_try = [url]

        # Hvis URL ser ut som en IR-side, legg til vanlige alternativer
        if any(x in url for x in ["investor", "ir", "relations"]):
            base = url.rstrip("/").rsplit("/", 1)[0]
            urls_to_try += [
                base + "/investor-center",
                base + "/investors",
                base + "/ir",
                base,  # fallback til hovedside
            ]

        last_error = None
        for attempt_url in urls_to_try:
            try:
                resp = requests.get(attempt_url, headers=headers, timeout=15)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                main = soup.find("main") or soup.find("article") or soup.body
                text = main.get_text(separator="\n", strip=True) if main else ""

                if len(text) > 200:
                    print(f"Hentet tekst fra: {attempt_url}")
                    return text[:48000]

            except requests.RequestException as e:
                last_error = e
                continue

        raise ValueError(
            f"Klarte ikke hente innhold fra noen URL-varianter av {url}. "
            f"Siste feil: {last_error}. "
            "Tips: prøv ticker-input istedenfor URL, eller last opp årsrapport som PDF."
        )

    def _ticker_to_text(self, ticker: str) -> str:
        """
        For ticker-input henter vi company description fra yfinance
        og formaterer det som strukturert tekst extractor kan lese.
        Den kvantitative dataen hentes separat i financials.py.
        """
        import yfinance as yf

        stock = yf.Ticker(ticker.upper())
        info = stock.info

        if not info or "longName" not in info:
            raise ValueError(
                f"Fant ingen data for ticker '{ticker}'. "
                "Sjekk at ticker er korrekt (f.eks. EQNR.OL for Oslo Børs)."
            )

        # Bygg en strukturert tekstblokk LLM-en kan lese godt
        lines = [
            f"Selskap: {info.get('longName', ticker)}",
            f"Sektor: {info.get('sector', 'Ukjent')}",
            f"Bransje: {info.get('industry', 'Ukjent')}",
            f"Hovedkontor: {info.get('city', '')}, {info.get('country', '')}",
            f"Ansatte: {info.get('fullTimeEmployees', 'N/A')}",
            "",
            "Beskrivelse:",
            info.get("longBusinessSummary", "Ingen beskrivelse tilgjengelig."),
        ]

        return "\n".join(lines)