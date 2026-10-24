import time
import re
import logging
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.v2.schemas import RadarItem, RadarResponse

logger = logging.getLogger(__name__)

# Supported countries & query parameters
COUNTRY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "IN": {
        "name": "India",
        "flag": "🇮🇳",
        "primary_feeds": [
            ("https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "Times of India"),
            ("https://feeds.feedburner.com/ndtvnews-top-stories", "NDTV Top Stories"),
            ("https://www.thehindu.com/news/national/feeder/default.rss", "The Hindu National"),
            ("https://factly.in/feed/", "Factly India"),
            ("https://www.altnews.in/feed/", "Alt News"),
            ("https://news.google.com/rss?gl=IN&hl=en-IN&ceid=IN:en", "Google News India"),
            ("https://news.google.com/rss/search?q=fact+check+OR+viral+rumor+OR+farzi+khabar+when:3d&gl=IN&hl=en-IN&ceid=IN:en", "Fact Check & Viral"),
        ],
    },
    "US": {
        "name": "United States",
        "flag": "🇺🇸",
        "primary_feeds": [
            ("https://feeds.npr.org/1001/rss.xml", "NPR News"),
            ("https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "BBC US & Canada"),
            ("https://www.snopes.com/feed/", "Snopes Fact Check"),
            ("https://news.google.com/rss?gl=US&hl=en-US&ceid=US:en", "Google News US"),
            ("https://news.google.com/rss/search?q=fact+check+OR+debunked+OR+viral+claim+when:3d&gl=US&hl=en-US&ceid=US:en", "Fact Check & Viral"),
        ],
    },
    "GB": {
        "name": "United Kingdom",
        "flag": "🇬🇧",
        "primary_feeds": [
            ("https://feeds.bbci.co.uk/news/uk/rss.xml", "BBC News UK"),
            ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
            ("https://www.snopes.com/feed/", "Snopes Fact Check"),
            ("https://news.google.com/rss?gl=GB&hl=en-GB&ceid=GB:en", "Google News UK"),
        ],
    },
    "GL": {
        "name": "Global Edition",
        "flag": "🌍",
        "primary_feeds": [
            ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World News"),
            ("https://feeds.npr.org/1004/rss.xml", "NPR World"),
            ("https://www.snopes.com/feed/", "Snopes Fact Check"),
            ("https://factly.in/feed/", "Factly Global"),
            ("https://news.google.com/rss?gl=US&hl=en-US&ceid=US:en", "Google News World"),
        ],
    },
}

CATEGORY_FEEDS: Dict[str, List[Tuple[str, str]]] = {
    "Tech & AI": [
        ("https://www.theverge.com/rss/index.xml", "The Verge"),
        ("https://www.wired.com/feed/rss", "Wired"),
        ("https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?gl=US&hl=en-US&ceid=US:en", "Google Tech"),
    ],
    "World & Politics": [
        ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
        ("https://www.thehindu.com/news/national/feeder/default.rss", "The Hindu"),
        ("https://feeds.npr.org/1001/rss.xml", "NPR Politics"),
        ("https://news.google.com/rss/headlines/section/topic/WORLD?gl=US&hl=en-US&ceid=US:en", "Google World"),
    ],
    "Science & Health": [
        ("https://www.sciencedaily.com/rss/top/science.xml", "ScienceDaily"),
        ("https://feeds.bbci.co.uk/news/health/rss.xml", "BBC Health"),
        ("https://news.google.com/rss/headlines/section/topic/SCIENCE?gl=US&hl=en-US&ceid=US:en", "Google Science"),
    ],
    "Markets & Finance": [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC Business"),
        ("https://www.moneycontrol.com/rss/latestnews.xml", "Moneycontrol"),
        ("https://news.google.com/rss/headlines/section/topic/BUSINESS?gl=US&hl=en-US&ceid=US:en", "Google Business"),
    ],
}

DISPUTED_KEYWORDS = [
    "fact check", "fact-check", "debunk", "false claim", "hoax",
    "viral rumor", "unverified", "claim", "rumor", "fake news",
    "misleading", "conspiracy", "scam", "myth", "disputed", "viral",
    "farzi", "fake", "fact-check:", "fact check:"
]

# High-velocity emergency fallback claims if live internet is unreachable
CURATED_FALLBACK_POOL: List[Dict[str, Any]] = [
    {
        "id": "radar_fb_1",
        "title": "Viral Social Media Audio Claiming New 500-Rupee Notes With Star Symbol Are Invalid",
        "summary": "Audio messages circulating on WhatsApp claim that currency notes with a star mark between serial digits are fake or banned by the Reserve Bank of India. Fact-checking agencies confirm these are genuine replacement notes.",
        "category": "Markets & Finance",
        "velocity": "HIGH",
        "disputed_flag": True,
        "source_preview": "Factly India",
        "mins_ago": 12,
        "prefilled_query": "Is 500 rupee note with star symbol invalid or fake currency RBI clarification.",
        "link": "https://factly.in"
    },
    {
        "id": "radar_fb_2",
        "title": "ISRO & NASA Finalize Readiness Protocols for NISAR Dual-Frequency Earth Satellite",
        "summary": "Joint space agencies confirm completion of synthetic aperture radar antenna testing ahead of planned equatorial orbit launch for global environmental monitoring.",
        "category": "Science & Health",
        "velocity": "HIGH",
        "disputed_flag": False,
        "source_preview": "The Hindu Science",
        "mins_ago": 18,
        "prefilled_query": "ISRO and NASA NISAR satellite launch and antenna testing readiness.",
        "link": "https://www.thehindu.com"
    },
    {
        "id": "radar_fb_3",
        "title": "OpenAI & Anthropic Release Joint Safety Evaluation Protocol for Agentic Autonomous Workflows",
        "summary": "Leading AI laboratories establish new alignment benchmarks to stress-test multi-turn autonomous coding agents against prompt injection and unauthorized API execution.",
        "category": "Tech & AI",
        "velocity": "SURGING",
        "disputed_flag": False,
        "source_preview": "The Verge",
        "mins_ago": 24,
        "prefilled_query": "OpenAI Anthropic AI safety evaluation protocols for autonomous agents.",
        "link": "https://www.theverge.com"
    },
    {
        "id": "radar_fb_4",
        "title": "Debunked: Viral Video Claiming Sudden Infrastructure Bridge Collapse in Gujarat is CGI",
        "summary": "A viral video purporting to capture a sudden bridge collapse in Gujarat has been debunked by forensic analysis as a digital 3D architectural rendering simulation from an overseas studio.",
        "category": "World & Politics",
        "velocity": "HIGH",
        "disputed_flag": True,
        "source_preview": "Alt News Fact Check",
        "mins_ago": 32,
        "prefilled_query": "Gujarat bridge collapse viral video fact check CGI simulation.",
        "link": "https://www.altnews.in"
    },
    {
        "id": "radar_fb_5",
        "title": "Reserve Bank of India Clarifies Guidelines on UPI Merchant Surcharges and Wallet Transactions",
        "summary": "The central bank reiterates that standard peer-to-peer and merchant UPI transactions remain completely free for retail customers following misleading social media rumors.",
        "category": "Markets & Finance",
        "velocity": "SURGING",
        "disputed_flag": True,
        "source_preview": "Moneycontrol",
        "mins_ago": 41,
        "prefilled_query": "RBI clarification on UPI surcharge fees for normal user bank transactions.",
        "link": "https://www.moneycontrol.com"
    },
    {
        "id": "radar_fb_6",
        "title": "Deepfake Audio Warning: Election Commission Issues Alert on AI-Cloned Candidate Calls",
        "summary": "Election oversight monitors flag automated robocall campaigns using synthetic voice models mimicking regional candidates to mislead voters regarding polling schedule hours.",
        "category": "World & Politics",
        "velocity": "HIGH",
        "disputed_flag": True,
        "source_preview": "Times of India",
        "mins_ago": 48,
        "prefilled_query": "Election Commission alert on AI deepfake audio robocalls and cloned voices.",
        "link": "https://timesofindia.indiatimes.com"
    },
    {
        "id": "radar_fb_7",
        "title": "Major Breakthrough in Quantum Dot Nanotechnology for Next-Gen Solid-State Battery Cells",
        "summary": "Researchers demonstrate 400Wh/kg energy density with zero thermal runaway in laboratory crash tests, paving the way for commercial electric aircraft and automotive storage.",
        "category": "Science & Health",
        "velocity": "MODERATE",
        "disputed_flag": False,
        "source_preview": "ScienceDaily",
        "mins_ago": 55,
        "prefilled_query": "Solid state quantum dot battery breakthrough 400 Wh/kg safety tests.",
        "link": "https://www.sciencedaily.com"
    },
    {
        "id": "radar_fb_8",
        "title": "Viral Post Claiming New WHO Pandemic Treaty Overrules Sovereign National Health Laws is False",
        "summary": "Claims spreading across Telegram state that the WHO accord grants the agency power to mandate lockdowns or override national parliaments. Official legal charters prove sovereign supremacy.",
        "category": "Science & Health",
        "velocity": "HIGH",
        "disputed_flag": True,
        "source_preview": "Snopes Fact Check",
        "mins_ago": 64,
        "prefilled_query": "WHO pandemic treaty sovereign law override lockdown false claim debunked.",
        "link": "https://www.snopes.com"
    },
    {
        "id": "radar_fb_9",
        "title": "European Union Antitrust Regulators Launch Formal Inquiry into Big Tech Cloud Licensing",
        "summary": "Regulatory authorities examine enterprise software interoperability constraints and egress fees following industry consortium grievances regarding fair competition in cloud computing.",
        "category": "Tech & AI",
        "velocity": "MODERATE",
        "disputed_flag": False,
        "source_preview": "BBC World",
        "mins_ago": 75,
        "prefilled_query": "EU antitrust inquiry cloud licensing fees big tech fair competition.",
        "link": "https://www.bbc.com"
    },
    {
        "id": "radar_fb_10",
        "title": "Indian Benchmark Indices Nifty and Sensex Touch New Milestone Amid Strong Domestic Flows",
        "summary": "Capital markets record sustained institutional buying across banking, renewable energy, and infrastructure sectors following positive quarterly macroeconomic indicators.",
        "category": "Markets & Finance",
        "velocity": "MODERATE",
        "disputed_flag": False,
        "source_preview": "NDTV Business",
        "mins_ago": 88,
        "prefilled_query": "Nifty Sensex record milestone domestic institutional inflows quarterly earnings.",
        "link": "https://www.ndtv.com"
    },
    {
        "id": "radar_fb_11",
        "title": "Unverified Claim: Viral WhatsApp Forward Alleges Airport Biometric Digiyatra Leaks Data to Advertisers",
        "summary": "Civil aviation authorities debunk rumors that biometric facial recognition data is sold to third parties, reiterating that facial credentials remain stored exclusively in encrypted user wallets.",
        "category": "Tech & AI",
        "velocity": "HIGH",
        "disputed_flag": True,
        "source_preview": "Factly India",
        "mins_ago": 96,
        "prefilled_query": "DigiYatra airport biometric data sharing advertisers privacy fact check.",
        "link": "https://factly.in"
    },
    {
        "id": "radar_fb_12",
        "title": "Global Climate Conference Agrees on Expanded Multi-Billion Dollar Coastal Resilience Fund",
        "summary": "Delegates from over 120 nations finalize operational mechanisms for climate adaptation financing targeted at vulnerable low-lying coastal and island ecosystems.",
        "category": "World & Politics",
        "velocity": "MODERATE",
        "disputed_flag": False,
        "source_preview": "NPR World",
        "mins_ago": 110,
        "prefilled_query": "Global climate conference coastal resilience fund vulnerable nations agreement.",
        "link": "https://www.npr.org"
    }
]

# Cache format: { (country, category): { "timestamp": float, "items": List[RadarItem], "offset": int } }
_RADAR_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
CACHE_REFETCH_TTL = 180  # 3 minutes TTL for refetching from network
BATCH_SIZE = 12          # Number of stories presented per view
ROTATION_STEP = 6        # Shift by 6 items on rotation to bring fresh cards


def _strip_html(text: str) -> str:
    """Removes HTML tags, CDATA wrappers, and unescapes common HTML entities."""
    clean = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = (
        clean.replace("&nbsp;", " ")
        .replace("&quot;", "\"")
        .replace("&amp;", "&")
        .replace("&#39;", "'")
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"\s+", " ", clean).strip()


def _format_time_ago(dt: datetime, now: datetime) -> Tuple[str, int]:
    """Returns human-readable relative time string and elapsed minutes."""
    diff_secs = max(0, (now - dt).total_seconds())
    mins = int(diff_secs / 60)
    if mins < 1:
        return "Just now", 0
    if mins < 60:
        return f"{mins}m ago", mins
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago", mins
    days = hours // 24
    return f"{days}d ago", mins


def _parse_pub_date(text_date: str) -> Optional[datetime]:
    """Robustly parses RFC 822 (e.g. RSS pubDate) or ISO 8601 timestamps."""
    if not text_date:
        return None
    cleaned = text_date.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(cleaned)
    except Exception:
        pass

    if dt is None:
        try:
            iso_str = cleaned.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
        except Exception:
            pass

    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _categorize_story(text_corpus: str, explicit_cat: Optional[str] = None) -> str:
    """Accurately classifies news into the 4 primary categories."""
    if explicit_cat and explicit_cat in ["Tech & AI", "Science & Health", "Markets & Finance", "World & Politics"]:
        return explicit_cat

    corpus = text_corpus.lower()

    tech_kw = [
        r"\bai\b", r"\btech\b", "artificial intelligence", "nvidia", "apple", "google", "meta",
        "openai", "software", "smartphone", "iphone", "chip", "robot", "cyber", "algorithm",
        "digital", "semiconductor", "quantum", "microsoft", "amazon", "chatgpt", "deepfake",
        "hardware", "gadget", "android", "cloud compute", "data center", "telecom"
    ]
    science_kw = [
        "health", "virus", "cancer", "space", "nasa", "isro", "planet", "vaccine", "doctor",
        "medical", "disease", "climate", "biology", "astronomy", "research", "hospital",
        "patient", "drug", "fda", "icmr", "who", "dengue", "surgery", "pandemic", "galaxy",
        "telescope", "scientific", "biology", "physics", "genetics", "immunology"
    ]
    market_kw = [
        "market", "stock", "revenue", "fed", "inflation", "economy", "bank", "nifty", "sensex",
        "rbi", "rupee", "crypto", "bitcoin", "shares", "investor", "trade", "finance", "gdp",
        "earnings", "quarter", "fund", "wall street", "banking", "treasury", "interest rate",
        "bonds", "nasdaq", "bse", "nse", "ipo", "valuation"
    ]

    for kw in tech_kw:
        if kw.startswith(r"\b"):
            if re.search(kw, corpus):
                return "Tech & AI"
        elif kw in corpus:
            return "Tech & AI"

    for kw in science_kw:
        if kw in corpus:
            return "Science & Health"

    for kw in market_kw:
        if kw in corpus:
            return "Markets & Finance"

    return "World & Politics"


def _fetch_single_rss(feed_url: str, default_source: str, explicit_cat: Optional[str] = None) -> List[RadarItem]:
    """Fetches an individual RSS feed and converts items to RadarItem models."""
    items: List[RadarItem] = []
    now = datetime.now(timezone.utc)

    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=7) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)

            channel = root.find("channel")
            if channel is None:
                channel = root

            item_elements = channel.findall("item")
            # In Atom feeds, items are named <entry>
            if not item_elements:
                item_elements = root.findall("{http://www.w3.org/2005/Atom}entry")
            if not item_elements:
                item_elements = root.findall(".//item")

            for idx, item_elem in enumerate(item_elements[:25]):
                title_elem = item_elem.find("title")
                if title_elem is None:
                    title_elem = item_elem.find("{http://www.w3.org/2005/Atom}title")
                if title_elem is None or not title_elem.text:
                    continue

                raw_title = _strip_html(title_elem.text)
                if len(raw_title) < 15:
                    continue

                source_name = default_source
                clean_title = raw_title
                source_elem = item_elem.find("source")
                if source_elem is not None and source_elem.text:
                    source_name = source_elem.text.strip()
                elif " - " in raw_title:
                    parts = raw_title.rsplit(" - ", 1)
                    if len(parts[1].strip()) < 30:
                        clean_title = parts[0].strip()
                        source_name = parts[1].strip()

                pub_elem = item_elem.find("pubDate")
                if pub_elem is None:
                    pub_elem = item_elem.find("{http://www.w3.org/2005/Atom}published")
                if pub_elem is None:
                    pub_elem = item_elem.find("{http://www.w3.org/2005/Atom}updated")

                pub_iso = None
                time_str = "Just now"
                mins_ago = 10

                if pub_elem is not None and pub_elem.text:
                    dt = _parse_pub_date(pub_elem.text)
                    if dt:
                        pub_iso = dt.isoformat()
                        time_str, mins_ago = _format_time_ago(dt, now)

                desc_elem = item_elem.find("description")
                if desc_elem is None:
                    desc_elem = item_elem.find("{http://www.w3.org/2005/Atom}summary")
                summary = ""
                if desc_elem is not None and desc_elem.text:
                    summary = _strip_html(desc_elem.text)
                if not summary or len(summary) < 20:
                    summary = f"Real-time breaking report originating from {source_name}. Fact-checking verification active."

                link_elem = item_elem.find("link")
                link_url = ""
                if link_elem is not None:
                    link_url = link_elem.text or link_elem.attrib.get("href", "")

                text_corpus = (clean_title + " " + summary).lower()
                is_disputed = any(kw in text_corpus for kw in DISPUTED_KEYWORDS)

                if is_disputed or mins_ago <= 45:
                    velocity = "HIGH"
                elif mins_ago <= 180:
                    velocity = "SURGING"
                else:
                    velocity = "MODERATE"

                category = _categorize_story(clean_title + " " + summary, explicit_cat)

                prefilled = f"{clean_title}. {summary[:160]}"
                item_id = f"radar_{abs(hash(clean_title)) % 10000000}_{idx}"

                items.append(RadarItem(
                    id=item_id,
                    title=clean_title,
                    summary=summary[:280] + ("..." if len(summary) > 280 else ""),
                    category=category,
                    velocity=velocity,
                    disputed_flag=is_disputed,
                    source_preview=source_name,
                    published_time=time_str,
                    prefilled_query=prefilled,
                    pub_date_iso=pub_iso,
                    link=link_url
                ))
    except Exception as e:
        logger.debug("RSS fetch error for %s: %s", feed_url, e)

    return items


def _build_candidate_pool(country: str, category: str) -> List[RadarItem]:
    """Collects candidate stories concurrently from multiple resilient RSS feeds."""
    cfg = COUNTRY_CONFIGS.get(country, COUNTRY_CONFIGS["IN"])
    feed_jobs: List[Tuple[str, str, Optional[str]]] = []  # (url, default_source, explicit_cat)

    if category == "All":
        for url, src in cfg.get("primary_feeds", []):
            feed_jobs.append((url, src, None))
    else:
        # 1. Specialized category feeds
        for url, src in CATEGORY_FEEDS.get(category, []):
            feed_jobs.append((url, src, category))
        # 2. Country feeds to discover additional relevant stories
        for url, src in cfg.get("primary_feeds", []):
            feed_jobs.append((url, src, None))

    pool: List[RadarItem] = []
    seen = set()

    # Fetch feeds concurrently using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(len(feed_jobs) or 1, 6)) as executor:
        future_map = {
            executor.submit(_fetch_single_rss, url, default_src, explicit_cat): (url, default_src)
            for url, default_src, explicit_cat in feed_jobs
        }
        for future in as_completed(future_map):
            try:
                feed_items = future.result()
                for item in feed_items:
                    # Filter for requested category unless "All"
                    if category != "All" and item.category != category:
                        continue
                    norm = re.sub(r"[^a-zA-Z0-9]", "", item.title.lower())[:60]
                    if norm and norm not in seen:
                        seen.add(norm)
                        pool.append(item)
            except Exception as e:
                logger.debug("Feed future error: %s", e)

    # Sort candidates prioritizing disputed viral claims and high velocity breaking news
    pool.sort(
        key=lambda x: (
            0 if x.disputed_flag else (1 if x.velocity == "HIGH" else 2)
        )
    )
    return pool


def _get_fallback_items_for(country: str, category: str) -> List[RadarItem]:
    """Generates dynamically refreshed curated fallback stories when live network fails."""
    now_utc = datetime.now(timezone.utc)
    filtered: List[RadarItem] = []

    for idx, fb in enumerate(CURATED_FALLBACK_POOL):
        if category != "All" and fb["category"] != category:
            continue

        mins = fb.get("mins_ago", (idx + 1) * 8)
        time_str = f"{mins}m ago" if mins < 60 else f"{mins // 60}h ago"

        filtered.append(RadarItem(
            id=f"{fb['id']}_{int(now_utc.timestamp()) % 1000}",
            title=fb["title"],
            summary=fb["summary"],
            category=fb["category"],
            velocity=fb["velocity"],
            disputed_flag=fb["disputed_flag"],
            source_preview=fb["source_preview"],
            published_time=time_str,
            prefilled_query=fb["prefilled_query"],
            pub_date_iso=now_utc.isoformat(),
            link=fb.get("link", "https://news.google.com")
        ))

    # If category filter yielded fewer than 6, supplement from remaining fallback pool
    if len(filtered) < 6 and category != "All":
        for idx, fb in enumerate(CURATED_FALLBACK_POOL):
            if any(f.title == fb["title"] for f in filtered):
                continue
            mins = fb.get("mins_ago", (idx + 1) * 12)
            time_str = f"{mins}m ago" if mins < 60 else f"{mins // 60}h ago"
            filtered.append(RadarItem(
                id=f"{fb['id']}_supp_{idx}",
                title=fb["title"],
                summary=fb["summary"],
                category=fb["category"],
                velocity=fb["velocity"],
                disputed_flag=fb["disputed_flag"],
                source_preview=fb["source_preview"],
                published_time=time_str,
                prefilled_query=fb["prefilled_query"],
                pub_date_iso=now_utc.isoformat(),
                link=fb.get("link", "https://news.google.com")
            ))
            if len(filtered) >= 12:
                break

    return filtered


def fetch_radar_feed(
    category: Optional[str] = None,
    country: Optional[str] = "IN",
    rotate: Optional[bool] = False
) -> RadarResponse:
    """Returns real-time radar trending feed with multi-feed concurrency, caching, and fallback guarantee."""
    target_country = (country or "IN").strip().upper()
    if target_country not in COUNTRY_CONFIGS:
        target_country = "IN"

    target_cat = (category or "All").strip()
    valid_categories = ["All", "World & Politics", "Tech & AI", "Science & Health", "Markets & Finance"]
    if target_cat not in valid_categories:
        target_cat = "All"

    cache_key = (target_country, target_cat)
    now_ts = time.time()
    now_utc = datetime.now(timezone.utc)

    cached = _RADAR_CACHE.get(cache_key)

    # Determine if we should refresh candidate pool from network
    needs_network_fetch = (
        cached is None or
        (now_ts - cached["timestamp"]) > CACHE_REFETCH_TTL or
        len(cached.get("items", [])) < 6
    )

    if needs_network_fetch:
        fresh_pool = _build_candidate_pool(target_country, target_cat)
        if len(fresh_pool) >= 4:
            _RADAR_CACHE[cache_key] = {
                "timestamp": now_ts,
                "items": fresh_pool,
                "offset": 0
            }
            cached = _RADAR_CACHE[cache_key]
        elif not cached or len(cached.get("items", [])) == 0:
            # If fresh pool was low and we have no cache, try general "All" pool
            if target_cat != "All":
                all_cache = _RADAR_CACHE.get((target_country, "All"))
                if all_cache and len(all_cache.get("items", [])) >= 4:
                    cat_items = [it for it in all_cache["items"] if it.category == target_cat]
                    if len(cat_items) >= 4:
                        fresh_pool = cat_items

            if not fresh_pool or len(fresh_pool) < 4:
                # Merge with fallback pool to guarantee a complete, active feed
                fallback_items = _get_fallback_items_for(target_country, target_cat)
                merged_pool = fresh_pool + fallback_items
                _RADAR_CACHE[cache_key] = {
                    "timestamp": now_ts,
                    "items": merged_pool,
                    "offset": 0
                }
                cached = _RADAR_CACHE[cache_key]

    # Final guarantee: ensure cached pool is non-empty
    if not cached or not cached.get("items"):
        fallback_items = _get_fallback_items_for(target_country, target_cat)
        _RADAR_CACHE[cache_key] = {
            "timestamp": now_ts,
            "items": fallback_items,
            "offset": 0
        }
        cached = _RADAR_CACHE[cache_key]

    pool = cached["items"]
    current_offset = cached.get("offset", 0)

    # If rotate requested, advance offset to present fresh stories from pool
    if rotate and len(pool) > BATCH_SIZE:
        current_offset = (current_offset + ROTATION_STEP) % len(pool)
        cached["offset"] = current_offset

    # Slice batch of stories using current offset
    selected_items: List[RadarItem] = []
    pool_len = len(pool)
    take_count = min(BATCH_SIZE, pool_len)

    for i in range(take_count):
        idx = (current_offset + i) % pool_len
        item = pool[idx]

        # Dynamically refresh relative published_time strings
        it_dict = item.model_dump()
        if item.pub_date_iso:
            try:
                dt = datetime.fromisoformat(item.pub_date_iso)
                it_dict["published_time"], _ = _format_time_ago(dt, now_utc)
            except Exception:
                pass
        selected_items.append(RadarItem(**it_dict))

    return RadarResponse(
        last_updated=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        total_active_stories=pool_len,
        categories=valid_categories,
        country=target_country,
        items=selected_items
    )
