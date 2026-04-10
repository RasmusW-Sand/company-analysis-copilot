import yfinance as yf
from models import CompanySnapshot, PeerMultiple


# Nordisk-orientert peer-database
# Utvid denne etterhvert som du tester flere selskaper
PEER_DB = {
    # Energi
    "EQNR.OL": ["AKRBP.OL", "VAR.OL", "TGS.OL", "SHELL.AS"],
    "AKRBP.OL": ["EQNR.OL", "VAR.OL", "TGS.OL"],

    # Shipping / offshore
    "SDRL.OL":  ["BORR.OL", "VAR.OL", "AKSO.OL"],
    "AKSO.OL":  ["SDRL.OL", "BORR.OL", "SUBC.OL"],

    # Finans
    "DNB.OL":   ["SRBNK.OL", "MING.OL", "SEB-A.ST", "SWED-A.ST"],
    "SRBNK.OL": ["DNB.OL", "MING.OL"],

    # Industri / teknologi
    "KOG.OL":   ["SUBC.OL", "NHY.OL", "AKSO.OL"],
    "OTEC.OL":  ["KAHOT.OL", "BOUVET.OL", "CRAYN.ST"],

    # Sverige
    "VOLV-B.ST": ["TRATON.DE", "HEXA-B.ST", "SAND.ST"],
    "ERIC-B.ST": ["NOK.HE", "ERICB.ST"],
}


class PeerEnricher:
    """
    Bygger peer group og henter multippel-data for hvert peer-selskap.
    Bruker PEER_DB hvis ticker er kjent, ellers bruker LLM-forslag
    fra snapshot.peers.
    """

    def enrich(self, snapshot: CompanySnapshot) -> CompanySnapshot:
        ticker = snapshot.ticker

        # Bruk hardkodet peer-liste hvis tilgjengelig, ellers LLM-forslag
        peer_tickers = PEER_DB.get(ticker, snapshot.peers)

        if not peer_tickers:
            return snapshot

        snapshot.peers          = peer_tickers
        snapshot.peer_multiples = self._fetch_multiples(peer_tickers)

        return snapshot

    def _fetch_multiples(self, tickers: list[str]) -> list[PeerMultiple]:
        multiples = []
        for t in tickers:
            try:
                info = yf.Ticker(t).info
                multiples.append(PeerMultiple(
                    ticker        = t,
                    name          = info.get("shortName", t),
                    ev_ebitda     = self._safe(info.get("enterpriseToEbitda")),
                    ebitda_margin = self._margin(
                        info.get("ebitda"), info.get("totalRevenue")
                    ),
                    revenue_cagr  = None,  # fylles ut i neste iterasjon
                ))
            except Exception as e:
                print(f"Advarsel: kunne ikke hente peer-data for {t}: {e}")

        return multiples

    def _safe(self, value) -> float | None:
        if value is None or value != value:
            return None
        return round(float(value), 1)

    def _margin(self, ebitda, revenue) -> float | None:
        if not ebitda or not revenue:
            return None
        return round((ebitda / revenue) * 100, 1)