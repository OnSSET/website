#!/usr/bin/env python3
import os
import re
import sys
import time
import json
import pathlib
from typing import Any, Dict, List, Optional, Tuple
import requests
import yaml

BASE = "https://api.openalex.org"
TIMEOUT = 30

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
OUT_MD = DOCS_DIR / "publications.generated.md"

SEEDS_FILE = DATA_DIR / "publications_seeds.yml"

AUTO_START = "<!-- AUTO-GENERATED:START -->"
AUTO_END = "<!-- AUTO-GENERATED:END -->"

def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.lower()
    return doi

def openalex_get(path: str, params: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
    # OpenAlex docs: api_key is passed as a query param. :contentReference[oaicite:1]{index=1}
    if api_key:
        params["api_key"] = api_key
    url = f"{BASE}{path}"
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"OpenAlex {url} failed ({r.status_code}): {r.text[:300]}")
    return r.json()

def find_work_by_doi(doi: str, api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    # Use filter=doi:https://doi.org/...
    doi_url = f"https://doi.org/{normalize_doi(doi)}"
    data = openalex_get(
        "/works",
        params={
            "filter": f"doi:{doi_url}",
            "per-page": 1,
            "select": "id,title,doi,publication_year,primary_location,authorships,cited_by_count,cited_by_api_url"
        },
        api_key=api_key
    )
    results = data.get("results", [])
    return results[0] if results else None

def list_citing_works(cited_by_api_url: str, api_key: Optional[str], max_items: int = 400) -> List[Dict[str, Any]]:
    # cited_by_api_url is a full URL; we can call it with api_key param appended.
    works: List[Dict[str, Any]] = []
    page = 1
    per_page = 200

    while True:
        params = {
            "per-page": per_page,
            "page": page,
            "select": "id,title,doi,publication_year,primary_location,authorships,cited_by_count"
        }
        if api_key:
            params["api_key"] = api_key

        r = requests.get(cited_by_api_url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAlex cited_by failed ({r.status_code}): {r.text[:300]}")

        data = r.json()
        results = data.get("results", [])
        works.extend(results)

        if len(results) < per_page:
            break
        if len(works) >= max_items:
            works = works[:max_items]
            break

        page += 1
        time.sleep(0.2)

    return works

def list_mentions(query: str, api_key: Optional[str], max_items: int = 200) -> List[Dict[str, Any]]:
    # Simple full-text search over works
    results: List[Dict[str, Any]] = []
    page = 1
    per_page = 200

    while True:
        data = openalex_get(
            "/works",
            params={
                "search": query,
                "per-page": per_page,
                "page": page,
                "select": "id,title,doi,publication_year,primary_location,authorships,cited_by_count"
            },
            api_key=api_key
        )
        batch = data.get("results", [])
        results.extend(batch)

        if len(batch) < per_page:
            break
        if len(results) >= max_items:
            results = results[:max_items]
            break
        page += 1
        time.sleep(0.2)

    return results

def short_authors(authorships: List[Dict[str, Any]], max_n: int = 3) -> str:
    names = []
    for a in authorships or []:
        auth = a.get("author", {})
        name = auth.get("display_name")
        if name:
            names.append(name)
    if not names:
        return ""
    if len(names) <= max_n:
        return ", ".join(names)
    return ", ".join(names[:max_n]) + ", et al."

def venue(primary_location: Dict[str, Any]) -> str:
    src = (primary_location or {}).get("source") or {}
    return src.get("display_name") or ""

def doi_link(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    # OpenAlex stores doi as https://doi.org/...
    return doi

def format_entry(w: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": w.get("title") or "",
        "year": w.get("publication_year"),
        "authors": short_authors(w.get("authorships", [])),
        "venue": venue(w.get("primary_location") or {}),
        "doi": doi_link(w.get("doi")),
        "cited_by_count": w.get("cited_by_count", 0),
        "id": w.get("id")
    }

def dedupe(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for w in works:
        key = w.get("doi") or w.get("id") or w.get("title")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out

def sort_works(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def k(w: Dict[str, Any]) -> Tuple[int, int, str]:
        year = w.get("publication_year") or 0
        cited = w.get("cited_by_count") or 0
        title = (w.get("title") or "").lower()
        return (year, cited, title)
    return sorted(works, key=k, reverse=True)

def render_markdown_section(title: str, items: List[Dict[str, Any]]) -> str:
    lines = [f"### {title}", ""]
    if not items:
        lines += ["No results found.", ""]
        return "\n".join(lines)

    for w in items:
        e = format_entry(w)
        t = e["title"].strip() or "Untitled"
        y = e["year"] or ""
        a = e["authors"] or ""
        v = e["venue"] or ""
        doi = e["doi"]
        cited = e["cited_by_count"] or 0

        bits = []
        if a: bits.append(a)
        if v: bits.append(v)
        if y: bits.append(str(y))
        meta = " — ".join(bits)

        if doi:
            lines.append(f"- **{t}**  ")
            lines.append(f"  {meta}  ")
            lines.append(f"  DOI: {doi} · Cited by: {cited}")
        else:
            # fallback to OpenAlex work id
            oid = e["id"] or ""
            link = oid.replace("https://openalex.org/", "https://openalex.org/")
            lines.append(f"- **{t}**  ")
            lines.append(f"  {meta}  ")
            lines.append(f"  OpenAlex: {link} · Cited by: {cited}")
        lines.append("")
    return "\n".join(lines)

def main() -> None:
    if not SEEDS_FILE.exists():
        die(f"Missing {SEEDS_FILE}. Create it first.")

    api_key = os.getenv("OPENALEX_API_KEY")
    if not api_key:
        print("NOTE: OPENALEX_API_KEY not set. Requests may be heavily limited or fail depending on OpenAlex policy.", file=sys.stderr)

    seeds = yaml.safe_load(SEEDS_FILE.read_text(encoding="utf-8")) or {}
    seed_dois = [normalize_doi(d) for d in seeds.get("seed_dois", [])]
    mention_queries = seeds.get("mention_queries", [])

    if not seed_dois:
        die("No seed_dois in publications_seeds.yml")

    citing_all: List[Dict[str, Any]] = []
    seed_info: List[str] = []

    for doi in seed_dois:
        w = find_work_by_doi(doi, api_key=api_key)
        if not w:
            seed_info.append(f"- Seed DOI not found in OpenAlex: {doi}")
            continue

        seed_title = w.get("title", "")
        seed_info.append(f"- Seed: **{seed_title}** (DOI: {w.get('doi')})")

        cited_by_url = w.get("cited_by_api_url")
        if not cited_by_url:
            seed_info.append(f"  - No cited_by_api_url available for: {doi}")
            continue

        citing = list_citing_works(cited_by_url, api_key=api_key)
        citing_all.extend(citing)

    citing_all = dedupe(citing_all)
    citing_all = sort_works(citing_all)

    mentions_all: List[Dict[str, Any]] = []
    for q in mention_queries:
        mentions_all.extend(list_mentions(q, api_key=api_key, max_items=200))

    mentions_all = dedupe(mentions_all)
    mentions_all = sort_works(mentions_all)

    md = []
    md.append("> This section is auto-generated from the OpenAlex citation graph and keyword searches. Coverage may differ from other indexes.")
    md.append("")
    md.append("## Seeds used")
    md.append("")
    md.extend(seed_info)
    md.append("")
    md.append("## Works citing OnSSET seed papers")
    md.append("")
    md.append(render_markdown_section("Citing works (auto)", citing_all[:200]))
    md.append("")
    md.append("## Works mentioning OnSSET (keyword search)")
    md.append("")
    md.append(render_markdown_section("Mentions (auto)", mentions_all[:120]))
    md.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT_MD}")

if __name__ == "__main__":
    main()
