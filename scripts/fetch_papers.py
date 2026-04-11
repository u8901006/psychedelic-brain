#!/usr/bin/env python3
"""
Fetch latest psychedelic research papers from PubMed E-utilities API.
Targets Q1/Q2 psychedelic journals and covers major psychedelic research topics.
"""

import json
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote_plus

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

JOURNALS = [
    "JAMA Psychiatry",
    "American Journal of Psychiatry",
    "Lancet Psychiatry",
    "Molecular Psychiatry",
    "Neuropsychopharmacology",
    "Biological Psychiatry",
    "European Neuropsychopharmacology",
    "Progress in Neuro-Psychopharmacology and Biological Psychiatry",
    "Journal of Psychopharmacology",
    "Psychopharmacology",
    "Neuroscience of Consciousness",
    "Consciousness and Cognition",
    "Journal of Psychedelic Studies",
    "Journal of Psychoactive Drugs",
]

SEARCH_QUERIES = [
    '("psychedelic-assisted therapy" OR "psychedelic-assisted psychotherapy" OR psilocybin OR LSD OR MDMA) AND (depression OR "major depressive disorder" OR MDD OR "treatment-resistant depression" OR TRD)',
    '("psychedelic-assisted therapy" OR psilocybin OR LSD OR MDMA) AND (anxiety OR "generalized anxiety disorder" OR GAD OR "social anxiety disorder")',
    '("psychedelic-assisted psychotherapy" OR MDMA OR psilocybin) AND (PTSD OR trauma OR "trauma-related disorders" OR dissociation OR depersonalization OR derealization)',
    '(psychedelic OR psychedelics OR psilocybin) AND (OCD OR "obsessive-compulsive disorder")',
    '("psychedelic-assisted therapy" OR psilocybin OR MDMA OR ibogaine OR ketamine) AND ("substance use disorder" OR SUD OR "alcohol use disorder" OR AUD OR addiction OR smoking cessation)',
    '(psychedelic OR psychedelics OR psilocybin OR LSD) AND ("chronic pain" OR "persistent pain" OR "pain management" OR analgesia)',
    '("psychedelic-assisted therapy" OR psilocybin OR psychedelic) AND (fibromyalgia OR "fibromyalgia syndrome" OR "central sensitization")',
    '(psychedelic OR psychedelics OR psilocybin OR LSD) AND ("altered states of consciousness" OR "ego dissolution" OR "mystical experience" OR phenomenology)',
    '(psychedelic OR psychedelics OR psilocybin OR LSD) AND ("5-HT2A receptor" OR neuroplasticity OR BDNF OR glutamate OR "functional connectivity" OR "default mode network")',
    '("psychedelic-assisted psychotherapy" OR "psychedelic-assisted therapy") AND (psychotherapy OR integration OR "set and setting" OR "therapeutic alliance")',
    '(psychedelic OR psychedelics OR psilocybin OR MDMA) AND (safety OR tolerability OR "adverse events" OR "randomized controlled trial" OR placebo-controlled)',
    "(psilocybin OR psychedelic) AND (depression OR TRD) AND (randomized controlled trial OR RCT OR trial OR review)",
]

HEADERS = {"User-Agent": "PsychedelicBrainBot/1.0 (research aggregator)"}


def search_papers(query: str, retmax: int = 20) -> list[str]:
    params = (
        f"?db=pubmed&term={quote_plus(query)}&retmax={retmax}&sort=date&retmode=json"
    )
    url = PUBMED_SEARCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[ERROR] PubMed search failed: {e}", file=sys.stderr)
        return []


def fetch_details(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = f"?db=pubmed&id={ids}&retmode=xml"
    url = PUBMED_FETCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as resp:
            xml_data = resp.read().decode()
    except Exception as e:
        print(f"[ERROR] PubMed fetch failed: {e}", file=sys.stderr)
        return []

    papers = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            art = medline.find(".//Article") if medline else None
            if art is None:
                continue

            title_el = art.find(".//ArticleTitle")
            title = (
                (title_el.text or "").strip()
                if title_el is not None and title_el.text
                else ""
            )

            abstract_parts = []
            for abs_el in art.findall(".//Abstract/AbstractText"):
                label = abs_el.get("Label", "")
                text = "".join(abs_el.itertext()).strip()
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:2000]

            journal_el = art.find(".//Journal/Title")
            journal = (
                (journal_el.text or "").strip()
                if journal_el is not None and journal_el.text
                else ""
            )

            pub_date = art.find(".//PubDate")
            date_str = ""
            if pub_date is not None:
                year = pub_date.findtext("Year", "")
                month = pub_date.findtext("Month", "")
                day = pub_date.findtext("Day", "")
                parts = [p for p in [year, month, day] if p]
                date_str = " ".join(parts)

            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            keywords = []
            for kw in medline.findall(".//KeywordList/Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())

            papers.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "journal": journal,
                    "date": date_str,
                    "abstract": abstract,
                    "url": link,
                    "keywords": keywords,
                }
            )
    except ET.ParseError as e:
        print(f"[ERROR] XML parse failed: {e}", file=sys.stderr)

    return papers


def main():
    parser = argparse.ArgumentParser(description="Fetch psychedelic papers from PubMed")
    parser.add_argument("--days", type=int, default=7, help="Lookback days")
    parser.add_argument(
        "--max-papers", type=int, default=40, help="Max papers to fetch"
    )
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    tz_taipei = timezone(timedelta(hours=8))
    today = datetime.now(tz_taipei)
    lookback = (today - timedelta(days=args.days)).strftime("%Y/%m/%d")
    date_filter = f'"{lookback}"[Date - Publication] : "3000"[Date - Publication]'

    all_pmids = set()
    per_query = max(args.max_papers // len(SEARCH_QUERIES), 3)

    for i, query in enumerate(SEARCH_QUERIES):
        full_query = f"({query}) AND {date_filter}"
        print(
            f"[INFO] Query {i + 1}/{len(SEARCH_QUERIES)}: {query[:80]}...",
            file=sys.stderr,
        )
        pmids = search_papers(full_query, retmax=per_query)
        all_pmids.update(pmids)
        print(
            f"[INFO]   Found {len(pmids)} PMIDs (total unique: {len(all_pmids)})",
            file=sys.stderr,
        )

    pmid_list = list(all_pmids)[: args.max_papers]
    print(
        f"[INFO] Fetching details for {len(pmid_list)} unique papers...",
        file=sys.stderr,
    )

    if not pmid_list:
        if args.json:
            output_data = {
                "date": today.strftime("%Y-%m-%d"),
                "count": 0,
                "papers": [],
            }
            out_str = json.dumps(output_data, ensure_ascii=False, indent=2)
            if args.output == "-":
                print(out_str)
            else:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(out_str)
        return

    papers = fetch_details(pmid_list)
    print(f"[INFO] Fetched details for {len(papers)} papers", file=sys.stderr)

    output_data = {
        "date": today.strftime("%Y-%m-%d"),
        "count": len(papers),
        "papers": papers,
    }

    out_str = json.dumps(output_data, ensure_ascii=False, indent=2)

    if args.output == "-":
        print(out_str)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"[INFO] Saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
