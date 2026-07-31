#!/usr/bin/env python3
"""
Free weekly IAM news collector.

It uses public Google News RSS search results, scores articles using IAM
keywords, removes duplicates and writes data/news.json plus a dated archive.
No paid AI API is required.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
OUTPUT_FILE = DATA_DIR / "news.json"

MAX_ITEMS = 18
LOOKBACK_DAYS = 8

SEARCH_QUERIES = [
    '"identity and access management"',
    'IAM cybersecurity authentication authorization',
    '"identity governance" OR IGA',
    '"privileged access management" OR PAM',
    '"customer identity" OR CIAM',
    '"identity security" OR ITDR',
    '"non-human identity" OR "machine identity"',
    'passkeys FIDO authentication',
    '"Microsoft Entra" identity',
    'Okta identity security',
    'SailPoint identity governance',
    'Saviynt identity governance',
    'CyberArk privileged access',
]

CATEGORY_RULES = [
    ("Machine Identity", ["non-human identity", "machine identity", "workload identity", "service account", "secrets management"]),
    ("CIAM", ["ciam", "customer identity", "consumer identity", "digital identity journey"]),
    ("PAM", ["pam", "privileged access", "privileged identity", "just-in-time access"]),
    ("IGA", ["iga", "identity governance", "access certification", "access review", "role management"]),
    ("Authentication", ["passkey", "fido", "authentication", "mfa", "passwordless", "openid", "oauth"]),
    ("Identity Security", ["identity threat", "itdr", "identity security", "credential attack", "account takeover"]),
    ("Entra ID", ["microsoft entra", "entra id", "azure ad"]),
]

HIGH_VALUE_TERMS = [
    "identity", "access", "authentication", "authorization", "governance",
    "privileged", "passkey", "fido", "zero trust", "entra", "okta",
    "sailpoint", "saviynt", "cyberark", "openid", "oauth", "machine identity",
    "non-human identity", "service account", "account takeover"
]

PROMOTIONAL_TERMS = [
    "sponsored", "webinar registration", "limited offer", "buy now",
    "partner announcement", "award winner"
]

def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "IAM-Knowledge-Hub/1.0 (+https://github.com/)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def canonical_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return " ".join(title.split())

def parse_date(value: str) -> dt.datetime:
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return dt.datetime.now(dt.timezone.utc)

def classify(text: str) -> str:
    lower = text.lower()
    for category, terms in CATEGORY_RULES:
        if any(term in lower for term in terms):
            return category
    return "IAM & Zero Trust"

def relevance(text: str, published: dt.datetime) -> int:
    lower = text.lower()
    score = sum(2 for term in HIGH_VALUE_TERMS if term in lower)
    score += max(0, 8 - (dt.datetime.now(dt.timezone.utc) - published).days)
    if any(term in lower for term in PROMOTIONAL_TERMS):
        score -= 8
    return max(1, min(10, score // 2))

def make_summary(description: str, title: str) -> str:
    clean = strip_html(description)
    clean = re.sub(r"\s*Read more.*$", "", clean, flags=re.I)
    if not clean or clean.lower() == title.lower():
        return "Open the original source for the full details."
    return clean[:320].rstrip(" ,.;") + ("…" if len(clean) > 320 else "")

def study_topic(category: str) -> str:
    mapping = {
        "Machine Identity": "Ownership, lifecycle and rotation of non-human identities",
        "CIAM": "Customer identity journeys, consent and fraud controls",
        "PAM": "Just-in-time access and privileged session controls",
        "IGA": "Application onboarding, access reviews and role design",
        "Authentication": "Passkeys, phishing-resistant MFA and recovery",
        "Identity Security": "Identity threat detection and response",
        "Entra ID": "Conditional Access and identity protection",
        "IAM & Zero Trust": "Identity-centric Zero Trust architecture",
    }
    return mapping.get(category, "IAM architecture and operating model")

def why_it_matters(category: str) -> str:
    mapping = {
        "Machine Identity": "Machine and workload identities often grow faster than workforce identities and require dedicated ownership and lifecycle controls.",
        "CIAM": "Customer identity decisions directly affect security, conversion, privacy and digital experience.",
        "PAM": "Privileged access remains a high-impact attack path across infrastructure, cloud and DevOps environments.",
        "IGA": "Governance quality depends on reliable data, clear ownership and enforceable lifecycle processes.",
        "Authentication": "Authentication changes affect phishing resistance, recovery, user experience and support demand.",
        "Identity Security": "Identity signals increasingly connect preventive IAM controls with detection and incident response.",
        "Entra ID": "Changes to Entra ID can affect Conditional Access, authentication and tenant security design.",
        "IAM & Zero Trust": "Identity is a primary policy enforcement layer in modern Zero Trust architectures.",
    }
    return mapping.get(category, mapping["IAM & Zero Trust"])

def parse_feed(query: str) -> list[dict]:
    encoded = urllib.parse.quote_plus(f"{query} when:7d")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    root = ET.fromstring(fetch(url))
    output = []
    for item in root.findall("./channel/item"):
        title = strip_html(item.findtext("title", ""))
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "")
        published = parse_date(item.findtext("pubDate", ""))
        source_node = item.find("source")
        source = strip_html(source_node.text if source_node is not None and source_node.text else "")
        if not source and " - " in title:
            source = title.rsplit(" - ", 1)[-1]
        output.append({
            "title": title,
            "url": link,
            "description": description,
            "published": published,
            "source": source or "News source",
        })
    return output

def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=LOOKBACK_DAYS)
    candidates: list[dict] = []
    errors: list[str] = []

    for query in SEARCH_QUERIES:
        try:
            candidates.extend(parse_feed(query))
        except Exception as exc:
            errors.append(f"{query}: {exc}")

    unique: dict[str, dict] = {}
    for article in candidates:
        if article["published"] < cutoff:
            continue
        key = canonical_title(article["title"])
        if len(key) < 12:
            continue
        combined = f'{article["title"]} {strip_html(article["description"])}'
        score = relevance(combined, article["published"])
        if score < 3:
            continue
        category = classify(combined)
        item = {
            "title": article["title"],
            "source": article["source"],
            "published_at": article["published"].isoformat(),
            "category": category,
            "summary": make_summary(article["description"], article["title"]),
            "why_it_matters": why_it_matters(category),
            "study_topic": study_topic(category),
            "relevance": score,
            "url": article["url"],
            "tags": [category],
        }
        previous = unique.get(key)
        if previous is None or item["relevance"] > previous["relevance"]:
            unique[key] = item

    items = sorted(
        unique.values(),
        key=lambda x: (x["relevance"], x["published_at"]),
        reverse=True,
    )[:MAX_ITEMS]

    if not items:
        print("No suitable articles found; the existing dashboard was not overwritten.", file=sys.stderr)
        if errors:
            print("\n".join(errors), file=sys.stderr)
        return 1

    payload = {
        "generated_at": now.isoformat(),
        "items": items,
        "collector_notes": {
            "method": "Public Google News RSS searches with keyword-based IAM relevance ranking",
            "errors": errors,
        },
    }

    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    archive_name = now.date().isoformat() + ".json"
    (ARCHIVE_DIR / archive_name).write_text(content, encoding="utf-8")
    print(f"Wrote {len(items)} articles to {OUTPUT_FILE}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
