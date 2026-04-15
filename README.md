# Company Analysis Copilot

AI-drevet selskapsanalyse og M&A intelligence platform for
nordiske markeder. Bygget for å automatisere arbeidet en
analytiker bruker timer på — fra selskapsanalyse til
deal screening og earnings prep.

## Funksjonalitet

### Selskapsanalyse

- Tre input-typer: børsticker (f.eks. `EQNR.OL`),
  PDF-årsrapport, eller IR-nettside
- LLM-extraction av business description, inntektsdrivere,
  geografisk eksponering og nøkkelrisikoer
- Live finansielle nøkkeltall via yfinance med automatisk
  valutakonvertering til NOK
- Peer comparison med multippeldata
- Investor-vurdering: "hvorfor interessant / ikke interessant"
- PDF-eksport — 1-side company snapshot

### Deal Screening Agent

- Screener 125+ nordiske selskaper på tvers av Oslo Børs,
  Nasdaq Stockholm, Nasdaq Copenhagen og Nasdaq Helsinki
- Filtrer på sektor, land, market cap, EV/EBITDA,
  gjeld/EBITDA og EBITDA-margin
- Parallell datahenting med ThreadPoolExecutor
- AI-rangering av topp oppkjøpskandidater med begrunnelse
- Signal-flagg: lav gjeld, høy kontantbeholdning,
  verdsettelsesrabatt vs sektor
- Ett klikk fra screening til full selskapsanalyse

### Watchlist og Overvåking

- Følg selskaper med automatisk kurs- og nyhetsovervåking
- Claude vurderer om nyheter er vesentlige nok til å varsle
- E-postvarsler med HTML-formatert rapport
- Automatisk daglig kjøring via Windows Task Scheduler
- Kjøring ved PC-oppstart hvis daglig kjøring ble misset

### Earnings Prep Agent

- Genererer profesjonelt briefing-dokument dagen før
  kvartalsrapport
- Henter konsensusestimat, historiske tall og beat/miss-historikk
- Web search-integrasjon — Claude søker aktivt etter
  geopolitisk og makroøkonomisk kontekst
- Vurderer M&A-implikasjoner av rapporten
- Foreslår spørsmål til management
- Sendes automatisk på e-post kvelden før rapport
- 3-siders PDF

### Agent Log

- Full oversikt over alle agent-kjøringer
- Kronologisk logg med status per kjøring
- Arkivering av gamle logger

## Teknisk arkitektur

```
┌─────────────────────────────────────────────────────────┐
│                        INPUT                            │
│         Ticker / PDF-årsrapport / IR-nettside           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
              [ Input Router ]
         Detekterer type, normaliserer
                      │
                      ▼
             [ LLM Extraction ]
          Claude → strukturert JSON
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
  [ Financial Enrichment ] [ Peer Enrichment ]
   yfinance + valutakurs    peer group + multippel
            └─────────┬─────────┘
                      ▼
           [ Snapshot Builder ]
        Merger alt til CompanySnapshot
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
       [ Dashboard ]       [ PDF Export ]
       Streamlit UI        ReportLab 1-side

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    AUTOMATISK OVERVÅKING

[ Task Scheduler ] ──► [ Watchlist Monitor ]
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            [ News Agent ]    [ Earnings Prep Agent ]
          Claude vurderer      Briefing + web search
          nyhetsvesentlighet   geopolitisk kontekst
                    └─────────┬──────────┘
                              ▼
                    [ Email Notifier ]
                   HTML-rapport + PDF-vedlegg

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                      DEAL SCREENING

[ 125+ Nordiske tickere ] ──► [ Screen Universe ]
  Oslo Børs / Nasdaq Nordic    ThreadPoolExecutor
                                      │
                                      ▼
                          [ Enrich Candidates ]
                           M&A signal-flagg
                                      │
                                      ▼
                           [ AI Rangering ]
                          Claude + begrunnelse
                                      │
                                      ▼
                            [ Shortlist UI ]
                         Ett klikk → full analyse
```

## Teknologistack

| Lag              | Teknologi                         |
| ---------------- | --------------------------------- |
| LLM              | Claude (Anthropic) med web search |
| Finansdata       | yfinance                          |
| UI               | Streamlit multi-page              |
| PDF-eksport      | ReportLab                         |
| Datamodell       | Python dataclasses                |
| Parallellisering | ThreadPoolExecutor                |
| Scheduling       | Windows Task Scheduler            |
| Versjonskontroll | Git / GitHub                      |

## Kom i gang

### Krav

- Python 3.10+
- Anthropic API-nøkkel ([console.anthropic.com](https://console.anthropic.com))
- Gmail App Password for e-postvarsler

### Installasjon

```bash
git clone https://github.com/RasmusW-Sand/company-analysis-copilot.git
cd company-analysis-copilot
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Konfigurasjon

Lag `.env` i rotmappen:

ANTHROPIC_API_KEY=sk-ant-...
EMAIL_FROM=din.epost@gmail.com
EMAIL_TO=din.epost@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx

### Kjør appen

```bash
streamlit run app.py
```

### Sett opp automatisk overvåking

```powershell
powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
```

## Prosjektstruktur

```
company-analysis-copilot/
│
├── app.py                          # Entry point — navigasjon
├── 1_Watchlist.py                  # Landing page
├── models.py                       # CompanySnapshot dataclass
├── requirements.txt
│
├── pages/
│   ├── 2_Analyser.py               # Selskapsanalyse
│   ├── 3_Agent_Log.py              # Agent-logg og historikk
│   └── 4_Screening.py             # Deal screening UI
│
├── pipeline/
│   ├── router.py                   # Input-deteksjon og normalisering
│   ├── extractor.py                # LLM extraction → JSON
│   ├── financials.py               # yfinance + valutakonvertering
│   ├── peers.py                    # Peer group og multippeldata
│   └── snapshot.py                 # Pipeline-koordinator
│
├── agents/
│   ├── screening_agent.py          # Deal screening, 125+ tickere
│   └── earnings_agent.py           # Earnings prep + web search
│
├── watchlist/
│   ├── store.py                    # JSON-persistering + cache
│   ├── monitor.py                  # Daglig overvåkingsagent
│   └── notifier.py                 # E-post med PDF-vedlegg
│
├── export/
│   ├── pdf_export.py               # Company snapshot — 1 side
│   └── earnings_pdf.py             # Earnings brief — 3 sider
│
├── prompts/
│   └── extraction.py               # LLM-prompts
│
├── run_monitor.bat                 # Windows bat-script
└── setup_scheduler.ps1             # Task Scheduler oppsett
```
