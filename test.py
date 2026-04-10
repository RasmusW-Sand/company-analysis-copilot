from dotenv import load_dotenv
load_dotenv()

from pipeline.snapshot import SnapshotBuilder

builder  = SnapshotBuilder()
snapshot = builder.build("EQNR.OL")

print(f"\n{'='*50}")
print(f"SELSKAP:          {snapshot.company_name}")
print(f"TICKER:           {snapshot.ticker}")
print(f"HOVEDKONTOR:      {snapshot.headquarters}")
print(f"{'='*50}")
print(f"\nBESKRIVELSE:")
print(f"  {snapshot.business_description}")
print(f"\nINNTEKTSDRIVERE:")
for d in snapshot.revenue_drivers:
    print(f"  - {d}")
print(f"\nGEOGRAFISK EKSPONERING:")
for region, andel in snapshot.geographic_exposure.items():
    bar = "█" * int(andel * 20)
    print(f"  {region:<15} {bar} {andel*100:.0f}%")
print(f"\nNØKKELTALL:")
print(f"  Market cap:      {snapshot.market_cap_mnok:,.0f} MNOK" if snapshot.market_cap_mnok else "  Market cap:      N/A")
print(f"  EV/EBITDA:       {snapshot.ev_ebitda}x" if snapshot.ev_ebitda else "  EV/EBITDA:       N/A")
print(f"  EBITDA-margin:   {snapshot.ebitda_margin}%" if snapshot.ebitda_margin else "  EBITDA-margin:   N/A")
print(f"  Netto gjeld/EBITDA: {snapshot.net_debt_ebitda}x" if snapshot.net_debt_ebitda else "  Netto gjeld/EBITDA: N/A")
print(f"  Omsetning CAGR:  {snapshot.revenue_cagr_3y}%" if snapshot.revenue_cagr_3y else "  Omsetning CAGR:  N/A")
print(f"\nPEER GROUP:")
for p in snapshot.peer_multiples:
    print(f"  {p.ticker:<12} EV/EBITDA: {str(p.ev_ebitda)+'x':<8} EBITDA-margin: {str(p.ebitda_margin)+'%' if p.ebitda_margin else 'N/A'}")
print(f"\nRISIKOER:")
for r in snapshot.key_risks:
    print(f"  - {r}")
print(f"\nHVORFOR INTERESSANT:")
print(f"  {snapshot.why_interesting}")
print(f"\nHVORFOR IKKE INTERESSANT:")
print(f"  {snapshot.why_not_interesting}")
print(f"\nKomplett: {snapshot.is_complete()}")