from __future__ import annotations

import html
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree as ET

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NBALivePredictor/1.0; +https://example.com/bot)",
    "Accept": "application/rss+xml, application/xml, application/json;q=0.9, */*;q=0.8",
}

TIMEOUT = 5

MEDIA_NS = "{http://search.yahoo.com/mrss/}"


@dataclass(frozen=True)
class SourceConfig:
    key: str
    name: str
    rank: int


GENERAL_SOURCES: list[SourceConfig] = [
    SourceConfig("espn", "ESPN", 1),
    SourceConfig("yahoo", "Yahoo Sports", 2),
    SourceConfig("cbs", "CBS Sports", 2),
    SourceConfig("br", "Bleacher Report", 3),
]

QUERY_SOURCES: list[SourceConfig] = [
    SourceConfig("google", "Google News", 4),
    SourceConfig("reddit", "r/nba (Reddit)", 5),
]


def _safe_text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None and el.text else ""


def _strip_html(value: str) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _parse_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return ""


def _normalize(headline: str, description: str, url: str, published: str, source: str, rank: int, image: str = "") -> dict[str, Any] | None:
    headline = html.unescape((headline or "").strip())
    if not headline or not url:
        return None
    return {
        "id": url,
        "headline": headline,
        "description": _strip_html(description)[:320],
        "url": url,
        "published": published,
        "image": image,
        "source": source,
        "source_rank": rank,
    }


def _http_get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        response.raise_for_status()
        return response.text
    except Exception:
        return ""


def _parse_rss(xml_text: str, default_source: str, rank: int) -> list[dict[str, Any]]:
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    articles: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = _safe_text(item.find("title"))
        link = _safe_text(item.find("link"))
        desc = _safe_text(item.find("description"))
        pub = _parse_pub_date(_safe_text(item.find("pubDate")))

        actual_source = default_source
        google_source = item.find("source")
        if google_source is not None and google_source.text:
            actual_source = f"{default_source} - {google_source.text.strip()}"

        image = ""
        media_thumb = item.find(MEDIA_NS + "thumbnail")
        media_content = item.find(MEDIA_NS + "content")
        enc = item.find("enclosure")
        if media_thumb is not None and media_thumb.attrib.get("url"):
            image = media_thumb.attrib["url"]
        elif media_content is not None and media_content.attrib.get("url"):
            image = media_content.attrib["url"]
        elif enc is not None and enc.attrib.get("url"):
            image = enc.attrib["url"]

        article = _normalize(title, desc, link, pub, actual_source, rank, image)
        if article:
            articles.append(article)
    return articles


@lru_cache(maxsize=4)
def fetch_yahoo(refresh_key: str = "cached") -> list[dict[str, Any]]:
    del refresh_key
    return _parse_rss(_http_get("https://sports.yahoo.com/nba/rss.xml"), "Yahoo Sports", 2)


@lru_cache(maxsize=4)
def fetch_cbs(refresh_key: str = "cached") -> list[dict[str, Any]]:
    del refresh_key
    return _parse_rss(_http_get("https://www.cbssports.com/rss/headlines/nba/"), "CBS Sports", 2)


@lru_cache(maxsize=4)
def fetch_bleacher_report(refresh_key: str = "cached") -> list[dict[str, Any]]:
    del refresh_key
    return _parse_rss(_http_get("https://bleacherreport.com/articles/feed?tag_id=19"), "Bleacher Report", 3)


@lru_cache(maxsize=128)
def fetch_google_news(query: str, refresh_key: str = "cached") -> list[dict[str, Any]]:
    del refresh_key
    if not query:
        return []
    encoded = urllib.parse.quote(f"{query} NBA")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    return _parse_rss(_http_get(url), "Google News", 4)


@lru_cache(maxsize=128)
def fetch_reddit(query: str, refresh_key: str = "cached") -> list[dict[str, Any]]:
    del refresh_key
    if not query:
        return []
    encoded = urllib.parse.quote(query)
    url = f"https://www.reddit.com/r/nba/search.json?q={encoded}&restrict_sr=1&sort=top&t=month&limit=15"
    text = _http_get(url)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    articles: list[dict[str, Any]] = []
    for child in (data.get("data", {}).get("children", []) or []):
        post = child.get("data", {}) or {}
        title = post.get("title", "")
        permalink = post.get("permalink", "")
        if not title or not permalink:
            continue
        link = "https://www.reddit.com" + permalink
        desc = post.get("selftext", "") or ""
        created = post.get("created_utc")
        published = ""
        if created:
            try:
                published = datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat()
            except (TypeError, ValueError):
                published = ""
        image = post.get("thumbnail", "") or ""
        if image and not image.startswith("http"):
            image = ""
        article = _normalize(title, desc, link, published, "r/nba (Reddit)", 5, image)
        if article:
            articles.append(article)
    return articles


def fetch_general_pool(refresh_key: str = "cached") -> list[dict[str, Any]]:
    return fetch_yahoo(refresh_key) + fetch_cbs(refresh_key) + fetch_bleacher_report(refresh_key)


def fetch_entity_pool(query: str, refresh_key: str = "cached") -> list[dict[str, Any]]:
    if not query:
        return []
    return fetch_google_news(query, refresh_key) + fetch_reddit(query, refresh_key)


def normalize_espn(article: dict[str, Any]) -> dict[str, Any] | None:
    images = article.get("images") or []
    links = article.get("links") or {}
    web_link = links.get("web") or {}
    image = next((item.get("url") for item in images if item.get("url")), "")
    headline = article.get("headline") or article.get("title") or ""
    url = web_link.get("href") or ""
    description = article.get("description") or ""
    published = article.get("published") or article.get("lastModified") or ""
    source_label = article.get("source") or "ESPN"
    if isinstance(source_label, dict):
        source_label = source_label.get("description") or "ESPN"
    source_label = f"ESPN ({source_label})" if source_label and source_label != "ESPN" else "ESPN"
    return _normalize(headline, description, url, _parse_pub_date(published) or published, source_label, 1, image)


def article_relevance(article: dict[str, Any], terms: list[str]) -> int:
    if not terms:
        return 0
    haystack = " ".join([
        article.get("headline", ""),
        article.get("description", ""),
        article.get("source", ""),
    ]).lower()
    return sum(1 for term in terms if term and term.lower() in haystack)


def sort_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(articles, key=lambda a: (int(a.get("source_rank", 9)), -_published_score(a.get("published", ""))))


def _published_score(value: str) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for article in articles:
        key = (article.get("id") or article.get("url") or article.get("headline") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result
