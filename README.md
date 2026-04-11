# Company Analysis Copilot

AI-drevet selskapsanalyse for nordisk M&A og investorarbeid.
Tar inn ticker, årsrapport (PDF) eller IR-nettside og genererer
en strukturert company snapshot med nøkkeltall, peer comparison og eksport.

## Demo

> Legg inn et skjermbilde her etter du har tatt ett av appen

## Funksjonalitet

- **Tre input-typer** — børsticker (f.eks. `EQNR.OL`), PDF-årsrapport, eller URL til IR-side
- **Kvalitativ extraction** — business description, inntektsdrivere, geografisk eksponering, nøkkelrisikoer
- **Finansielle nøkkeltall** — market cap, EV/EBITDA, EBITDA-margin, netto gjeld/EBITDA, omsetnings-CAGR
- **Peer comparison** — automatisk peer group med multippelsammenlikning
- **PDF-eksport** — 1-side company snapshot klar til å printe eller dele

## Teknisk arkitektur# company-analysis-copilot

## Teknisk arkitektur

Input (ticker / PDF / URL)
↓
Input Router — detekterer type, normaliserer til tekst
↓
LLM Extraction — Claude ekstraherer strukturert info (JSON)
↓
Financial Enrichment — yfinance henter live nøkkeltall
↓
Peer Enrichment — bygger peer group og henter multippeldata
↓
Snapshot Builder — merger alt til én CompanySnapshot
↓
Dashboard + PDF Export — Streamlit UI og ReportLab PDF

## Kom i gang

### Krav

- Python 3.10+
- Anthropic API-nøkkel ([console.anthropic.com](https://console.anthropic.com))

### Installasjon

```bash
git clone https://github.com/RasmusW-Sand/company-analysis-copilot.git
cd company-analysis-copilot
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Konfigurasjon

Lag en `.env`-fil i rotmappen:

### Kjør appen

```bash
streamlit run app.py
```

Åpne [http://localhost:8501](http://localhost:8501) i nettleseren.

## Eksempel-input

| Input      | Beskrivelse                           |
| ---------- | ------------------------------------- |
| `EQNR.OL`  | Equinor — Oslo Børs ticker            |
| `TGS.OL`   | TGS ASA — seismikk og energidata      |
| `KAHOT.OL` | Kahoot — EdTech                       |
| URL        | `https://www.tgs.com/investor-center` |
| PDF        | Last opp årsrapport direkte i appen   |

## Teknologistack

| Lag         | Teknologi          |
| ----------- | ------------------ |
| LLM         | Claude (Anthropic) |
| Finansdata  | yfinance           |
| UI          | Streamlit          |
| PDF-eksport | ReportLab          |
| Datamodell  | Python dataclasses |

## Prosjektstruktur

├── app.py # Streamlit UI
├── models.py # CompanySnapshot dataclass
├── pipeline/
│ ├── router.py # Input-deteksjon og normalisering
│ ├── extractor.py # LLM extraction
│ ├── financials.py # yfinance enrichment
│ ├── peers.py # Peer group og multippeldata
│ └── snapshot.py # Pipeline-koordinator
├── prompts/
│ └── extraction.py # LLM-prompts
└── export/
└── pdf_export.py # 1-side PDF-generering
