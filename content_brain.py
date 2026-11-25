"""
JumboPack - Content Brain
Uses Gemini to suggest video ideas based on your content pillars.
Saves ideas to queue/pending_ideas.json for approval.
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
    pass  # python-dotenv not installed yet; run setup.py first

try:
    from google import genai
except ImportError:
    print("Run: pip install google-genai")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QUEUE_DIR = Path("queue")
PENDING_FILE = QUEUE_DIR / "pending_ideas.json"

CONTENT_PILLARS = [
    "travel_vlog",        # Ghoomne ke videos
    "ai_tech",            # AI/tech related videos
    "project_build",      # Project banana dikhao
    "daily_interesting",  # Interesting cheezein jo karta hoon
    "bihar_documentary",  # Bihar ke baare mein documentaries
]

PILLAR_PROMPTS = {
    "travel_vlog": "Travel vlog video ideas for a young Indian creator exploring places in Bihar and nearby states. Include specific locations, story angles, and what makes them compelling.",
    "ai_tech": "AI/tech video ideas that explain AI concepts simply for Indian audience. Include tutorials, demos, and opinion pieces about AI tools and trends.",
    "project_build": "Project build video ideas - coding projects, side hustles, apps, tools that a young developer can build and document on camera.",
    "daily_interesting": "Day-in-life and interesting activity video ideas - productivity hacks, experiments, challenges, reactions to interesting things.",
    "bihar_documentary": "Documentary video ideas about Bihar - history, culture, food, unsung heroes, hidden places, development stories, mythology.",
}


def load_pending():
    if PENDING_FILE.exists():
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    return []


def save_pending(ideas):
    QUEUE_DIR.mkdir(exist_ok=True)
    PENDING_FILE.write_text(json.dumps(ideas, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_ideas(pillar: str, count: int = 5) -> list[dict]:
    if not GEMINI_API_KEY:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""You are a YouTube content strategist for a young Indian creator named Aakar.

Channel focus: {PILLAR_PROMPTS[pillar]}

Generate {count} specific, compelling video ideas. For each idea return a JSON object with:
- title: catchy YouTube title (in English, can mix Hindi words naturally)
- hook: first 15 seconds hook to grab attention
- outline: 3-4 bullet points of what the video covers
- thumbnail_concept: simple description of thumbnail idea
- estimated_duration: in minutes
- pillar: "{pillar}"
- tags: list of 5 relevant YouTube tags

Return ONLY a JSON array, no markdown, no explanation."""

    response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = response.text.strip()

    # Clean up if Gemini wraps in markdown
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    ideas = json.loads(text)

    # Add metadata
    for idx, idea in enumerate(ideas):
        idea["id"] = f"{pillar}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}"
        idea["status"] = "pending"
        idea["created_at"] = datetime.now().isoformat()

    return ideas


def generate_trending_ideas() -> list[dict]:
    """Fetch daily trends and return Gemini-synthesized ideas."""
    from trend_scout import get_trending_ideas
    return get_trending_ideas()


def main():
    print("\n=== JumboPack Content Brain ===\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--trending":
        print("Mode: Daily Trending Topics\n")
        try:
            ideas = generate_trending_ideas()
        except Exception as e:
            print(f"[FAIL] Trend fetch failed: {e}")
            sys.exit(1)

        all_ideas = load_pending()
        # Deduplicate by ID
        existing_ids = {i["id"] for i in all_ideas}
        new_ideas = [i for i in ideas if i["id"] not in existing_ids]
        all_ideas.extend(new_ideas)
        save_pending(all_ideas)
        print(f"\n{len(new_ideas)} trending ideas saved to queue/pending_ideas.json")
        print("Run: python approval_cli.py  to approve ideas")
        return

    if len(sys.argv) > 1:
        pillar = sys.argv[1]
        if pillar not in CONTENT_PILLARS:
            print(f"Valid pillars: {', '.join(CONTENT_PILLARS)}")
            print("Or use: python content_brain.py --trending")
            sys.exit(1)
        pillars_to_run = [pillar]
    else:
        print("Which content pillar?")
        for i, p in enumerate(CONTENT_PILLARS, 1):
            print(f"  {i}. {p}")
        print("  0. All pillars (1 idea each)")

        choice = input("\nEnter number: ").strip()
        if choice == "0":
            pillars_to_run = CONTENT_PILLARS
        else:
            pillars_to_run = [CONTENT_PILLARS[int(choice) - 1]]

    all_ideas = load_pending()
    new_count = 0

    for pillar in pillars_to_run:
        count = 1 if len(pillars_to_run) > 1 else 5
        print(f"\nGenerating {count} ideas for: {pillar}...")
        try:
            ideas = generate_ideas(pillar, count)
            all_ideas.extend(ideas)
            new_count += len(ideas)
            print(f"  Got {len(ideas)} ideas")
        except Exception as e:
            print(f"  ERROR: {e}")

    save_pending(all_ideas)
    print(f"\n{new_count} new ideas saved to queue/pending_ideas.json")
    print("Run: python approval_cli.py  to approve ideas")


if __name__ == "__main__":
    main()
