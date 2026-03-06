"""
SHL Assessment Catalog Scraper — v2 (Fixed Parser)
Scrapes all Individual Test Solutions. Uses text-line parsing which works
reliably on SHL's server-rendered pages.
"""

import requests
import time
import json
import re
import os
from bs4 import BeautifulSoup

BASE_URL = "https://www.shl.com"
CATALOG_LIST_URL = "https://www.shl.com/products/product-catalog/"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data", "assessments.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TEST_TYPE_MAP = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}


def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except Exception as e:
            print(f"  [Retry {attempt+1}] {url}: {e}")
            time.sleep(2 * (attempt + 1))
    return None


def get_links_from_listing_page(start: int) -> list[str]:
    """Get assessment detail page links from one catalog listing page."""
    url = f"{CATALOG_LIST_URL}?start={start}&type=1"
    soup = fetch(url)
    if not soup:
        return []
    links = []
    # SHL listing puts assessment links in <a href="/products/product-catalog/view/...">
    for a in soup.find_all("a", href=re.compile(r"/product-catalog/view/")):
        href = a["href"]
        if href.startswith("http"):
            full = href
        else:
            full = BASE_URL + href
        links.append(full)
    return list(dict.fromkeys(links))  # deduplicate, preserve order


def parse_detail(url: str) -> dict | None:
    """
    Parse an individual assessment detail page.
    Uses plain text extraction which is reliable on SHL's server-rendered HTML.
    """
    soup = fetch(url)
    if not soup:
        return None

    # --- Name ---
    h1 = soup.find("h1")
    name = h1.get_text(strip=True) if h1 else ""
    if not name:
        return None

    # Get all page text as lines
    raw_text = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    description = ""
    job_levels = []
    languages = []
    duration = None
    test_type_codes = []
    remote_support = "No"
    adaptive_support = "No"

    i = 0
    while i < len(lines):
        line = lines[i]

        # Description
        if line.lower() == "description" and i + 1 < len(lines):
            desc_parts = []
            j = i + 1
            while j < len(lines) and lines[j].lower() not in [
                "job levels", "languages", "assessment length", "downloads", "description"
            ]:
                desc_parts.append(lines[j])
                j += 1
            description = " ".join(desc_parts)
            i = j
            continue

        # Job levels
        if line.lower() == "job levels" and i + 1 < len(lines):
            job_text = lines[i + 1]
            job_levels = [j.strip() for j in re.split(r"[,\n]", job_text) if j.strip()]
            i += 2
            continue

        # Languages
        if line.lower() == "languages" and i + 1 < len(lines):
            lang_text = lines[i + 1]
            languages = [l.strip() for l in re.split(r"[,\n]", lang_text) if l.strip()]
            i += 2
            continue

        # Assessment length section — duration + test type + remote + adaptive
        if "completion time in minutes" in line.lower():
            dur_match = re.search(r"=\s*(\d+)", line)
            if dur_match:
                duration = int(dur_match.group(1))

        if line.lower().startswith("test type"):
            # e.g. "Test Type: K" or next line is "K"
            code_match = re.search(r"Test Type\s*:?\s*([A-Z])", line)
            if code_match:
                test_type_codes.append(code_match.group(1))
            elif i + 1 < len(lines) and lines[i + 1] in TEST_TYPE_MAP:
                test_type_codes.append(lines[i + 1])

        if "remote testing" in line.lower():
            # Look for Yes/No in the same line or nearby
            if "yes" in line.lower():
                remote_support = "Yes"
            elif "-yes" in line.lower() or "✓" in line:
                remote_support = "Yes"
            # Check next line
            elif i + 1 < len(lines):
                nxt = lines[i + 1].lower()
                if nxt in ["yes", "✓", "-yes"]:
                    remote_support = "Yes"

        if "adaptive" in line.lower() or "irt" in line.lower():
            if "yes" in line.lower():
                adaptive_support = "Yes"
            elif i + 1 < len(lines):
                nxt = lines[i + 1].lower()
                if nxt in ["yes", "✓", "-yes"]:
                    adaptive_support = "Yes"

        i += 1

    # --- Fallback: find single-letter test type code from a catalogue tooltip span ---
    if not test_type_codes:
        for span in soup.find_all("span"):
            t = span.get_text(strip=True)
            if t in TEST_TYPE_MAP:
                # Verify it's not just a stray letter
                parent_cls = " ".join(span.get("class", []))
                if "tooltip" in parent_cls.lower() or "catalogue" in parent_cls.lower() or "badge" in parent_cls.lower():
                    test_type_codes.append(t)
                    break
        # Wider fallback
        if not test_type_codes:
            for span in soup.find_all("span"):
                t = span.get_text(strip=True)
                if t in TEST_TYPE_MAP and len(t) == 1:
                    gp = span.parent
                    if gp and "remote" not in gp.get_text("", strip=True).lower():
                        test_type_codes.append(t)
                        break

    # --- Fallback: detect remote/adaptive from CSS class -yes ---
    for el in soup.find_all(class_=re.compile(r"-yes", re.I)):
        parent_text = ""
        p = el.parent
        while p and parent_text == "":
            parent_text = p.get_text(" ", strip=True).lower()
            p = p.parent
        if "remote" in parent_text[:80]:
            remote_support = "Yes"
        if "adaptive" in parent_text[:80] or "irt" in parent_text[:80]:
            adaptive_support = "Yes"

    # --- Duration fallback via regex on full page text ---
    if duration is None:
        m = re.search(r"Completion Time in minutes\s*=\s*(\d+)", raw_text, re.I)
        if m:
            duration = int(m.group(1))

    # Map codes to full names
    test_type_full = [TEST_TYPE_MAP.get(code, code) for code in test_type_codes]
    if not test_type_full:
        # Last resort — regex on raw text
        m = re.search(r"Test Type\s*:?\s*([A-Z])\b", raw_text)
        if m:
            code = m.group(1)
            if code in TEST_TYPE_MAP:
                test_type_full = [TEST_TYPE_MAP[code]]

    # Normalize URL to /solutions/ format (matches training data)
    canonical_url = url.replace(
        "https://www.shl.com/products/product-catalog/view/",
        "https://www.shl.com/solutions/products/product-catalog/view/"
    )

    return {
        "name": name,
        "url": canonical_url,
        "description": description,
        "job_levels": job_levels,
        "languages": languages,
        "duration": duration,
        "test_type": test_type_full,
        "remote_support": remote_support,
        "adaptive_support": adaptive_support,
    }


def _save(data: list[dict]):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scrape_all():
    assessments = []
    seen_urls = set()

    print("=" * 60)
    print("SHL Catalog Scraper v2 — Individual Test Solutions")
    print("=" * 60)

    # 32 pages of individual tests (start=0 to 372, step=12)
    for page_idx, start in enumerate(range(0, 396, 12)):  # 33 pages
        print(f"\n[Page {page_idx+1}/33] start={start}")
        links = get_links_from_listing_page(start)
        print(f"  Found {len(links)} links")

        for link in links:
            if link in seen_urls:
                continue
            seen_urls.add(link)
            slug = link.rstrip("/").split("/")[-1]
            print(f"  Parsing: {slug}")

            result = parse_detail(link)
            if result:
                assessments.append(result)
                if len(assessments) % 20 == 0:
                    _save(assessments)
                    print(f"  >>> Checkpoint: {len(assessments)} saved")
            time.sleep(0.8)

        time.sleep(1.5)

    _save(assessments)
    print(f"\n✅ Done! {len(assessments)} assessments scraped.")

    # Quality report
    with_desc = sum(1 for a in assessments if a["description"])
    with_type = sum(1 for a in assessments if a["test_type"])
    with_dur  = sum(1 for a in assessments if a["duration"])
    print(f"   With description : {with_desc}/{len(assessments)}")
    print(f"   With test type   : {with_type}/{len(assessments)}")
    print(f"   With duration    : {with_dur}/{len(assessments)}")

    if len(assessments) < 377:
        print(f"  ⚠️  WARNING: got {len(assessments)}, expected 377+")


if __name__ == "__main__":
    scrape_all()
