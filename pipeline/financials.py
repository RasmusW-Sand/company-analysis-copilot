import yfinance as yf
import pandas as pd
from functools import lru_cache
from models import CompanySnapshot


class FinancialEnricher:

    @lru_cache(maxsize=32)
    def _get_fx_to_nok(self, currency: str) -> float:
        """
        Henter live valutakurs til NOK via yfinance.
        lru_cache sørger for at samme valuta bare hentes én gang per kjøring.
        """
        if currency == "NOK":
            return 1.0

        pair = f"{currency}NOK=X"
        try:
            ticker = yf.Ticker(pair)
            rate = ticker.fast_info.get("lastPrice") or ticker.fast_info.last_price
            if rate and rate > 0:
                return float(rate)
        except Exception:
            pass

        # Fallback: prøv via EUR som bro hvis direkte par ikke finnes
        try:
            to_eur   = yf.Ticker(f"{currency}EUR=X").fast_info.last_price
            eur_nok  = yf.Ticker("EURNOK=X").fast_info.last_price
            if to_eur and eur_nok:
                return float(to_eur * eur_nok)
        except Exception:
            pass

        print(f"Advarsel: fant ikke kurs for {currency}/NOK — bruker 1.0")
        return 1.0

    def enrich(self, snapshot: CompanySnapshot) -> CompanySnapshot:
        if not snapshot.ticker:
            return snapshot

        try:
            stock    = yf.Ticker(snapshot.ticker)
            info     = stock.info
            currency = info.get("currency", "USD")
            fx       = self._get_fx_to_nok(currency)

            print(f"  Valuta: {currency} → kurs mot NOK: {fx:.4f}")

            snapshot.market_cap_mnok  = self._to_mnok(info.get("marketCap"), fx)
            snapshot.revenue_ttm_mnok = self._to_mnok(info.get("totalRevenue"), fx)
            snapshot.ev_ebitda        = self._safe(info.get("enterpriseToEbitda"))
            snapshot.ev_ebit          = self._safe(info.get("enterpriseToRevenue"))
            snapshot.ebitda_margin    = self._margin(
                info.get("ebitda"), info.get("totalRevenue")
            )
            snapshot.net_debt_ebitda  = self._net_debt_ebitda(info)
            snapshot.revenue_cagr_3y  = self._cagr(stock)

        except Exception as e:
            print(f"Advarsel: kunne ikke hente finansdata for "
                  f"{snapshot.ticker}: {e}")

        return snapshot

    # ── Hjelpemetoder ────────────────────────────────────────

    def _to_mnok(self, value, fx: float) -> float | None:
        if value is None:
            return None
        return round((value * fx) / 1_000_000, 1)

    def _safe(self, value) -> float | None:
        if value is None or value != value:
            return None
        return round(float(value), 1)

    def _margin(self, ebitda, revenue) -> float | None:
        if not ebitda or not revenue:
            return None
        return round((ebitda / revenue) * 100, 1)

    def _net_debt_ebitda(self, info: dict) -> float | None:
        total_debt = info.get("totalDebt", 0) or 0
        cash       = info.get("totalCash", 0) or 0
        ebitda     = info.get("ebitda")
        if not ebitda or ebitda == 0:
            return None
        net_debt = total_debt - cash
        return round(net_debt / ebitda, 1)

    def _cagr(self, stock) -> float | None:
        try:
            financials = stock.financials
            if financials is None or financials.empty:
                return None

            financials = financials.sort_index(axis=1, ascending=False)

            revenue_row = None
            for label in ["Total Revenue", "Revenue"]:
                if label in financials.index:
                    revenue_row = financials.loc[label]
                    break

            if revenue_row is None or len(revenue_row) < 4:
                return None

            newest = float(revenue_row.iloc[0])
            oldest = float(revenue_row.iloc[3])

            if oldest <= 0:
                return None

            cagr = ((newest / oldest) ** (1 / 3) - 1) * 100
            return round(cagr, 1)

        except Exception:
            return None