# Nature T-Cell Immunology Paper Collector

Fetches recent T cell immunology papers from Nature Publishing Group.

## Sources

- Nature.com search (sorted by date)
- Nature T-cells RSS feed
- PubMed (Nature / Nature Immunology / Nature Reviews Immunology journals)

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Basic usage — collect from all sources
python collector.py

# Show summaries/abstracts
python collector.py -v

# Custom query
python collector.py -q "CAR-T cell therapy"

# Limit results
python collector.py -n 10

# Save to JSON
python collector.py -o results.json

# Single source
python collector.py --source pubmed
```

## Output

Papers are displayed with title, authors, journal, date, URL, and DOI.
Use `-v` for abstracts, `-o file.json` for machine-readable output.

## Notes

This project is under active development. Stay tuned for updates!

---

## Test

This is a test update to verify GitHub push workflow — April 16, 2026.
