from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .common import raw_event
from .news_keyword_scout import KeywordNewsScoutBase


QUANTUM_TICKERS = ["INFQ", "QBTS", "RGTI", "QUBT", "IONQ", "IBM", "GFS"]
THEME_TERMS = {
    "quantum_computing": {
        "terms": ["quantum", "qubit", "chips", "department of commerce", "commerce department", "government funding", "grant", "equity stake"],
        "basket": QUANTUM_TICKERS,
        "retail_story": "government-backed quantum winners",
    }
}


def detect_theme_baskets(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    for theme, cfg in THEME_TERMS.items():
        matched_events = []
        direct_tickers: set[str] = set()
        combined_text = []
        urls: list[str] = []
        for event in events:
            text = " ".join([str(event.get("headline") or ""), str(event.get("raw_text") or ""), " ".join(str(n) for n in (event.get("notes") or []))]).lower()
            if not any(term in text for term in cfg["terms"]):
                continue
            matched_events.append(event)
            combined_text.append(text)
            urls.extend([str(event.get("source_url"))] if event.get("source_url") else [])
            direct_tickers.update(str(t).upper() for t in (event.get("ticker_candidates") or []) if str(t).strip())
        if not matched_events:
            continue
        basket = [ticker for ticker in cfg["basket"] if ticker in direct_tickers] + [ticker for ticker in cfg["basket"] if ticker not in direct_tickers]
        undercovered = next((ticker for ticker in basket if ticker not in {"IBM", "GFS"}), basket[0])
        best_beta = next((ticker for ticker in basket if ticker in direct_tickers and ticker not in {"IBM", "GFS"}), undercovered)
        strength = min(10.0, 4.0 + len(matched_events) * 1.1 + len(direct_tickers) * 0.6)
        all_text = " ".join(combined_text)
        if "department of commerce" in all_text or "chips" in all_text:
            strength += 1.2
        baskets.append(
            {
                "theme": theme,
                "catalyst": "government funding / policy / grants / equity stake" if "government" in all_text or "chips" in all_text else "sector momentum",
                "theme_strength_0_10": round(min(10.0, strength), 3),
                "freshness": "same_morning",
                "sector_basket": basket,
                "likely_retail_story": cfg["retail_story"],
                "theme_leader": best_beta,
                "best_beta_candidate": best_beta,
                "undercovered_candidate": undercovered,
                "obvious_but_boring_candidate": "IBM" if "IBM" in basket else None,
                "source_urls": sorted(set(urls)),
            }
        )
    return baskets


class ThemeBasketScout(KeywordNewsScoutBase):
    scout_name = "theme_basket_scout"
    catalyst_type = "sector_theme_wave"
    keywords = ("quantum", "chips", "department of commerce", "government funding", "grant", "equity stake")
    credibility_base = 6.8

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        base_events = super().collect(tickers)
        if not base_events:
            return []
        theme_events: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()
        for basket in detect_theme_baskets(base_events):
            symbol = str(basket.get("best_beta_candidate") or "").upper()
            if not symbol:
                continue
            event = raw_event(
                source_name=self.scout_name,
                source_tier=1,
                source_url=(basket.get("source_urls") or ["https://example.com/theme-basket"])[0],
                headline=f"{symbol} sector-theme basket candidate: {basket.get('theme')}",
                raw_text=f"{basket.get('likely_retail_story')} | basket={','.join(basket.get('sector_basket') or [])}",
                company_name=None,
                ticker_candidates=[symbol],
                catalyst_type=self.catalyst_type,
                official_flag=False,
                structured_flag=True,
                social_flag=False,
                credibility_score_initial=7.0,
                extraction_confidence=0.75,
                published_at=now,
                updated_at=now,
                notes=[f"theme={basket.get('theme')}", f"theme_strength={basket.get('theme_strength_0_10')}", f"sector_basket={','.join(basket.get('sector_basket') or [])}", "lesser_known_candidate=true"],
            )
            theme_events.append(event.to_dict())
        return theme_events
