from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class PeerMultiple:
    ticker:        str
    name:          str
    ev_ebitda:     Optional[float]
    ebitda_margin: Optional[float]
    revenue_cagr:  Optional[float]


@dataclass
class CompanySnapshot:
    # ── Identitet ────────────────────────────────────────────
    ticker:               Optional[str]
    company_name:         str
    headquarters:         str
    founded:              Optional[str]

    # ── Kvalitativt (LLM-ekstrahert) ─────────────────────────
    business_description: str = ""
    revenue_drivers:      list[str] = field(default_factory=list)
    geographic_exposure:  dict[str, float] = field(default_factory=dict)
    key_risks:            list[str] = field(default_factory=list)
    why_interesting:      str = ""
    why_not_interesting:  str = ""

    # ── Kvantitativt (yfinance) ──────────────────────────────
    market_cap_mnok:      Optional[float] = None
    ev_ebitda:            Optional[float] = None
    ev_ebit:              Optional[float] = None
    revenue_ttm_mnok:     Optional[float] = None
    ebitda_margin:        Optional[float] = None
    net_debt_ebitda:      Optional[float] = None
    revenue_cagr_3y:      Optional[float] = None

    # ── Peer group ───────────────────────────────────────────
    peers:                list[str]       = field(default_factory=list)
    peer_multiples:       list[PeerMultiple] = field(default_factory=list)

    # ── Metadata ─────────────────────────────────────────────
    source_type:          str             = "unknown"
    generated_at:         str             = field(
                              default_factory=lambda: datetime.now().isoformat()
                          )

    def is_complete(self) -> bool:
        """Sjekker at alle kritiske felt er fylt ut."""
        return all([
            self.business_description,
            self.revenue_drivers,
            self.key_risks,
            self.why_interesting,
            self.why_not_interesting,
        ])