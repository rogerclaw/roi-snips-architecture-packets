from __future__ import annotations

import os
from typing import Any

from ...adapters.federal_sources import ClinicalTrialsAdapter, OpenFdaAdapter, SamGovAdapter, UsaSpendingAdapter
from ...adapters.fmp_market_data import FmpMarketDataAdapter
from ...adapters.stocktwits_stream import StockTwitsStreamAdapter
from ...adapters.tradingview_screener import TradingViewScreenerAdapter
from .common import raw_event


class ExternalMoversScout:
    """Discovery scout for FMP movers, TradingView-style screeners, and StockTwits attention."""

    def __init__(
        self,
        fmp: FmpMarketDataAdapter | None = None,
        stocktwits: StockTwitsStreamAdapter | None = None,
        tradingview: TradingViewScreenerAdapter | None = None,
        max_stocktwits_enrichment: int | None = None,
    ) -> None:
        self.fmp = fmp or FmpMarketDataAdapter()
        self.stocktwits = stocktwits or StockTwitsStreamAdapter()
        self.tradingview = tradingview or TradingViewScreenerAdapter()
        self.max_stocktwits_enrichment = int(max_stocktwits_enrichment or os.getenv("ROI_SNIPS_MAX_STOCKTWITS_ENRICHMENT", "8"))

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        requested = sorted({str(t).upper() for t in (tickers or []) if str(t).strip()})
        symbols: dict[str, dict[str, Any]] = {}
        degraded: list[str] = []

        fmp_res = self.fmp.fetch_movers()
        if fmp_res.get("ok"):
            for row in fmp_res.get("events") or []:
                symbol = str(row.get("symbol") or "").upper()
                if symbol and (not requested or symbol in requested):
                    symbols.setdefault(symbol, {})["fmp"] = row
        else:
            degraded.append(str(fmp_res.get("reason") or "fmp_unavailable"))

        tv_res = self.tradingview.fetch_us_movers()
        if tv_res.get("ok"):
            for row in tv_res.get("rows") or []:
                symbol = str(row.get("symbol") or "").upper()
                if symbol and (not requested or symbol in requested):
                    symbols.setdefault(symbol, {})["tradingview"] = row
        else:
            degraded.append(str(tv_res.get("reason") or "tradingview_unavailable"))

        if requested and not symbols:
            symbols = {symbol: {} for symbol in requested}

        events: list[dict[str, Any]] = []
        for idx, (symbol, source_rows) in enumerate(list(symbols.items())[:40]):
            if idx < self.max_stocktwits_enrichment:
                st_res = self.stocktwits.fetch_symbol_stream(symbol, limit=20)
            else:
                st_res = {"ok": False, "reason": "stocktwits_enrichment_budget_exhausted", "messages": []}
            messages = st_res.get("messages") or []
            bullish = sum(1 for msg in messages if str(msg.get("sentiment") or "").lower() == "bullish")
            bearish = sum(1 for msg in messages if str(msg.get("sentiment") or "").lower() == "bearish")
            if not st_res.get("ok"):
                degraded.append(f"{symbol}:{st_res.get('reason')}")
            fmp_row = source_rows.get("fmp") or {}
            tv_row = source_rows.get("tradingview") or {}
            headline = f"{symbol} external mover candidate"
            if fmp_row.get("change_percent") is not None:
                headline = f"{symbol} FMP mover change={fmp_row.get('change_percent')}"
            elif tv_row.get("relative_volume") is not None:
                headline = f"{symbol} TradingView-style relative-volume mover={tv_row.get('relative_volume')}"
            notes = [
                "scout=external_movers_scout",
                f"fmp_present={bool(fmp_row)}",
                f"tradingview_present={bool(tv_row)}",
                f"stocktwits_messages={len(messages)}",
                f"stocktwits_bullish={bullish}",
                f"stocktwits_bearish={bearish}",
            ]
            notes.extend(f"degraded={reason}" for reason in degraded[:5])
            events.append(
                raw_event(
                    source_name="external_movers_scout",
                    source_tier=1,
                    source_url=f"https://finance.yahoo.com/quote/{symbol}",
                    headline=headline,
                    raw_text=str({"fmp": fmp_row, "tradingview": tv_row, "stocktwits_sample": messages[:3]}),
                    company_name=fmp_row.get("name") or tv_row.get("description"),
                    ticker_candidates=[symbol],
                    catalyst_type="exchange_mover",
                    official_flag=False,
                    structured_flag=True,
                    social_flag=bool(messages),
                    credibility_score_initial=6.1 + min(1.2, len(messages) * 0.05),
                    extraction_confidence=0.72,
                    notes=notes,
                ).to_dict()
            )
        return events


class FederalCatalystScout:
    """Evidence scout for government award and biotech/regulatory databases."""

    def __init__(
        self,
        sam: SamGovAdapter | None = None,
        usaspending: UsaSpendingAdapter | None = None,
        clinical: ClinicalTrialsAdapter | None = None,
        openfda: OpenFdaAdapter | None = None,
        enabled: bool | None = None,
    ) -> None:
        injected = any(item is not None for item in [sam, usaspending, clinical, openfda])
        self.enabled = injected if enabled is None else enabled
        if enabled is None and not injected:
            self.enabled = os.getenv("ROI_SNIPS_ENABLE_FEDERAL_CATALYST_SCOUT", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.sam = sam or SamGovAdapter()
        self.usaspending = usaspending or UsaSpendingAdapter()
        self.clinical = clinical or ClinicalTrialsAdapter()
        self.openfda = openfda or OpenFdaAdapter()

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        symbols = sorted({str(t).upper() for t in (tickers or []) if str(t).strip()})[:20]
        if not symbols:
            return []
        events: list[dict[str, Any]] = []
        for symbol in symbols:
            sam_res = self.sam.search_opportunities(query=symbol, limit=10)
            usa_res = self.usaspending.search_awards(query=symbol, limit=10)
            clinical_res = self.clinical.search_studies(query=symbol, limit=10)
            fda_res = self.openfda.search_drug_events(query=symbol, limit=10)
            government_hits = len(sam_res.get("opportunities") or []) + len(usa_res.get("awards") or [])
            biotech_hits = len(clinical_res.get("studies") or []) + len(fda_res.get("events") or [])
            if not government_hits and not biotech_hits:
                continue
            catalyst_type = "government_contract" if government_hits >= biotech_hits else "medical_or_biotech"
            notes = [
                "scout=federal_catalyst_scout",
                f"sam_hits={len(sam_res.get('opportunities') or [])}",
                f"usaspending_hits={len(usa_res.get('awards') or [])}",
                f"clinicaltrials_hits={len(clinical_res.get('studies') or [])}",
                f"openfda_hits={len(fda_res.get('events') or [])}",
            ]
            for label, res in [("sam", sam_res), ("usaspending", usa_res), ("clinicaltrials", clinical_res), ("openfda", fda_res)]:
                if not res.get("ok"):
                    notes.append(f"{label}_degraded={res.get('reason')}")
            events.append(
                raw_event(
                    source_name="federal_catalyst_scout",
                    source_tier=1,
                    source_url=f"https://www.google.com/search?q={symbol}+government+award+clinical+trial+FDA",
                    headline=f"{symbol} external federal/regulatory catalyst evidence",
                    raw_text=str({"sam": sam_res, "usaspending": usa_res, "clinicaltrials": clinical_res, "openfda": fda_res})[:4000],
                    company_name=None,
                    ticker_candidates=[symbol],
                    catalyst_type=catalyst_type,
                    official_flag=bool(government_hits or biotech_hits),
                    structured_flag=True,
                    social_flag=False,
                    credibility_score_initial=7.0,
                    extraction_confidence=0.74,
                    notes=notes,
                ).to_dict()
            )
        return events
