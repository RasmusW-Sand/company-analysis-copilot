import json
import os
from anthropic import Anthropic
from models import CompanySnapshot
from prompts.extraction import EXTRACTION_PROMPT


class Extractor:
    """
    Tar råtekst fra InputRouter og returnerer en delvis utfylt
    CompanySnapshot med alle kvalitative felt.
    Kvantitative felt (market_cap, EV/EBITDA osv.) fylles ut
    av financials.py.
    """

    def __init__(self):
        self.client = Anthropic()  # leser ANTHROPIC_API_KEY fra env

    def extract(
        self,
        raw_text: str,
        source_type: str,
        ticker: str | None = None,
    ) -> CompanySnapshot:

        prompt = EXTRACTION_PROMPT.format(text=raw_text)

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_json = response.content[0].text.strip()
        data = self._parse_response(raw_json)

        return CompanySnapshot(
            ticker=ticker,
            company_name=data.get("company_name", "Ukjent"),
            headquarters=data.get("headquarters", "Ukjent"),
            founded=data.get("founded"),
            business_description=data.get("business_description", ""),
            revenue_drivers=data.get("revenue_drivers", []),
            geographic_exposure=self._normalize_geo(
                data.get("geographic_exposure", {})
            ),
            key_risks=data.get("key_risks", []),
            why_interesting=data.get("why_interesting", ""),
            why_not_interesting=data.get("why_not_interesting", ""),
            peers=data.get("suggested_peers", []),
            source_type=source_type,
        )

    def _parse_response(self, raw: str) -> dict:
        """
        Robust JSON-parsing — håndterer tilfeller der LLM-en
        pakker svaret i markdown-kodeblokker.
        """
        # Fjern evt. ```json ... ``` wrapper
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returnerte ugyldig JSON.\n"
                f"Feil: {e}\n"
                f"Råsvar (første 500 tegn): {raw[:500]}"
            )

    def _normalize_geo(self, geo: dict) -> dict:
        """
        Sørger for at geografisk eksponering summerer til 1.0.
        Runder av og justerer største post hvis nødvendig.
        """
        if not geo:
            return {}

        total = sum(geo.values())
        if total == 0:
            return geo

        normalized = {k: round(v / total, 3) for k, v in geo.items()}

        # Fikser avrundingsfeil ved å justere største post
        diff = 1.0 - sum(normalized.values())
        if diff != 0:
            largest = max(normalized, key=normalized.get)
            normalized[largest] = round(normalized[largest] + diff, 3)

        return normalized