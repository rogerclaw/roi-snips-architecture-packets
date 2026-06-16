from __future__ import annotations

from .news_keyword_scout import KeywordNewsScoutBase


class FdaScout(KeywordNewsScoutBase):
    scout_name = "fda_scout"
    catalyst_type = "medical_or_biotech"
    keywords = (
        "fda",
        "phase 1",
        "phase 2",
        "phase 3",
        "trial",
        "clearance",
        "approval",
        "pdufa",
        "nda",
        "bla",
        "fast track",
        "orphan drug",
        "clinical data",
    )
    credibility_base = 6.9
