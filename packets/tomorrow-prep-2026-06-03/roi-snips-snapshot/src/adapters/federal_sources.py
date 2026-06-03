"""Federal catalyst adapters for SAM.gov, USAspending, ClinicalTrials, and OpenFDA."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json, http_post_json


class SamGovAdapter:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.sam.gov") -> None:
        self.api_key = api_key or os.getenv("SAM_GOV_API_KEY")
        self.base_url = os.getenv("SAM_GOV_BASE_URL", base_url).rstrip("/")

    def search_opportunities(self, *, query: str, limit: int = 25) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "reason": "missing_sam_gov_api_key", "opportunities": []}
        res = http_get_json(f"{self.base_url}/opportunities/v2/search", params={"api_key": self.api_key, "q": query, "limit": limit})
        if not res.ok:
            return {"ok": False, "reason": "sam_gov_http_error", "status": res.status, "error": res.error, "opportunities": []}
        rows = (res.data or {}).get("opportunitiesData") or []
        return {"ok": True, "opportunities": rows, "count": len(rows)}


class UsaSpendingAdapter:
    def __init__(self, base_url: str = "https://api.usaspending.gov/api/v2") -> None:
        self.base_url = os.getenv("USASPENDING_BASE_URL", base_url).rstrip("/")

    def search_awards(self, *, query: str, limit: int = 25) -> dict[str, Any]:
        payload = {"filters": {"keywords": [query]}, "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "Awarding Agency"], "page": 1, "limit": limit, "sort": "Start Date", "order": "desc"}
        res = http_post_json(f"{self.base_url}/search/spending_by_award/", payload)
        if not res.ok:
            return {"ok": False, "reason": "usaspending_http_error", "status": res.status, "error": res.error, "awards": []}
        rows = ((res.data or {}).get("results") or [])
        return {"ok": True, "awards": rows, "count": len(rows)}


class ClinicalTrialsAdapter:
    def __init__(self, base_url: str = "https://clinicaltrials.gov/api/v2") -> None:
        self.base_url = os.getenv("CLINICALTRIALS_BASE_URL", base_url).rstrip("/")

    def search_studies(self, *, query: str, limit: int = 25) -> dict[str, Any]:
        res = http_get_json(f"{self.base_url}/studies", params={"query.term": query, "pageSize": limit})
        if not res.ok:
            return {"ok": False, "reason": "clinicaltrials_http_error", "status": res.status, "error": res.error, "studies": []}
        rows = (res.data or {}).get("studies") or []
        return {"ok": True, "studies": rows, "count": len(rows)}


class OpenFdaAdapter:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.fda.gov") -> None:
        self.api_key = api_key or os.getenv("OPENFDA_API_KEY")
        self.base_url = os.getenv("OPENFDA_BASE_URL", base_url).rstrip("/")

    def search_drug_events(self, *, query: str, limit: int = 25) -> dict[str, Any]:
        params: dict[str, Any] = {"search": query, "limit": limit}
        if self.api_key:
            params["api_key"] = self.api_key
        res = http_get_json(f"{self.base_url}/drug/event.json", params=params)
        if not res.ok:
            return {"ok": False, "reason": "openfda_http_error", "status": res.status, "error": res.error, "events": []}
        rows = (res.data or {}).get("results") or []
        return {"ok": True, "events": rows, "count": len(rows)}
