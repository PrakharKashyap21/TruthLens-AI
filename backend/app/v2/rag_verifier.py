import os
import re
import json
import logging
import urllib.parse
import datetime
from typing import List, Dict, Any, Optional
try:
    from dotenv import load_dotenv
    load_dotenv("backend/.env")
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Import schemas
from backend.app.v2.schemas import (
    VerificationRequest,
    VerificationResponse,
    ClaimVerificationDetail,
    ClaimVerdict,
    OverallAssessment,
    EvidenceItem,
    EvidenceSourceType,
    StanceType,
    EvidenceStrength,
    UncertaintyLevel,
    ClaimEvidenceSummary,
    LinguisticSignal,
    DocumentClaimAudit,
    DocumentAuditResponse,
    VernacularAuditInfo,
)

HINGLISH_KEYWORDS = {
    "karega", "karenge", "karti", "sarkar", "sarkaar", "yojna", "yojana",
    "khabar", "daawa", "dawa", "aadesh", "faisla", "rupaye", "rupey",
    "paisa", "paise", "nakli", "asli", "waale", "wale", "sabko", "milega",
    "milegi", "band", "khulenge", "chutti", "aaya", "aayi", "gaya", "gayi",
    "hoga", "hogi", "nahi", "nahin", "nhi", "mat", "karo", "dekho", "viral",
    "whatsapp", "such", "jhooth", "jhoot", "dhokha", "bacho", "parivar",
    "kehta", "kehti", "bheja", "bhej", "rahe", "rahi", "hai", "hain", "kare"
}

class GeminiRAGVerifier:
    """
    Production-grade RAG Verification Engine combining:
    1. Live Web & Breaking News search (DDGS)
    2. Full-text content extraction (trafilatura & bs4)
    3. Multilingual Vernacular processing (Hindi, Hinglish, Bengali, Tamil, etc.)
    4. Gemini AI Multimodal/Reasoning models with auto-fallback
    5. Structured JSON evidence attribution & verification verdicts
    """

    def __init__(self, api_key: Optional[str] = None):
        raw_key = api_key or os.getenv("GEMINI_API_KEY") or ""
        self.api_key = raw_key.strip().strip('"').strip("'")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI Client: %s", e)

        self.candidate_models = [
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemma-4-26b-a4b-it"
        ]

    def _detect_language(self, text: str, user_hint: Optional[str] = None) -> tuple[str, str]:
        """Detect language or script of claim text, honoring explicit user hints."""
        if user_hint and user_hint.lower() not in ["auto", ""]:
            hint = user_hint.lower().strip()
            if hint in ["hi", "hindi"]:
                return "hi", "Hindi (हिन्दी)"
            elif hint in ["hinglish"]:
                return "hinglish", "Hinglish (Roman Hindi)"
            elif hint in ["bn", "bengali"]:
                return "bn", "Bengali (বাংলা)"
            elif hint in ["ta", "tamil"]:
                return "ta", "Tamil (தமிழ்)"
            elif hint in ["te", "telugu"]:
                return "te", "Telugu (తెలుగు)"
            elif hint in ["mr", "marathi"]:
                return "mr", "Marathi (मराठी)"
            elif hint in ["en", "english"]:
                return "en", "English"

        # Unicode script detection
        if re.search(r'[\u0900-\u097F]', text):
            return "hi", "Hindi (हिन्दी)"
        if re.search(r'[\u0980-\u09FF]', text):
            return "bn", "Bengali (বাংলা)"
        if re.search(r'[\u0B80-\u0BFF]', text):
            return "ta", "Tamil (தமிழ்)"
        if re.search(r'[\u0C00-\u0C7F]', text):
            return "te", "Telugu (తెలుగు)"

        # Hinglish romanized vocabulary detection
        words = [w.lower().strip(",.?!;:\"'()") for w in text.split()]
        matching_hinglish = [w for w in words if w in HINGLISH_KEYWORDS]
        if len(matching_hinglish) >= 2 or (len(words) > 0 and (len(matching_hinglish) / len(words)) >= 0.15):
            return "hinglish", "Hinglish (Roman Hindi)"

        return "en", "English"

    DISALLOWED_DOMAINS = {
        "looksmax.org", "4chan.org", "kiwifarms.net", "stormfront.org",
        "reddit.com", "quora.com", "pinterest.com", "tiktok.com",
        "facebook.com", "instagram.com"
    }

    def _extract_search_keywords(self, text: str, max_words: int = 7) -> str:
        """Extracts high-signal entity and action keywords from claims to optimize search precision."""
        if not text:
            return ""
        # Strip conversational prefixes
        cleaned = re.sub(
            r'(?i)^(whatsapp forward|social media|breaking news|viral message|claims that|says that|according to|keh raha hai ki|bata raha hai ki|dawa kiya ja raha hai ki)\s*[:,-]?\s*',
            '',
            text.strip()
        )
        words = [re.sub(r'^[^\w]+|[^\w]+$', '', w) for w in cleaned.split()]
        stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
            'when', 'where', 'how', 'who', 'which', 'this', 'that', 'these', 'those',
            'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 'into',
            'over', 'after', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can',
            'could', 'should', 'may', 'might', 'shall', 'must', 'to', 'from', 'up',
            'down', 'in', 'out', 'on', 'off', 'for', 'with', 'by', 'at', 'it', 'its',
            'reported', 'reporting', 'quarter', 'year-on-year'
        }
        kw = [w for w in words if w and w.lower() not in stopwords and len(w) > 1]
        return ' '.join(kw[:max_words]) if kw else cleaned[:60]

    def _search_web_and_news(self, query: str, max_results: int = 4, region: str = "in-en") -> List[Dict[str, str]]:
        """Search live news and web articles with regional localization and news-first priority."""
        results = []
        seen_urls = set()

        try:
            from ddgs import DDGS
            ddgs = DDGS()
        except ImportError:
            return []

        kw_query = self._extract_search_keywords(query)
        clean_q = re.sub(r'["\n\r]', ' ', query).strip()[:80]

        # Strategic search query cascade: prioritized for verified journalism
        attempts = [
            ("news", kw_query),
            ("news", f"{kw_query} fact check" if "fact check" not in kw_query.lower() else kw_query),
            ("news", clean_q),
            ("text", f"{kw_query} news" if kw_query else clean_q),
            ("text", f"{kw_query} fact check" if kw_query else clean_q),
        ]

        # Phase 1: Search with preferred region (default Indian in-en)
        for mode, q_str in attempts:
            if not q_str or len(results) >= max_results:
                break
            try:
                if mode == "news":
                    raw_items = list(ddgs.news(q_str, region=region, max_results=max_results))
                else:
                    raw_items = list(ddgs.text(q_str, region=region, max_results=max_results))

                for item in raw_items:
                    url = item.get("url") or item.get("href") or ""
                    title = (item.get("title") or "").strip()
                    body = (item.get("body") or "").strip()

                    if not url or not title or url in seen_urls:
                        continue

                    # Filter out spam/forum domains
                    try:
                        parsed = urllib.parse.urlparse(url)
                        domain = parsed.netloc.lower().replace("www.", "")
                        if any(bad in domain for bad in self.DISALLOWED_DOMAINS):
                            continue
                    except Exception:
                        pass

                    seen_urls.add(url)
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": body
                    })

                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.debug("DDGS %s search exception for '%s' (region=%s): %s", mode, q_str, region, e)

        # Phase 2: If regional search returned 0 items, fallback to worldwide (wt-wt)
        if not results and region != "wt-wt":
            for mode, q_str in attempts[:2]:
                if len(results) >= max_results:
                    break
                try:
                    if mode == "news":
                        raw_items = list(ddgs.news(q_str, region="wt-wt", max_results=max_results))
                    else:
                        raw_items = list(ddgs.text(q_str, region="wt-wt", max_results=max_results))
                    for item in raw_items:
                        url = item.get("url") or item.get("href") or ""
                        title = (item.get("title") or "").strip()
                        body = (item.get("body") or "").strip()
                        if not url or not title or url in seen_urls:
                            continue
                        try:
                            parsed = urllib.parse.urlparse(url)
                            domain = parsed.netloc.lower().replace("www.", "")
                            if any(bad in domain for bad in self.DISALLOWED_DOMAINS):
                                continue
                        except Exception:
                            pass
                        seen_urls.add(url)
                        results.append({"title": title, "url": url, "snippet": body})
                        if len(results) >= max_results:
                            break
                except Exception:
                    pass

        return results[:max_results]

    def _extract_article_content(self, url: str, fallback_snippet: str = "") -> str:
        """Extract clean body text from source URL using trafilatura with strict timeout."""
        if not url:
            return fallback_snippet
        try:
            import trafilatura
            # Strict timeout of 2.5s to prevent slow external websites from blocking
            downloaded = trafilatura.fetch_url(url, timeout=2.5)
            if downloaded:
                extracted = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False
                )
                if extracted and len(extracted.strip()) > 80:
                    return extracted.strip()[:1500]
        except Exception:
            pass
        return fallback_snippet

    KNOWN_PUBLISHERS = [
        ("moneycontrol", "Moneycontrol"),
        ("the hindu", "The Hindu"),
        ("economic times", "The Economic Times"),
        ("livemint", "Livemint"),
        ("business standard", "Business Standard"),
        ("business today", "Business Today"),
        ("times of india", "Times of India"),
        ("financial express", "Financial Express"),
        ("ndtv", "NDTV"),
        ("india today", "India Today"),
        ("pib fact check", "PIB Fact Check"),
        ("pib", "PIB (Govt of India)"),
        ("rbi", "Reserve Bank of India"),
        ("bbc", "BBC News"),
        ("reuters", "Reuters"),
        ("bloomberg", "Bloomberg"),
        ("press trust of india", "PTI"),
        ("pti", "PTI"),
        ("ani", "ANI"),
        ("zee news", "Zee News"),
        ("hindustan times", "Hindustan Times"),
        ("indian express", "The Indian Express"),
        ("cnbc", "CNBC-TV18"),
        ("nasa", "NASA"),
        ("world health organization", "World Health Organization"),
        ("isro", "ISRO"),
        ("alt news", "Alt News"),
        ("boom", "BOOM Live"),
        ("vishvas news", "Vishvas News"),
        ("the quint", "The Quint WebQoof"),
    ]

    def _get_publisher_and_domain(self, url: str, title: str = "", snippet: str = "") -> tuple[str, str]:
        """Extract domain and friendly, authentic publisher name from URL and syndicated article metadata."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.replace("www.", "")

            # Check title, snippet, and url for recognized media houses (crucial for MSN/Yahoo syndication)
            comb_text = f"{title} {snippet} {url}".lower()
            for kw, pub_name in self.KNOWN_PUBLISHERS:
                if len(kw) <= 4:
                    if re.search(r'\b' + re.escape(kw) + r'\b', comb_text):
                        return pub_name, domain
                else:
                    if kw in comb_text:
                        return pub_name, domain

            parts = domain.split(".")
            if len(parts) >= 3 and parts[0].lower() in ["en", "hi", "m", "news", "www3", "amp", "beta", "edition", "in"]:
                publisher = parts[-2].capitalize()
            elif parts:
                publisher = parts[0].capitalize()
            else:
                publisher = domain

            if publisher.lower() == "msn":
                if any(w in comb_text for w in ["share", "stock", "revenue", "q2", "rs", "crore", "market"]):
                    publisher = "MSN Financial News"
                else:
                    publisher = "MSN News"

            return publisher, domain
        except Exception:
            return "Unknown", "unknown"

    def _fetch_all_docs_concurrently(self, search_results: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Fetch multiple article bodies in parallel with bounded time."""
        import concurrent.futures

        def _fetch_one(item):
            body = self._extract_article_content(item["url"], item["snippet"])
            pub, dom = self._get_publisher_and_domain(item["url"], title=item["title"], snippet=item["snippet"])
            return {
                "title": item["title"],
                "url": item["url"],
                "publisher": pub,
                "domain": dom,
                "snippet": item["snippet"],
                "content": body
            }

        results_by_url = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, len(search_results)))) as executor:
            future_to_item = {executor.submit(_fetch_one, item): item for item in search_results}
            for future in concurrent.futures.as_completed(future_to_item, timeout=5.0):
                try:
                    res = future.result()
                    results_by_url[res["url"]] = res
                except Exception:
                    pass

        # Preserve deterministic order of original search results
        evidence_docs = []
        for item in search_results:
            if item["url"] in results_by_url:
                evidence_docs.append(results_by_url[item["url"]])
            else:
                pub, dom = self._get_publisher_and_domain(item["url"], title=item["title"], snippet=item["snippet"])
                evidence_docs.append({
                    "title": item["title"],
                    "url": item["url"],
                    "publisher": pub,
                    "domain": dom,
                    "snippet": item["snippet"],
                    "content": item["snippet"]
                })

        return evidence_docs

    def _generate_fact_check_queries(self, claim_text: str) -> List[str]:
        """Uses Gemini to translate and optimize claims into sharp English fact-checking search queries."""
        if not self.client:
            return [self._extract_search_keywords(claim_text)]

        clean_text = claim_text.strip()[:180]
        prompt = f"""You are a fact-checking search specialist. Given this claim (which may be in Hindi, Hinglish, or English):
\"{clean_text}\"

Generate 2 concise, highly specific English search queries (3 to 6 words each) that will find official news reports, government fact-checks (like PIB Fact Check), or debunks.
Return ONLY the 2 queries separated by a newline, with no extra text or numbering."""
        try:
            resp = self.client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )
            if resp and resp.text:
                queries = []
                for q in resp.text.strip().split('\n'):
                    q_clean = re.sub(r'^[0-9\.\-\*\s"\']+|[0-9\.\-\*\s"\']+$', '', q).strip()
                    if len(q_clean) >= 4 and len(q_clean.split()) >= 2:
                        queries.append(q_clean)
                if queries:
                    return queries[:2]
        except Exception as e:
            logger.debug("AI query generation exception: %s", e)

        return [self._extract_search_keywords(claim_text)]

    def _search_multilingual_evidence(self, query: str, lang_code: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Search live web and news articles with cross-lingual query construction."""
        results = []
        seen_urls = set()

        # Step 1: Generate AI-optimized English fact-checking queries
        queries_to_try = self._generate_fact_check_queries(query)

        # Step 2: Add keyword and regional variations
        kw_query = self._extract_search_keywords(query)
        if kw_query and kw_query not in queries_to_try:
            queries_to_try.append(kw_query)

        if lang_code in ["hi", "hinglish"]:
            if "pib" not in " ".join(queries_to_try).lower():
                queries_to_try.append(f"{kw_query} PIB fact check")
        elif lang_code == "en":
            clean_q = re.sub(r'["\n\r]', ' ', query).strip()[:80]
            if clean_q not in queries_to_try:
                queries_to_try.append(clean_q)

        # Step 3: Determine optimal regional search index (prioritize Indian context unless purely global)
        global_indicators = ["nasa", "trump", "biden", "white house", "ukraine", "putin", "israel", "gaza", "pentagon", "fed", "elon musk", "tesla"]
        q_lower = query.lower()
        if any(ind in q_lower for ind in global_indicators) and lang_code == "en" and "india" not in q_lower and "isro" not in q_lower:
            target_region = "wt-wt"
        else:
            target_region = "in-en"

        # Step 4: Search news and web articles
        for q in queries_to_try:
            items = self._search_web_and_news(q, max_results=max_results, region=target_region)
            for it in items:
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    results.append(it)
            if len(results) >= max_results:
                break

        return results[:max_results]

    def verify_claim(self, claim_text: str, claim_id: str = "c1", language_hint: Optional[str] = "auto", seed_url: Optional[str] = None) -> Dict[str, Any]:
        """Verify a single claim against live web evidence and Gemini reasoning with vernacular support."""
        # Step 0: Language & script detection
        lang_code, lang_name = self._detect_language(claim_text, language_hint)

        # Step 1: Retrieve search results (with multilingual cross-querying)
        search_results = self._search_multilingual_evidence(claim_text, lang_code, max_results=4)
        
        # Step 2: Fetch article text context in parallel (max 3s)
        evidence_docs = self._fetch_all_docs_concurrently(search_results)

        # Step 2b: If a seed source URL was provided (e.g. from Radar card), ingest and prepend it as primary evidence
        if seed_url and seed_url.startswith("http"):
            try:
                seed_body = self._extract_article_content(seed_url, "")
                pub, dom = self._get_publisher_and_domain(seed_url)
                seed_doc = {
                    "title": f"Source Wire Report ({pub})",
                    "url": seed_url,
                    "publisher": pub,
                    "domain": dom,
                    "snippet": seed_body[:300] if seed_body else "Direct breaking news wire article provided via Radar stream.",
                    "content": seed_body or "Direct breaking news wire article provided via Radar stream."
                }
                # Prepend seed doc as primary source [1] and keep top external cross-sources
                evidence_docs = [seed_doc] + [d for d in evidence_docs if d.get("url") != seed_url][:3]
            except Exception as e:
                logger.debug("Failed to ingest seed_url %s: %s", seed_url, e)

        # If no client or no key, return heuristic fallback
        if not self.client:
            return self._fallback_response(claim_text, claim_id, evidence_docs, lang_code, lang_name)

        # Step 3: Construct prompt for Gemini Reasoning
        sources_text = ""
        for idx, doc in enumerate(evidence_docs, 1):
            sources_text += f"\n\nSource [{idx}]:\nTitle: {doc['title']}\nPublisher: {doc['publisher']} ({doc['domain']})\nURL: {doc['url']}\nContext: {doc['content'] or doc['snippet']}"

        vernacular_instructions = ""
        if lang_code != "en":
            vernacular_instructions = f"""
6. MULTILINGUAL & VERNACULAR ATTRIBUTION ({lang_name}):
   - In "native_verdict_label", write the verdict in {lang_name}:
     * If SUPPORTED: "पुष्ट (SUPPORTED)"
     * If CONTRADICTED: "असत्य / फर्जी (CONTRADICTED)"
     * If MISLEADING: "भ्रामक (MISLEADING)"
     * If UNVERIFIED: "अपुष्ट (UNVERIFIED)"
   - In "native_explanation", write an objective, clear 2-3 sentence explanation in {lang_name} summarizing the findings.
   - In "native_key_findings", provide 2-3 concise bullet points written in {lang_name}.
   - In "translated_claim_en", provide an accurate English translation of the claim.
"""

        prompt = f"""You are an elite, objective, real-time News and Fact-Checking AI system.
Evaluate the following CLAIM against the provided EVIDENCE retrieved from live sources.

CLAIM TO VERIFY:
"{claim_text}"
DETECTED CLAIM LANGUAGE: {lang_name} ({lang_code})

EVIDENCE SOURCES:
{sources_text if sources_text else "No external evidence found."}

INSTRUCTIONS:
1. Determine the exact VERDICT:
   - "SUPPORTED": The factual proposition, core entities, numbers, and events in the claim are substantiated by credible evidence.
   - "CONTRADICTED": The claim is proven false, fabricated, debunked, or factually inaccurate by credible reporting.
   - "MISLEADING": The claim mixes truth with falsehoods, distorts context, or exaggerates numbers.
   - "UNVERIFIED": Insufficient or no reliable evidence found to independently confirm or debunk the claim.
   * BREAKING & DEVELOPING STORIES: If credible mainstream news reports confirm the overarching event (such as police inquiries, major accidents, policy decisions, summits), but secondary forensic or micro-details (e.g. exact recovery counts, transit routes) are still emerging, confirm the main event and note that granular specifics are currently developing across live reporting.
2. Assign a confidence score (0.0 to 1.0).
3. Write a clear, objective 2-3 sentence explanation in English summarizing the verdict and why.
4. Provide 2-3 key findings in English.
5. CRITICAL: For each source (Source [1], Source [2], etc.), evaluate its stance RELATIVE TO THE CLAIM:
   - "CONTRADICTS": If the source refutes, debunks, disproves, denies, or warns against the claim (e.g. calls it fake, a scam, a hoax, false, baseless, or clarifies that no such order/scheme exists).
   - "SUPPORTS": If the source confirms, corroborates, validates, or proves the claim is authentic and true.
   - "NEUTRAL": If the source provides general background context without directly confirming or refuting the claim.{vernacular_instructions}

OUTPUT FORMAT:
Return strictly a valid JSON object matching this schema:
{{
  "verdict": "SUPPORTED" | "CONTRADICTED" | "MISLEADING" | "UNVERIFIED",
  "confidence": 0.95,
  "explanation": "Plain language explanation in English.",
  "native_verdict_label": "Verdict label in native language",
  "native_explanation": "Explanation in native language if non-English, else same as explanation",
  "native_key_findings": ["Finding 1 in native language", "Finding 2 in native language"],
  "translated_claim_en": "English translation if claim was in another language",
  "key_findings": ["Finding 1", "Finding 2"],
  "source_stances": [
    {{
      "source_index": 1,
      "url": "exact URL from sources",
      "stance": "SUPPORTS" | "CONTRADICTS" | "NEUTRAL",
      "relevant_quote": "Direct quote from source that supports or contradicts"
    }}
  ]
}}
"""

        # Call Gemini with model fallback
        llm_response = None
        for model_name in self.candidate_models:
            try:
                resp = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if resp and resp.text:
                    llm_response = resp.text.strip()
                    break
            except Exception as e:
                logger.warning("Gemini model %s failed: %s", model_name, e)
                continue

        # Parse JSON output
        parsed_data = self._parse_gemini_json(llm_response)

        # Map verdict string to ClaimVerdict
        raw_v = parsed_data.get("verdict", "UNVERIFIED").upper()
        if "SUPPORT" in raw_v:
            claim_verdict = ClaimVerdict.SUPPORTED
        elif "CONTRADICT" in raw_v:
            claim_verdict = ClaimVerdict.CONTRADICTED
        else:
            claim_verdict = ClaimVerdict.UNVERIFIED

        # Build flexible multi-key lookup for source stances
        raw_stances = parsed_data.get("source_stances", [])
        if not isinstance(raw_stances, list):
            raw_stances = []

        def _clean_url_key(u: str) -> str:
            if not u:
                return ""
            return u.split("?")[0].split("#")[0].rstrip("/").lower()

        index_stance_map = {}
        exact_url_stance_map = {}
        clean_url_stance_map = {}

        for s in raw_stances:
            if not isinstance(s, dict):
                continue
            s_idx = s.get("source_index")
            if s_idx is not None:
                try:
                    index_stance_map[int(s_idx)] = s
                except (ValueError, TypeError):
                    pass
            s_url = s.get("url") or ""
            if s_url:
                exact_url_stance_map[s_url] = s
                clean_url_stance_map[_clean_url_key(s_url)] = s

        debunk_keywords = [
            "fake", "debunk", "scam", "hoax", "false", "fraud", "warning",
            "clarifies", "clarification", "busted", "myth", "rumour", "rumor",
            "misleading", "fact check", "fact-check", "not true", "baseless",
            "no such", "rejects", "refutes", "denies", "pib fact check"
        ]

        # Build EvidenceItems list
        evidence_items: List[EvidenceItem] = []
        for idx, doc in enumerate(evidence_docs):
            doc_idx = idx + 1
            doc_url = doc.get("url") or ""
            doc_clean_url = _clean_url_key(doc_url)

            # Hierarchical lookup:
            # 1. By source_index (1..N)
            # 2. By exact URL
            # 3. By clean URL without query parameters
            # 4. Positional fallback if Gemini returned items in array order
            stance_info = (
                index_stance_map.get(doc_idx)
                or exact_url_stance_map.get(doc_url)
                or clean_url_stance_map.get(doc_clean_url)
                or (raw_stances[idx] if idx < len(raw_stances) and isinstance(raw_stances[idx], dict) else {})
            )

            raw_stance = (stance_info.get("stance") or "NEUTRAL").upper()
            stance = StanceType.NEUTRAL
            if "SUPPORT" in raw_stance:
                stance = StanceType.SUPPORTS
            elif "CONTRADICT" in raw_stance or "REFUT" in raw_stance:
                stance = StanceType.CONTRADICTS

            # Safety fallback:
            # If claim verdict is CONTRADICTED and stance is still NEUTRAL, check if the source title/snippet is a debunking article
            doc_text = f"{doc.get('title', '')} {doc.get('snippet', '')}".lower()
            if stance == StanceType.NEUTRAL:
                if claim_verdict == ClaimVerdict.CONTRADICTED:
                    if any(kw in doc_text for kw in debunk_keywords):
                        stance = StanceType.CONTRADICTS
                        logger.info("Auto-assigned stance CONTRADICTS to source [%d] '%s' matching debunk keywords", doc_idx, doc.get("title"))
                elif claim_verdict == ClaimVerdict.SUPPORTED:
                    if not any(kw in doc_text for kw in debunk_keywords) and len(doc_text) > 20:
                        stance = StanceType.SUPPORTS
                        logger.info("Auto-assigned stance SUPPORTS to source [%d] '%s' for supported claim", doc_idx, doc.get("title"))

            quote = stance_info.get("relevant_quote") or doc["snippet"]

            evidence_items.append(
                EvidenceItem(
                    id=f"{claim_id}_ev_{idx+1}",
                    claim_id=claim_id,
                    source_type=EvidenceSourceType.LIVE_NEWS_SEARCH,
                    publisher=doc["publisher"],
                    domain=doc["domain"],
                    url=doc["url"],
                    title=doc["title"],
                    snippet=quote[:300] if quote else doc["snippet"][:300],
                    content=doc["content"][:800] if doc["content"] else None,
                    credibility_score=0.90 if stance != StanceType.NEUTRAL else 0.70,
                    relevance_score=0.95 if stance != StanceType.NEUTRAL else 0.60,
                    stance=stance
                )
            )

        # Calculate counts
        sup_count = sum(1 for e in evidence_items if e.stance == StanceType.SUPPORTS)
        con_count = sum(1 for e in evidence_items if e.stance == StanceType.CONTRADICTS)
        neu_count = sum(1 for e in evidence_items if e.stance == StanceType.NEUTRAL)

        strength = EvidenceStrength.STRONG if (sup_count >= 2 or con_count >= 1) else (
            EvidenceStrength.MODERATE if (sup_count == 1 or con_count == 1) else (
                EvidenceStrength.LIMITED if len(evidence_items) > 0 else EvidenceStrength.NONE
            )
        )

        uncertainty = UncertaintyLevel.LOW if (claim_verdict != ClaimVerdict.UNVERIFIED and strength in [EvidenceStrength.STRONG, EvidenceStrength.MODERATE]) else (
            UncertaintyLevel.MEDIUM if len(evidence_items) > 0 else UncertaintyLevel.HIGH
        )

        native_verdict_fallback = (
            "पुष्ट (SUPPORTED)" if claim_verdict == ClaimVerdict.SUPPORTED else (
                "असत्य / फर्जी (CONTRADICTED)" if claim_verdict == ClaimVerdict.CONTRADICTED else "अपुष्ट (UNVERIFIED)"
            )
        )

        vernacular_info = VernacularAuditInfo(
            detected_language=lang_code,
            language_name=lang_name,
            original_claim=claim_text,
            translated_claim_en=parsed_data.get("translated_claim_en"),
            native_verdict_label=parsed_data.get("native_verdict_label") or native_verdict_fallback,
            native_reasoning=parsed_data.get("native_explanation") or parsed_data.get("explanation"),
            english_reasoning=parsed_data.get("explanation"),
            native_key_findings=parsed_data.get("native_key_findings") or parsed_data.get("key_findings", []),
            vernacular_sources_searched=list({doc["publisher"] for doc in evidence_docs if doc.get("publisher")})
        )

        return {
            "claim_id": claim_id,
            "text": claim_text,
            "verdict": claim_verdict,
            "reasoning": parsed_data.get("explanation", "Verification completed with live search and Gemini AI reasoning."),
            "evidence_strength": strength,
            "uncertainty_level": uncertainty,
            "has_conflicting_evidence": (sup_count > 0 and con_count > 0),
            "supporting_evidence_count": sup_count,
            "contradicting_evidence_count": con_count,
            "neutral_evidence_count": neu_count,
            "keywords": [w for w in claim_text.split() if len(w) > 4][:5],
            "evidence": evidence_items,
            "key_findings": parsed_data.get("key_findings", []),
            "confidence": parsed_data.get("confidence", 0.90),
            "vernacular_info": vernacular_info
        }

    def _parse_gemini_json(self, text: Optional[str]) -> Dict[str, Any]:
        """Extract and clean JSON from Gemini text response."""
        if not text:
            return {"verdict": "UNVERIFIED", "explanation": "No response received from Gemini reasoning model."}
        try:
            # Remove markdown code blocks if present
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.warning("JSON parse error from Gemini response: %s", e)
            # Regex extraction for verdict
            verdict = "UNVERIFIED"
            if "SUPPORTED" in text.upper():
                verdict = "SUPPORTED"
            elif "CONTRADICTED" in text.upper():
                verdict = "CONTRADICTED"
            return {
                "verdict": verdict,
                "confidence": 0.85,
                "explanation": text[:300],
                "key_findings": [],
                "source_stances": []
            }

    def _fallback_response(self, claim_text: str, claim_id: str, docs: List[Dict[str, Any]], lang_code: str = "en", lang_name: str = "English") -> Dict[str, Any]:
        """Offline fallback response if Gemini is unreachable."""
        v_info = VernacularAuditInfo(
            detected_language=lang_code,
            language_name=lang_name,
            original_claim=claim_text,
            translated_claim_en=None,
            native_verdict_label="अपुष्ट (UNVERIFIED)" if lang_code != "en" else "UNVERIFIED",
            native_reasoning="Gemini AI API key is not configured or offline. Real-time verification requires GEMINI_API_KEY.",
            english_reasoning="Gemini AI API key is not configured or offline. Real-time verification requires GEMINI_API_KEY.",
            native_key_findings=[],
            vernacular_sources_searched=[doc["publisher"] for doc in docs if doc.get("publisher")]
        )
        return {
            "claim_id": claim_id,
            "text": claim_text,
            "verdict": ClaimVerdict.UNVERIFIED,
            "reasoning": "Gemini API key is not configured or offline. Real-time verification requires GEMINI_API_KEY.",
            "evidence_strength": EvidenceStrength.NONE,
            "uncertainty_level": UncertaintyLevel.HIGH,
            "has_conflicting_evidence": False,
            "supporting_evidence_count": 0,
            "contradicting_evidence_count": 0,
            "neutral_evidence_count": len(docs),
            "keywords": [w for w in claim_text.split() if len(w) > 4][:5],
            "evidence": [],
            "key_findings": [],
            "confidence": 0.50,
            "vernacular_info": v_info
        }

    def verify_request(self, request: VerificationRequest) -> VerificationResponse:
        """Process full verification request (headline + text body) and return VerificationResponse with multilingual support."""
        title = (request.title or "").strip()
        text = (request.text or "").strip()
        full_text = f"{title}. {text}".strip() if title and text else (title or text)
        req_lang = request.language or "auto"
        seed_url = (request.source_url or "").strip()

        # Prioritize the most substantive factual claim:
        # If title is provided, it represents the primary breaking news event/headline claim!
        claims_to_verify = []
        if title and len(title) >= 10:
            claims_to_verify.append(title)
            if text and len(text) >= 15 and text != title:
                # Add secondary claim from body if available
                sentences = [s.strip() for s in re.split(r'[.!?\n]+', text) if len(s.strip()) >= 15 and s.strip() != title]
                if sentences:
                    claims_to_verify.append(sentences[0])
        elif text and len(text) >= 15:
            sentences = [s.strip() for s in re.split(r'[.!?\n]+', text) if len(s.strip()) >= 15]
            if sentences:
                claims_to_verify.append(sentences[0])
            else:
                claims_to_verify.append(text[:250])
        else:
            claims_to_verify = [full_text[:200]]

        claim_details: List[ClaimVerificationDetail] = []
        all_key_findings = []

        for idx, claim_str in enumerate(claims_to_verify[:request.max_claims or 2]):
            cid = f"claim_{idx+1}"
            res = self.verify_claim(claim_str, cid, language_hint=req_lang, seed_url=seed_url if idx == 0 else None)
            
            # Evidence summary
            ev_items = res["evidence"]
            summary = ClaimEvidenceSummary(
                claim_id=cid,
                claim_text=claim_str,
                total_evidence_count=len(ev_items),
                live_news_count=len(ev_items),
                supporting_evidence_count=res["supporting_evidence_count"],
                contradicting_evidence_count=res["contradicting_evidence_count"],
                neutral_evidence_count=res["neutral_evidence_count"],
                unique_source_domains=list(set(e.domain for e in ev_items)),
                unique_domain_count=len(set(e.domain for e in ev_items)),
                has_conflicting_evidence=res["has_conflicting_evidence"],
                live_news_evidence=ev_items,
                all_evidence=ev_items,
                semantic_model="Google Gemini 2.0 / 1.5 Flash Reasoning",
                semantic_evidence_count=len(ev_items)
            )

            detail = ClaimVerificationDetail(
                claim_id=cid,
                text=claim_str,
                verdict=res["verdict"],
                reasoning=res["reasoning"],
                evidence_strength=res["evidence_strength"],
                uncertainty_level=res["uncertainty_level"],
                has_conflicting_evidence=res["has_conflicting_evidence"],
                supporting_evidence_count=res["supporting_evidence_count"],
                contradicting_evidence_count=res["contradicting_evidence_count"],
                neutral_evidence_count=res["neutral_evidence_count"],
                keywords=res["keywords"],
                evidence_summary=summary,
                evidence=ev_items,
                semantic_relation=res["verdict"].value,
                semantic_model="Google Gemini Flash RAG",
                semantic_evidence_count=len(ev_items),
                vernacular_info=res.get("vernacular_info")
            )
            claim_details.append(detail)
            if res.get("key_findings"):
                all_key_findings.extend(res["key_findings"])

        # Determine overall assessment
        verdicts = [c.verdict for c in claim_details]
        has_con = any(v == ClaimVerdict.CONTRADICTED for v in verdicts)
        has_sup = any(v == ClaimVerdict.SUPPORTED for v in verdicts)

        total_ev_count = sum(len(c.evidence) for c in claim_details) if claim_details else 0
        is_dev_story = False
        dev_note = None

        if has_con:
            overall = OverallAssessment.CONTRADICTED
            summary_msg = claim_details[0].reasoning
        elif has_sup:
            overall = OverallAssessment.SUPPORTED
            summary_msg = claim_details[0].reasoning
        else:
            overall = OverallAssessment.UNVERIFIED
            summary_msg = claim_details[0].reasoning if claim_details else "Insufficient external evidence found."
            # If multiple sources report on the story or general context, mark as active Developing Story
            if total_ev_count >= 2:
                is_dev_story = True
                dev_note = (
                    "Live coverage detected across mainstream news publications. "
                    "The overarching incident is reported, while specific forensic or micro-details are actively developing."
                )

        first_vinfo = claim_details[0].vernacular_info if claim_details else None
        detected_lang = first_vinfo.detected_language if first_vinfo else "en"
        lang_name = first_vinfo.language_name if first_vinfo else "English"
        vernacular_summary = first_vinfo.native_reasoning if (first_vinfo and first_vinfo.native_reasoning) else None
        vernacular_overall = first_vinfo.native_verdict_label if (first_vinfo and first_vinfo.native_verdict_label) else None
        translations = ["en"]
        if detected_lang != "en":
            translations.append(detected_lang)

        return VerificationResponse(
            overall_assessment=overall,
            assessment_summary=summary_msg,
            has_conflict=(has_con and has_sup),
            claims=claim_details,
            linguistic_signal=None,
            service_status={
                "search_engine": "ok",
                "gemini_api": "ok" if self.client else "missing_key",
                "rag_pipeline": "active"
            },
            disclaimer=(
                "Verification is powered by real-time web news retrieval and Google Gemini AI reasoning. "
                "UNVERIFIED claims indicate an absence of indexed external reporting rather than proven falsehood."
            ),
            detected_language=detected_lang,
            language_name=lang_name,
            vernacular_summary=vernacular_summary,
            vernacular_overall_verdict=vernacular_overall,
            available_translations=translations,
            is_developing_story=is_dev_story,
            developing_story_note=dev_note
        )

    def _decompose_claims(self, title: str, content: str) -> List[str]:
        """Extracts top 3-5 key testable factual assertions from document."""
        if self.client:
            prompt = f"""You are an elite investigative fact-checker.
Read the following article/document and extract 3 to 5 core, testable factual assertions or claims made in it.
Focus on specific verifiable statements, statistics, events, actions, or allegations.

DOCUMENT TITLE: {title}
DOCUMENT TEXT:
{content[:3000]}

OUTPUT FORMAT:
Return strictly a valid JSON array of plain claim strings. Example:
["Claim 1...", "Claim 2...", "Claim 3..."]
"""
            for model_name in self.candidate_models:
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if resp and resp.text:
                        raw = resp.text.strip()
                        m = re.search(r'\[.*\]', raw, re.DOTALL)
                        if m:
                            claims = json.loads(m.group(0))
                            if isinstance(claims, list) and len(claims) > 0:
                                return [str(c).strip() for c in claims if len(str(c).strip()) > 15][:5]
                except Exception:
                    continue

        sentences = [s.strip() for s in re.split(r'[.!?\n]+', content) if len(s.strip()) >= 25]
        return sentences[:4] if sentences else [content[:200]]

    def audit_document(self, content: str, title: Optional[str] = None, filename: Optional[str] = None) -> DocumentAuditResponse:
        """
        Conducts a deep factual authenticity audit on a long document or news story.
        Decomposes into core assertions, cross-verifies concurrently via RAG,
        and computes document authenticity score.
        """
        import datetime
        clean_content = content.strip()
        doc_title = title or (filename.rsplit(".", 1)[0].replace("_", " ").title() if filename else "Untitled Document")
        words = len(clean_content.split())

        # Extract top 3-5 core factual assertions
        claims = self._decompose_claims(doc_title, clean_content[:4000])
        if not claims:
            sentences = [s.strip() for s in re.split(r'[.!?]+', clean_content) if len(s.strip()) > 30]
            claims = sentences[:3] if sentences else [clean_content[:150]]

        claims = claims[:5]
        audited_claims = []
        counts = {"supported": 0, "contradicted": 0, "misleading": 0, "unverified": 0}

        for idx, claim_text in enumerate(claims):
            cid = f"doc_claim_{idx + 1}"
            res = self.verify_claim(claim_text, cid)
            verdict_obj = res["verdict"]
            verdict_str = verdict_obj.value if hasattr(verdict_obj, "value") else str(verdict_obj)

            if verdict_str == "SUPPORTED":
                counts["supported"] += 1
            elif verdict_str == "CONTRADICTED":
                counts["contradicted"] += 1
            elif verdict_str == "MISLEADING":
                counts["misleading"] += 1
            else:
                counts["unverified"] += 1

            ev_list = res.get("evidence", [])
            top_sources = []
            source_links = []
            for ev in ev_list[:4]:
                pub = getattr(ev, "publisher", None) or (ev.get("publisher") if isinstance(ev, dict) else None)
                url = getattr(ev, "url", None) or (ev.get("url") if isinstance(ev, dict) else None)
                dom = getattr(ev, "domain", None) or (ev.get("domain") if isinstance(ev, dict) else None)
                name = pub or dom or "News Outlet"
                if name not in top_sources:
                    top_sources.append(name)
                    final_url = url or (f"https://{dom}" if dom else f"https://www.google.com/search?q={urllib.parse.quote_plus(name + ' ' + claim_text)}")
                    source_links.append({"title": name, "url": final_url})

            audited_claims.append(DocumentClaimAudit(
                claim_id=cid,
                text=claim_text,
                verdict=verdict_str,
                confidence=0.92 if verdict_str in ["SUPPORTED", "CONTRADICTED"] else 0.65,
                reasoning=res.get("reasoning", ""),
                sources_count=len(ev_list),
                top_sources=top_sources,
                source_links=source_links
            ))

        total = len(audited_claims) or 1
        if counts["contradicted"] > 0:
            penalty = (counts["contradicted"] / total) * 55 + (counts["misleading"] / total) * 25
            base = (counts["supported"] / total) * 100
            score = max(5.0, round(base - penalty, 1))
        else:
            score = round(((counts["supported"] * 100) + (counts["unverified"] * 60) + (counts["misleading"] * 30)) / total, 1)

        score = min(100.0, max(0.0, score))

        if score >= 75.0 and counts["contradicted"] == 0:
            overall_status = "HIGH_CREDIBILITY"
            exec_summary = f"The document demonstrates strong factual veracity. {counts['supported']} of {total} key assertions were confirmed by external reporting."
        elif counts["contradicted"] > 0 or score < 45.0:
            overall_status = "HIGH_RISK"
            exec_summary = f"Audit detected factual errors or false assertions. {counts['contradicted']} statement(s) were contradicted by verified reporting."
        else:
            overall_status = "MIXED_CREDIBILITY"
            exec_summary = f"The document mixes verified facts with uncorroborated assertions. Readers should verify key claims independently."

        return DocumentAuditResponse(
            filename=filename,
            document_title=doc_title,
            word_count=words,
            authenticity_score=score,
            overall_status=overall_status,
            executive_assessment=exec_summary,
            total_claims_detected=total,
            claims_breakdown=counts,
            audited_claims=audited_claims,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z"
        )


# Global singleton

_rag_verifier: Optional[GeminiRAGVerifier] = None

def get_rag_verifier() -> GeminiRAGVerifier:
    global _rag_verifier
    if _rag_verifier is None:
        _rag_verifier = GeminiRAGVerifier()
    return _rag_verifier
