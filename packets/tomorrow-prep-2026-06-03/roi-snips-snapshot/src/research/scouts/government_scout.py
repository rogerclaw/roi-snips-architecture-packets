from __future__ import annotations

from .news_keyword_scout import KeywordNewsScoutBase


class GovernmentScout(KeywordNewsScoutBase):
    scout_name = "government_scout"
    catalyst_type = "government_contract"
    keywords = (
        "award",
        "awards",
        "contract award",
        "letter of intent",
        "loi",
        "funding",
        "grant",
        "grants",
        "chips",
        "chips act",
        "department of commerce",
        "commerce department",
        "department of defense",
        "dod",
        "army",
        "navy",
        "air force",
        "space force",
        "nasa",
        "department of energy",
        "government grant",
        "federal contract",
        "government equity",
        "equity stake",
        "homeland security",
        "quantum",
        "quantum computing",
        "va contract",
    )
    credibility_base = 6.8
