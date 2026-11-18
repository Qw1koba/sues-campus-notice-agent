#!/usr/bin/env python3
"""Fetch public student notices from the SUES Academic Affairs Office.

Only public titles, dates, links and short body excerpts are retained.  The
script is intentionally polite: it waits between requests, identifies itself
with a clear User-Agent, and does not access authenticated pages or files.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE_URL = "https://jwc.sues.edu.cn"
LIST_PATH = "/24063/list.htm"
USER_AGENT = "SUES-Course-Project-Notice-Agent/1.0 (educational research)"


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def find_body_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(".article") or soup.select_one(".wp_articlecontent")
    if node is None:
        return ""
    for bad in node.select("script, style, .wp_articlecontent .wp_articlecontent"):
        bad.decompose()
    return clean_text(node.get_text(" ", strip=True))


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    seen_links: set[str] = set()
    for page in range(1, 10):
        list_url = urljoin(BASE_URL, LIST_PATH if page == 1 else f"/24063/list{page}.htm")
        soup = BeautifulSoup(fetch_html(list_url), "lxml")
        for item in soup.select("li.news"):
            date_node = item.select_one(".news_meta")
            link_node = item.select_one(".news_title a")
            if date_node is None or link_node is None:
                continue
            href = urljoin(BASE_URL, link_node.get("href", ""))
            if not href or href in seen_links:
                continue
            seen_links.add(href)
            records.append(
                {
                    "title": clean_text(link_node.get("title") or link_node.get_text()),
                    "date": clean_text(date_node.get_text()),
                    "url": href,
                    "body": "",
                    "source": "上海工程技术大学教务处·通知公告（学生）",
                }
            )
        print(f"list page {page}: {len(records)} records")
        time.sleep(0.2)

    for idx, record in enumerate(records, start=1):
        try:
            record["body"] = find_body_text(fetch_html(record["url"]))[:2000]
        except Exception as exc:
            record["fetch_error"] = str(exc)
        if idx % 15 == 0:
            print(f"articles: {idx}/{len(records)}")
        time.sleep(0.15)

    output = out_dir / "sues_jwc_notices.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records to {output}")


if __name__ == "__main__":
    main()
