#!/usr/bin/env python3
"""
Nature T-Cell Immunology Paper Collector

Fetches recent T cell immunology papers from Nature Publishing Group
using their search and RSS feeds, then displays summaries.
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
import feedparser


NATURE_SEARCH_URL = "https://www.nature.com/search"
NATURE_RSS_URL = "https://www.nature.com/nature.rss"
NATURE_SUBJECT_RSS = "https://www.nature.com/subjects/t-cells.rss"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Paper:
    title: str
    authors: List[str]
    journal: str
    published: str
    url: str
    summary: str
    doi: Optional[str] = None


def fetch_nature_search(query: str = "T cell immunology", num_results: int = 10) -> List[Paper]:
    """Fetch papers from Nature's search page."""
    papers = []
    params = {
        "q": query,
        "order": "date_desc",
        "date_range": "last_year",
    }

    try:
        resp = requests.get(NATURE_SEARCH_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[!] Search request failed: {e}", file=sys.stderr)
        return papers

    soup = BeautifulSoup(resp.text, "lxml")

    # Find article cards
    articles = soup.select("article[data-test='article-card']")
    if not articles:
        # Fallback: try other selectors
        articles = soup.select("li[class*='result']")

    for article in articles[:num_results]:
        try:
            # Title and link
            title_el = article.select_one("h3 a, h2 a, [data-test='title-link']")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.nature.com" + link

            # Authors
            author_el = article.select_one("[data-test='authors'], .authors, ul[class*='author']")
            authors = []
            if author_el:
                authors = [a.get_text(strip=True) for a in author_el.select("a, li, span")]
                authors = [a for a in authors if a and len(a) > 1]

            # Journal
            journal_el = article.select_one("[data-test='journal'], .journal, span[class*='journal']")
            journal = journal_el.get_text(strip=True) if journal_el else "Nature"

            # Date
            date_el = article.select_one("time, [data-test='date'], span[class*='date']")
            published = date_el.get_text(strip=True) if date_el else "Unknown"

            # Summary/Abstract
            summary_el = article.select_one("p, [data-test='article-description'], .description")
            summary = summary_el.get_text(strip=True) if summary_el else "No summary available."

            papers.append(Paper(
                title=title,
                authors=authors[:5],
                journal=journal,
                published=published,
                url=link,
                summary=summary[:300],
            ))
        except Exception:
            continue

    return papers


def fetch_rss_feed(url: str, max_items: int = 10) -> List[Paper]:
    """Fetch papers from an RSS feed."""
    papers = []

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[!] RSS parse failed: {e}", file=sys.stderr)
        return papers

    for entry in feed.entries[:max_items]:
        title = entry.get("title", "Unknown Title")
        link = entry.get("link", "")
        summary = entry.get("summary", entry.get("description", "No summary."))
        # Clean HTML from summary
        if summary:
            summary = BeautifulSoup(summary, "lxml").get_text(strip=True)[:300]

        published = entry.get("published", entry.get("updated", "Unknown"))
        authors = []
        if hasattr(entry, "authors"):
            authors = [a.get("name", "") for a in entry.authors]
        elif hasattr(entry, "author"):
            authors = [entry.author]

        journal = "Nature"

        papers.append(Paper(
            title=title,
            authors=authors,
            journal=journal,
            published=published,
            url=link,
            summary=summary,
        ))

    return papers


def search_pubmed_tcell(query: str = "T cell immunology", max_results: int = 10) -> List[Paper]:
    """Fallback: search PubMed for T cell papers from Nature journals."""
    papers = []

    # PubMed E-utilities
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    # Search for recent Nature T cell papers
    search_params = {
        "db": "pubmed",
        "term": f"({query}) AND (Nature[Journal] OR Nature Immunology[Journal] OR Nature Reviews Immunology[Journal])",
        "retmax": max_results,
        "sort": "date",
        "retmode": "json",
        "datetype": "pdat",
        "mindate": (datetime.now() - timedelta(days=90)).strftime("%Y/%m/%d"),
        "maxdate": datetime.now().strftime("%Y/%m/%d"),
    }

    try:
        resp = requests.get(search_url, params=search_params, timeout=30)
        data = resp.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[!] PubMed search failed: {e}", file=sys.stderr)
        return papers

    if not ids:
        return papers

    # Fetch details
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
        "rettype": "abstract",
    }

    try:
        resp = requests.get(fetch_url, params=fetch_params, timeout=30)
        soup = BeautifulSoup(resp.text, features="xml")
    except Exception as e:
        print(f"[!] PubMed fetch failed: {e}", file=sys.stderr)
        return papers

    for article in soup.select("PubmedArticle"):
        try:
            # Title
            title_el = article.select_one("ArticleTitle")
            title = title_el.get_text(strip=True) if title_el else "Unknown"

            # Authors
            authors = []
            for author in article.select("Author"):
                last = author.select_one("LastName")
                first = author.select_one("ForeName")
                if last and first:
                    authors.append(f"{first.get_text()} {last.get_text()}")
                elif last:
                    authors.append(last.get_text())

            # Journal
            journal_el = article.select_one("Journal > Title")
            journal = journal_el.get_text(strip=True) if journal_el else "Nature"

            # Date
            pub_date = article.select_one("PubDate")
            if pub_date:
                year = pub_date.select_one("Year")
                month = pub_date.select_one("Month")
                day = pub_date.select_one("Day")
                parts = []
                if year:
                    parts.append(year.get_text())
                if month:
                    parts.append(month.get_text())
                if day:
                    parts.append(day.get_text())
                published = " ".join(parts) if parts else "Unknown"
            else:
                published = "Unknown"

            # DOI
            doi_el = article.select_one("ArticleId[IdType='doi']")
            doi = doi_el.get_text(strip=True) if doi_el else None
            url = f"https://doi.org/{doi}" if doi else ""

            # Abstract
            abstract_el = article.select_one("AbstractText")
            summary = abstract_el.get_text(strip=True)[:300] if abstract_el else "No abstract available."

            papers.append(Paper(
                title=title,
                authors=authors[:5],
                journal=journal,
                published=published,
                url=url,
                summary=summary,
                doi=doi,
            ))
        except Exception:
            continue

    return papers


def collect_all(query: str = "T cell immunology", max_results: int = 15) -> List[Paper]:
    """Collect papers from all sources, deduplicate by title."""
    all_papers = []
    seen_titles = set()

    print("[*] Fetching from Nature search...")
    for p in fetch_nature_search(query, max_results):
        key = p.title.lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            all_papers.append(p)

    print("[*] Fetching from Nature T-cells RSS feed...")
    for p in fetch_rss_feed(NATURE_SUBJECT_RSS, max_results):
        key = p.title.lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            all_papers.append(p)

    print("[*] Fetching from PubMed (Nature journals)...")
    for p in search_pubmed_tcell(query, max_results):
        key = p.title.lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            all_papers.append(p)

    return all_papers


def print_papers(papers: List[Paper], verbose: bool = False):
    """Pretty-print collected papers."""
    if not papers:
        print("\nNo papers found. The search sources may be temporarily unavailable.")
        return

    print(f"\n{'='*70}")
    print(f"  T-Cell Immunology Papers — {len(papers)} results")
    print(f"{'='*70}\n")

    for i, paper in enumerate(papers, 1):
        print(f"[{i}] {paper.title}")
        if paper.authors:
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" et al. ({len(paper.authors)} authors)"
            print(f"    Authors: {authors_str}")
        print(f"    Journal: {paper.journal}")
        print(f"    Published: {paper.published}")
        if paper.url:
            print(f"    URL: {paper.url}")
        if paper.doi:
            print(f"    DOI: {paper.doi}")
        if verbose and paper.summary:
            print(f"    Summary: {paper.summary}")
        print()


def save_json(papers: List[Paper], filepath: str):
    """Save papers to JSON file."""
    data = [asdict(p) for p in papers]
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[*] Saved {len(papers)} papers to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Collect T-cell immunology papers from Nature Publishing Group")
    parser.add_argument("-q", "--query", default="T cell immunology", help="Search query (default: 'T cell immunology')")
    parser.add_argument("-n", "--num", type=int, default=15, help="Max results per source (default: 15)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show paper summaries/abstracts")
    parser.add_argument("-o", "--output", help="Save results to JSON file")
    parser.add_argument("--source", choices=["search", "rss", "pubmed", "all"], default="all",
                        help="Data source (default: all)")
    args = parser.parse_args()

    if args.source == "search":
        papers = fetch_nature_search(args.query, args.num)
    elif args.source == "rss":
        papers = fetch_rss_feed(NATURE_SUBJECT_RSS, args.num)
    elif args.source == "pubmed":
        papers = search_pubmed_tcell(args.query, args.num)
    else:
        papers = collect_all(args.query, args.num)

    print_papers(papers, verbose=args.verbose)

    if args.output:
        save_json(papers, args.output)


if __name__ == "__main__":
    main()
