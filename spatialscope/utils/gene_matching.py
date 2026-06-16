from __future__ import annotations

from difflib import get_close_matches
from typing import Iterable


def match_gene_name(query: str, candidates: Iterable[str], *, limit: int = 5) -> dict[str, object]:
    names = list(candidates)
    if query in names:
        return {"query": query, "match": query, "score": 100.0, "candidates": [query]}

    lower_map = {name.lower(): name for name in names}
    if query.lower() in lower_map:
        match = lower_map[query.lower()]
        return {"query": query, "match": match, "score": 98.0, "candidates": [match]}

    try:
        from rapidfuzz import process

        results = process.extract(query, names, limit=limit)
        candidates_out = [item[0] for item in results]
        best = results[0] if results else (None, 0)
        return {
            "query": query,
            "match": best[0],
            "score": float(best[1]),
            "candidates": candidates_out,
        }
    except Exception:
        matches = get_close_matches(query, names, n=limit, cutoff=0)
        best = matches[0] if matches else None
        return {
            "query": query,
            "match": best,
            "score": 75.0 if best else 0.0,
            "candidates": matches,
        }

