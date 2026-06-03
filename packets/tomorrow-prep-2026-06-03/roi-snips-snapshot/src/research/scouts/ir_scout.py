from __future__ import annotations

from .news_keyword_scout import KeywordNewsScoutBase


class IRScout(KeywordNewsScoutBase):
    scout_name = "ir_scout"
    catalyst_type = "product_or_partnership"
    keywords = (
        "announces",
        "launches",
        "partnership",
        "collaboration",
        "contract",
        "letter of intent",
        "loi",
        "funding",
        "grant",
        "guidance",
        "preliminary results",
        "investor day",
        "investor event",
        "symposium",
        "fireside",
        "fireside chat",
        "conference call",
        "webcast",
        "presentation",
        "commercial launch",
    )
    credibility_base = 6.6
