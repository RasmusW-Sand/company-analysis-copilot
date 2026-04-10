from models import CompanySnapshot
from pipeline.router import InputRouter
from pipeline.extractor import Extractor
from pipeline.financials import FinancialEnricher
from pipeline.peers import PeerEnricher


class SnapshotBuilder:
    """
    Koordinerer hele pipelinen:
    Input → Router → Extractor → FinancialEnricher → PeerEnricher → CompanySnapshot
    """

    def __init__(self):
        self.router    = InputRouter()
        self.extractor = Extractor()
        self.financials = FinancialEnricher()
        self.peers      = PeerEnricher()

    def build(self, user_input: str) -> CompanySnapshot:
        # 1. Detekter input-type og hent råtekst
        input_type, raw_text = self.router.route(user_input)

        # Ekstraher ticker fra input hvis det er en ticker
        ticker = user_input.strip().upper() if input_type == "ticker" else None

        print(f"Input type: {input_type}")
        print(f"Ekstrahere kvalitativ info...")

        # 2. LLM-extraction → kvalitative felt
        snapshot = self.extractor.extract(raw_text, input_type, ticker=ticker)

        print(f"Henter finansdata...")

        # 3. yfinance → kvantitative felt
        snapshot = self.financials.enrich(snapshot)

        print(f"Bygger peer group...")

        # 4. Peer group + multippel
        snapshot = self.peers.enrich(snapshot)

        print(f"Ferdig.")

        return snapshot