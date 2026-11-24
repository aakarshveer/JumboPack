"""
JumboPack - Reporter
Generates a Gemini-powered weekly report on:
- Content ideas generated vs approved vs uploaded
- YouTube video performance (views, subs gained)
- Next week's content suggestions
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed yet; run setup.py first

try:
    import google.generativeai as genai
except ImportError:
    print("Run: pip install google-generativeai")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QUEUE_DIR = Path("queue")
REPORTS_DIR = Path("reports")


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def get_youtube_stats(video_ids: list[str]) -> dict:
    """Fetch YouTube video stats if credentials available."""
    try:
        from googleapiclient.discovery import build
        import pickle

        TOKEN_PATH = Path("credentials/youtube_token.pickle")
        if not TOKEN_PATH.exists() or not video_ids:
            return {}

        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

        youtube = build("youtube", "v3", credentials=creds)
        stats_response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids)
        ).execute()

        stats = {}
        for item in stats_response.get("items", []):
            vid_id = item["id"]
            s = item.get("statistics", {})
            stats[vid_id] = {
                "title": item["snippet"]["title"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            }
        return stats
    except Exception:
        return {}


def build_report_data() -> dict:
    """Collect all queue data for the report."""
    pending_ideas = load_json(QUEUE_DIR / "pending_ideas.json")
    approved_ideas = load_json(QUEUE_DIR / "approved_ideas.json")
    pending_videos = load_json(QUEUE_DIR / "pending_videos.json")
    approved_videos = load_json(QUEUE_DIR / "approved_videos.json")
    uploaded_log = load_json(QUEUE_DIR / "uploaded_log.json")

    # Get YouTube video IDs from upload log
    yt_ids = []
    for entry in uploaded_log:
        url = entry.get("youtube_url", "")
        if "v=" in url:
            yt_ids.append(url.split("v=")[1].split("&")[0])

    yt_stats = get_youtube_stats(yt_ids)

    # Pillar breakdown
    pillar_counts = {}
    for idea in approved_ideas:
        p = idea.get("pillar", "unknown")
        pillar_counts[p] = pillar_counts.get(p, 0) + 1

    return {
        "week": datetime.now().strftime("%Y-W%W"),
        "summary": {
            "ideas_pending": len([i for i in pending_ideas if i.get("status") == "pending"]),
            "ideas_approved": len(approved_ideas),
            "videos_pending": len([v for v in pending_videos if v.get("status") == "pending"]),
            "videos_approved": len(approved_videos),
            "videos_uploaded": len(uploaded_log),
        },
        "pillar_breakdown": pillar_counts,
        "uploaded_videos": [
            {
                "title": e["title"],
                "url": e.get("youtube_url", ""),
                "ig_clips": len(e.get("instagram_clips", [])),
                "uploaded_at": e.get("uploaded_at", ""),
                **yt_stats.get(
                    e.get("youtube_url", "").split("v=")[-1] if "v=" in e.get("youtube_url", "") else "",
                    {}
                )
            }
            for e in uploaded_log
        ],
    }


def generate_gemini_report(data: dict) -> str:
    """Use Gemini to write a human-readable weekly report."""
    if not GEMINI_API_KEY:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""You are the content strategist for Aakar, a young YouTube creator from Bihar, India.

Here is this week's JumboPack data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a concise weekly report (in English) with these sections:
1. **This Week's Highlights** - what was accomplished
2. **Pipeline Health** - ideas → scripts → videos → uploads funnel
3. **Performance Insights** - what the YouTube stats tell us (if any)
4. **Content Gaps** - which pillars need more content
5. **Next Week's Priorities** - top 3 specific action items
6. **Suggested Ideas for Next Week** - 2 specific video ideas with titles

Keep it actionable, specific, and encouraging. Max 400 words."""

    response = model.generate_content(prompt)
    return response.text


def save_report(report_text: str, data: dict):
    REPORTS_DIR.mkdir(exist_ok=True)
    week = datetime.now().strftime("%Y-W%W")
    report_path = REPORTS_DIR / f"report_{week}.md"

    content = f"""# JumboPack Weekly Report — {week}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{report_text}

---

## Raw Data
```json
{json.dumps(data['summary'], indent=2)}
```
"""
    report_path.write_text(content, encoding="utf-8")
    return str(report_path)


def main():
    print("\n=== JumboPack Weekly Reporter ===\n")
    print("Collecting data...")
    data = build_report_data()

    print("Generating Gemini report...")
    report_text = generate_gemini_report(data)

    report_path = save_report(report_text, data)
    print(f"\n✓ Report saved: {report_path}")
    print("\n" + "="*50)
    print(report_text)
    print("="*50)


if __name__ == "__main__":
    main()
