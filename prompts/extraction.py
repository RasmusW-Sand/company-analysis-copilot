EXTRACTION_PROMPT = """\
Du er en erfaren M&A-analytiker i et nordisk investeringsbankmiljø.

Ekstraher selskapsinformasjon fra teksten nedenfor og returner KUN gyldig JSON.
Ikke skriv noe annet — ingen forklaring, ingen markdown, bare JSON.

TEKST:
{text}

Returner dette skjemaet nøyaktig:
{{
  "company_name": "Fullt selskapsnavn",
  "headquarters": "By, Land",
  "founded": "År eller null",
  "business_description": "2-3 setninger: hva gjør selskapet, hvordan tjener det penger, hva er kjernevirksomheten",
  "revenue_drivers": [
    "Primær inntektsdriver",
    "Sekundær inntektsdriver",
    "Eventuell tredje driver"
  ],
  "geographic_exposure": {{
    "Norge": 0.0,
    "Sverige": 0.0,
    "Europa": 0.0,
    "Nord-Amerika": 0.0,
    "Annet": 0.0
  }},
  "key_risks": [
    "Risiko 1",
    "Risiko 2",
    "Risiko 3"
  ],
  "why_interesting": "1-2 setninger fra perspektivet til en strategisk kjøper eller finansiell investor",
  "why_not_interesting": "1-2 setninger — hva ville gitt en analytiker pause",
  "suggested_peers": ["TICKER1", "TICKER2", "TICKER3"]
}}

REGLER:
- geographic_exposure-verdiene skal summere til nøyaktig 1.0
- Bruk kun informasjon fra teksten — ikke finn opp tall eller fakta
- Hvis du ikke finner informasjon om et felt, bruk null
- suggested_peers skal være reelle børstickere for sammenlignbare selskaper
- Svar alltid på norsk i tekstfeltene
"""