"""Build a local index from publicly accessible Venuvanam pages.
Run only where automated access is permitted; this script checks robots.txt,
uses a small page limit, and waits between requests. It stores short extracts,
not full article text, in data/articles.json.
"""
import json
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE = "https://venuvanam.com/"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "articles.json"
MAX_PAGES = 35
DELAY_SECONDS = 1.0
USER_AGENT = "VenuvanamAIAssistantStarter/1.0 (polite public-page indexer)"


def normalize_url(url):
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != urlparse(BASE).netloc.lower():
        return None
    if parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".zip", ".css", ".js")):
        return None
    return url


def main():
    robots = RobotFileParser(urljoin(BASE, "/robots.txt"))
    try:
        robots.read()
    except Exception:
        print("Could not read robots.txt; stopping rather than assuming permission.")
        return
    if not robots.can_fetch(USER_AGENT, BASE):
        print("robots.txt does not allow this crawler on the homepage. No pages were fetched.")
        return

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    queue = deque([BASE])
    seen = set()
    records = []

    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            continue
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", ""):
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
                tag.decompose()
            title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip() or url
            main_content = soup.find("article") or soup.find("main") or soup.find("body") or soup
            text = re.sub(r"\s+", " ", main_content.get_text(" ", strip=True)).strip()
            if text:
                # Store a concise excerpt to help retrieval, not a full copyrighted article.
                excerpt = text[:1800]
                records.append({
                    "title": title[:240],
                    "url": url,
                    "summary": excerpt[:400],
                    "content": excerpt,
                    "tags": []
                })
            for anchor in soup.find_all("a", href=True):
                found = normalize_url(urljoin(url, anchor["href"]))
                if found and found not in seen and found not in queue:
                    queue.append(found)
            print(f"Indexed {len(records)} / visited {len(seen)}: {title[:70]}")
            time.sleep(DELAY_SECONDS)
        except requests.RequestException as exc:
            print(f"Skipping {url}: {exc}")

    if records:
        OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(records)} short page records to {OUT}")
    else:
        print("No pages indexed. Keeping the starter index unchanged.")


if __name__ == "__main__":
    main()
