#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
CURRENT_FILE = DATA / "news.json"
ALL_FILE = DATA / "all_articles.json"

MAX_CURRENT_ITEMS = 24
LOOKBACK_DAYS = 8
MAX_PER_SOURCE = 5

# Restrict discovery to editorial/research areas rather than entire vendor domains.
SEARCH_TARGETS = [
    ("Cloud Security Alliance", "site:cloudsecurityalliance.org/blog"),
    ("Cloud Security Alliance", "site:cloudsecurityalliance.org/artifacts"),
    ("Cloud Security Alliance", "site:cloudsecurityalliance.org/research"),
    ("Gartner", "site:gartner.com/en/information-technology"),
    ("Identity Defined Security Alliance", "site:idsalliance.org/blog"),
    ("KuppingerCole", "site:kuppingercole.com/insights"),
    ("KuppingerCole", "site:kuppingercole.com/blog"),
    ("Microsoft Security", "site:microsoft.com/en-us/security/blog"),
    ("Okta", "site:okta.com/blog"),
    ("Okta Security", "site:sec.okta.com/articles"),
    ("Wiz", "site:wiz.io/blog"),
]

SOURCE_WEIGHT = {
    "Gartner": 5,
    "KuppingerCole": 5,
    "Cloud Security Alliance": 4,
    "Identity Defined Security Alliance": 4,
    "Microsoft Security": 4,
    "Okta": 4,
    "Okta Security": 5,
    "Wiz": 4,
}

# Hard exclusions: transactional, account/login, low-value or irrelevant page types.
TITLE_EXCLUSIONS = [
    "sign in", "sign-in", "login", "log in", "authorize", "authorization endpoint",
    "workday", "careers", "jobs", "pricing", "contact sales", "request a demo",
    "register now", "registration", "customer portal", "support portal",
]

TEXT_EXCLUSIONS = [
    "/oauth2/", "/authorize", "/signin", "/login", "/enduser/",
    "redirect_uri=", "response_type=code", "client_id=",
]

SECTION_RULES = {
    "Latest IAM Trends": [
        "trend", "future of identity", "identity strategy", "identity fabric",
        "agentic ai", "ai agent", "non-human identity", "machine identity",
        "passwordless", "passkey", "identity-first", "zero trust"
    ],
    "Top Security Vendors": [
        "vendor", "leader", "platform", "launch", "announces", "acquisition",
        "partnership", "integration", "microsoft", "okta", "sailpoint",
        "saviynt", "cyberark", "ping identity", "wiz"
    ],
    "Emerging Threats": [
        "threat", "attack", "breach", "exploit", "vulnerability", "credential",
        "phishing", "token theft", "account takeover", "identity attack",
        "malware", "ransomware", "compromise", "adversary"
    ],
    "Market Share Insights": [
        "market share", "market growth", "market size", "magic quadrant",
        "leader", "challenger", "adoption", "market forecast",
        "market analysis", "market presence", "revenue", "market guide"
    ],
    "Technology Developments": [
        "technology", "passkey", "fido", "oauth", "openid", "mfa",
        "passwordless", "continuous access", "conditional access",
        "identity proofing", "authorization", "policy engine",
        "non-human identity", "workload identity", "ai agent", "itdr",
        "identity threat detection"
    ],
    "Competitive Analysis": [
        "compare", "comparison", "versus", " vs ", "competitive",
        "capabilities", "strengths", "weaknesses", "magic quadrant",
        "market guide", "vendor evaluation", "platform comparison"
    ],
}

TAG_RULES = {
    "IGA": ["identity governance", "iga", "access review", "certification", "role management", "lifecycle"],
    "PAM": ["privileged access", "pam", "privileged identity", "just-in-time"],
    "CIAM": ["ciam", "customer identity", "consumer identity"],
    "Authentication": ["passkey", "fido", "authentication", "mfa", "passwordless", "phishing-resistant"],
    "Identity Security": ["identity security", "identity threat", "itdr", "account takeover", "credential"],
    "Machine Identity": ["non-human identity", "machine identity", "workload identity", "service account"],
    "Zero Trust": ["zero trust", "continuous access", "conditional access"],
    "AI & Identity": ["ai agent", "agentic ai", "identity for ai", "ai identity"],
    "Authorization": ["authorization", "policy engine", "fine-grained access", "oauth", "openid"],
}

HIGH_CONFIDENCE_TERMS = [
    "identity", "access", "authentication", "authorization", "governance",
    "privileged", "passkey", "fido", "zero trust", "entra", "okta",
    "sailpoint", "saviynt", "cyberark", "openid", "oauth",
    "machine identity", "non-human identity", "service account",
    "identity threat", "account takeover"
]

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "IAM-Market-Monitor/3.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()

def strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def parse_date(value: str) -> dt.datetime:
    try:
        d = parsedate_to_datetime(value)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except Exception:
        return dt.datetime.now(dt.timezone.utc)

def canonical_title(title: str) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return " ".join(title.split())

def clean_title(title: str, source: str) -> str:
    title = strip_html(title)
    title = re.sub(rf"\s*-\s*{re.escape(source)}\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*-\s*[A-Za-z0-9.-]+\.(?:com|org|net|io)\s*$", "", title, flags=re.I)
    return title.strip(" -|")

def excluded(title: str, description: str, link: str) -> bool:
    t = title.lower()
    blob = f"{title} {description} {link}".lower()
    if any(term in t for term in TITLE_EXCLUSIONS):
        return True
    if any(term in blob for term in TEXT_EXCLUSIONS):
        return True
    return False

def section_scores(text: str) -> dict[str, int]:
    lower = text.lower()
    return {
        section: sum(2 if " " in term else 1 for term in terms if term in lower)
        for section, terms in SECTION_RULES.items()
    }

def tags_for(text: str) -> list[str]:
    lower = text.lower()
    tags = [tag for tag, terms in TAG_RULES.items() if any(term in lower for term in terms)]
    return tags[:4] or ["IAM"]

def confidence(text: str, source: str) -> str:
    lower = text.lower()
    matches = sum(1 for term in HIGH_CONFIDENCE_TERMS if term in lower)
    if source in {"Gartner", "KuppingerCole", "Okta Security"} and matches >= 1:
        return "High"
    if matches >= 2:
        return "High"
    if matches >= 1:
        return "Medium"
    return "Low"

def make_summary(description: str, title: str) -> str:
    clean = strip_html(description)
    clean = re.sub(r"\s*Read more.*$", "", clean, flags=re.I)
    if not clean or clean.lower() == title.lower():
        return "Open the original source for the full details."
    return clean[:340].rstrip(" ,.;") + ("…" if len(clean) > 340 else "")

def parse_feed(source_name: str, search_scope: str) -> list[dict]:
    query = urllib.parse.quote_plus(
        f'{search_scope} ("identity" OR "IAM" OR "authentication" OR "access" OR "security") when:7d'
    )
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    root = ET.fromstring(fetch(url))
    output = []

    for item in root.findall("./channel/item"):
        raw_title = item.findtext("title", "")
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "")
        published = parse_date(item.findtext("pubDate", ""))
        title = clean_title(raw_title, source_name)

        if excluded(title, description, link):
            continue

        output.append({
            "title": title,
            "url": link,
            "description": description,
            "published": published,
            "source": source_name,
        })

    return output

def load_existing_archive() -> dict[str, dict]:
    merged: dict[str, dict] = {}

    candidates = []
    if ALL_FILE.exists():
        candidates.append(ALL_FILE)
    if CURRENT_FILE.exists():
        candidates.append(CURRENT_FILE)
    if ARCHIVE.exists():
        candidates.extend(sorted(ARCHIVE.glob("*.json")))

    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for item in payload.get("items", []):
                key = canonical_title(item.get("title", ""))
                if key:
                    merged[key] = item
        except Exception:
            continue

    return merged

def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=LOOKBACK_DAYS)

    candidates: list[dict] = []
    errors: list[str] = []

    for source_name, search_scope in SEARCH_TARGETS:
        try:
            candidates.extend(parse_feed(source_name, search_scope))
        except Exception as exc:
            errors.append(f"{source_name} / {search_scope}: {exc}")

    unique: dict[str, dict] = {}

    for article in candidates:
        if article["published"] < cutoff:
            continue

        key = canonical_title(article["title"])
        if len(key) < 12:
            continue

        text = f'{article["title"]} {strip_html(article["description"])}'
        conf = confidence(text, article["source"])

        # Minimum-substance rule: do not auto-publish low-confidence items.
        if conf == "Low":
            continue

        scores = section_scores(text)
        primary = max(scores, key=scores.get)

        # Market Share Insights must be explicit, never inferred just because a vendor is mentioned.
        if primary == "Market Share Insights" and scores["Market Share Insights"] < 2:
            primary = "Latest IAM Trends"

        sections = [
            section for section, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if score >= 2
        ][:2]

        if not sections:
            sections = [primary]

        age_days = max(0, (now - article["published"]).days)
        recency_bonus = max(0, 5 - age_days)

        relevance = min(
            10,
            2
            + SOURCE_WEIGHT.get(article["source"], 2)
            + min(scores.get(primary, 0), 3)
            + recency_bonus
        )

        item = {
            "title": article["title"],
            "source": article["source"],
            "published_at": article["published"].isoformat(),
            "primary_section": primary,
            "sections": sections,
            "summary": make_summary(article["description"], article["title"]),
            "relevance": relevance,
            "confidence": conf,
            "url": article["url"],
            "tags": tags_for(text),
            "first_seen": now.isoformat(),
            "last_seen": now.isoformat(),
        }

        previous = unique.get(key)
        if previous is None or item["relevance"] > previous["relevance"]:
            unique[key] = item

    all_candidates = sorted(
        unique.values(),
        key=lambda x: (x["relevance"], x["published_at"]),
        reverse=True
    )

    # Vendor/source balance.
    current: list[dict] = []
    source_counts: dict[str, int] = {}

    # First ensure some section diversity.
    seen = set()
    for section in SECTION_RULES:
        for item in [i for i in all_candidates if section in i["sections"]][:3]:
            key = canonical_title(item["title"])
            src = item["source"]
            if key in seen or source_counts.get(src, 0) >= MAX_PER_SOURCE:
                continue
            current.append(item)
            seen.add(key)
            source_counts[src] = source_counts.get(src, 0) + 1

    # Fill remaining slots by relevance while respecting source cap.
    for item in all_candidates:
        if len(current) >= MAX_CURRENT_ITEMS:
            break
        key = canonical_title(item["title"])
        src = item["source"]
        if key in seen or source_counts.get(src, 0) >= MAX_PER_SOURCE:
            continue
        current.append(item)
        seen.add(key)
        source_counts[src] = source_counts.get(src, 0) + 1

    if not current:
        print("No suitable current items found; existing current feed was not overwritten.", file=sys.stderr)
        if errors:
            print("\n".join(errors), file=sys.stderr)
        return 1

    # Persistent searchable archive across weeks.
    archive_index = load_existing_archive()

    for item in current:
        key = canonical_title(item["title"])
        if key in archive_index:
            old = archive_index[key]
            item["first_seen"] = old.get("first_seen", old.get("published_at", item["first_seen"]))
        archive_index[key] = item

    all_articles = sorted(
        archive_index.values(),
        key=lambda x: x.get("published_at", ""),
        reverse=True
    )

    DATA.mkdir(exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    current_payload = {
        "generated_at": now.isoformat(),
        "items": current,
        "collector_notes": {
            "method": "Approved editorial/research paths only; hard exclusions; IAM relevance and confidence scoring; source balancing.",
            "errors": errors,
        },
    }

    all_payload = {
        "generated_at": now.isoformat(),
        "items": all_articles,
        "collector_notes": {
            "method": "Persistent cumulative index of all articles previously selected by the weekly collector."
        },
    }

    current_text = json.dumps(current_payload, indent=2, ensure_ascii=False) + "\n"
    all_text = json.dumps(all_payload, indent=2, ensure_ascii=False) + "\n"

    CURRENT_FILE.write_text(current_text, encoding="utf-8")
    ALL_FILE.write_text(all_text, encoding="utf-8")
    (ARCHIVE / f"{now.date().isoformat()}.json").write_text(current_text, encoding="utf-8")

    print(f"Wrote {len(current)} current articles")
    print(f"Searchable archive contains {len(all_articles)} articles")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
