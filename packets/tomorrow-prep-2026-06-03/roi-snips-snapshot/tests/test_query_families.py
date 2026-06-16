from src.research.query_families import generate_query_plan


def test_query_plan_includes_broad_families_and_ticker_enrichment() -> None:
    rows = generate_query_plan(["INFQ"])
    families = {row["family"] for row in rows}
    queries = [row["query"] for row in rows]

    assert {"general_premarket", "government_policy_contract", "biotech_fda"}.issubset(families)
    assert any("INFQ" in query and "8-K" in query for query in queries)
    assert len(queries) == len(set(q.lower() for q in queries))
