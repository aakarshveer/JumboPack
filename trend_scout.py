"""
JumboPack - Trend Scout
Fetches daily trending topics from free sources and uses Gemini to map them
to Aakar's content pillars. Result is used by content_brain.py.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
except ImportError:
    print("Run: pip install google-genai")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Free RSS/JSON trend feeds — no API key needed
TREND_FEEDS = [
    # Google Trends RSS (India)
    ("google_trends_india", "https://trends.google.com/trending/rss?geo=IN"),
    # Times of India technology
    ("toi_tech", "https://timesofindia.indiatimes.com/rssfeeds/5880659.cms"),
    # NDTV India news
    ("ndtv_india", "https://feeds.feedburner.com/ndtvnews-india-news"),
]

CONTENT_PILLARS = [
    "travel_vlog",
    "ai_tech",
    "project_build",
    "daily_interesting",
    "bihar_documentary",
]


def _fetch_feed_titles(url: str, limit: int = 10) -> list[str]:
    """Parse RSS feed and return item titles. Returns [] on any error."""
    if requests is None:
        return []
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "JumboPack/1.0"})
        resp.raise_for_status()
        # Simple title extraction without feedparser dependency
        import re
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", resp.text)
        if not titles:
            titles = re.findall(r"<title>(.+?)</title>", resp.text)
        # Skip channel-level title (first item is usually the feed name)
        return [t.strip() for t in titles[1:limit+1] if t.strip()]
    except Exception:
        return []


def fetch_trending_topics(max_per_feed: int = 8) -> dict:
    """
    Fetch trending headlines from free RSS feeds.
    Returns {"source_name": ["headline1", ...], ...}
    Falls back to empty dict gracefully if network is unavailable.
    """
    results = {}
    for name, url in TREND_FEEDS:
        titles = _fetch_feed_titles(url, max_per_feed)
        if titles:
            results[name] = titles
    return results


def _fallback_topics() -> dict:
    """Return generic trending topic buckets when feeds are unavailable."""
    return {
        "fallback": [
            "AI tools replacing jobs in India 2026",
            "Bihar startup ecosystem growing rapidly",
            "Spatial computing Apple Vision Pro India launch",
            "India's space program ISRO latest mission",
            "GenZ career trends India 2026",
            "Viral productivity hack goes mainstream",
            "Ancient Indian technology rediscovered",
        ]
    }


def synthesize_with_gemini(raw_topics: dict) -> list[dict]:
    """
    Ask Gemini to map raw headlines to content pillars and generate
    trend-aware idea seeds.
    """
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    all_headlines = []
    for source, titles in raw_topics.items():
        for t in titles:
            all_headlines.append(f"[{source}] {t}")

    headlines_text = "\n".join(all_headlines[:40])  # Cap to avoid huge prompt

    prompt = f"""You are a content strategist for Aakar, a young Indian creator from Bihar (age ~22).
His content pillars: travel_vlog, ai_tech, project_build, daily_interesting, bihar_documentary.

Today's trending headlines (India-focused):
{headlines_text}

For each pillar, identify 1-2 trending angles that Aakar could make a video about.
Return a JSON array where each object has:
- pillar: one of the 5 pillar names above
- title: specific, catchy YouTube title tied to the trend
- trend_context: 1-sentence explanation of why this is trending NOW
- source: source feed name from above (or "synthesized")
- hook: compelling first 15 seconds
- outline: list of 3-4 bullet points
- tags: list of 5 YouTube tags

Return ONLY valid JSON array, no markdown, no extra text."""

    response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    ideas = json.loads(text)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for idx, idea in enumerate(ideas):
        idea["id"] = f"{idea.get('pillar', 'general')}_{ts}_{idx}"
        idea["status"] = "pending"
        idea["created_at"] = datetime.now().isoformat()
        idea["estimated_duration"] = idea.get("estimated_duration", 8)
        idea["thumbnail_concept"] = idea.get("thumbnail_concept", f"Bold text: {idea.get('title','')[:30]}")

    return ideas


def get_trending_ideas() -> list[dict]:
    """Main entry: fetch trends + synthesize ideas. Always returns a list."""
    print("  Fetching trending topics from free RSS feeds...")
    raw = fetch_trending_topics()

    if not raw:
        print("  [!] No feeds reachable — using fallback topics")
        raw = _fallback_topics()
    else:
        feeds_hit = list(raw.keys())
        total = sum(len(v) for v in raw.values())
        print(f"  [OK] Got {total} headlines from: {', '.join(feeds_hit)}")

    print("  Asking Gemini to map trends to your pillars...")
    return synthesize_with_gemini(raw)


def main():
    print("\n=== JumboPack Trend Scout ===\n")
    ideas = get_trending_ideas()
    print(f"\n{len(ideas)} trend-based ideas generated:\n")
    for idea in ideas:
        print(f"  [{idea['pillar']}] {idea['title']}")
        print(f"    Trend: {idea.get('trend_context', '')}")
        print()

    out = Path("queue") / "trending_preview.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(ideas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved preview to {out}")
    print("Run content_brain.py --trending to merge into pending_ideas.json")


if __name__ == "__main__":
    main()
