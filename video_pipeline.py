"""
JumboPack - Video Pipeline
Takes approved ideas and helps you:
1. Generate a full video script (Gemini)
2. Create intro/outro segments
3. For uploaded footage: extract highlights, add captions
4. Create Instagram clips from YouTube videos (FFmpeg)
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import google.generativeai as genai
except ImportError:
    print("Run: pip install google-generativeai")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QUEUE_DIR = Path("queue")
VIDEOS_DIR = Path("videos")
CLIPS_DIR = Path("clips")  # Instagram clips go here

APPROVED_IDEAS = QUEUE_DIR / "approved_ideas.json"
PENDING_VIDEOS = QUEUE_DIR / "pending_videos.json"


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_script(idea: dict) -> dict:
    """Generate full video script using Gemini."""
    if not GEMINI_API_KEY:
        print("ERROR: Set GEMINI_API_KEY")
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""You are writing a YouTube script for Aakar, a young Indian creator from Bihar.

Video idea:
Title: {idea['title']}
Hook: {idea.get('hook', '')}
Outline: {json.dumps(idea.get('outline', []))}
Pillar: {idea.get('pillar', '')}
Duration: ~{idea.get('estimated_duration', 10)} minutes

Write a complete, engaging video script. Format as JSON:
{{
  "title": "final title",
  "description": "YouTube description (500 chars, with line breaks, include call to action)",
  "tags": ["tag1", "tag2", ...],
  "script": [
    {{"section": "INTRO", "duration_sec": 30, "text": "script text here", "b_roll": "what to show on screen"}},
    {{"section": "HOOK", "duration_sec": 15, "text": "...", "b_roll": "..."}},
    ...
  ],
  "thumbnail_text": "big bold text for thumbnail",
  "end_screen_cta": "subscribe + watch next video"
}}

Style: conversational Hindi-English mix (Hinglish). Energetic. Personal. Real.
Return ONLY valid JSON."""

    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text)


def save_script(idea: dict, script: dict):
    """Save script as a readable text file."""
    VIDEOS_DIR.mkdir(exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in idea["title"])[:50]
    script_path = VIDEOS_DIR / f"{idea['id']}_script.txt"

    lines = [
        f"=== JUMBPACK SCRIPT ===",
        f"Title: {script['title']}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"--- YOUTUBE DESCRIPTION ---",
        script.get("description", ""),
        f"",
        f"Tags: {', '.join(script.get('tags', []))}",
        f"",
        f"--- THUMBNAIL TEXT ---",
        script.get("thumbnail_text", ""),
        f"",
        f"{'='*60}",
        f"SCRIPT",
        f"{'='*60}",
    ]

    for section in script.get("script", []):
        lines.extend([
            f"",
            f"[{section['section']}] (~{section.get('duration_sec', 0)}s)",
            f"B-ROLL: {section.get('b_roll', '')}",
            f"",
            section.get("text", ""),
            f"---",
        ])

    lines.append(f"\nEND SCREEN: {script.get('end_screen_cta', '')}")

    script_path.write_text("\n".join(lines), encoding="utf-8")
    return str(script_path)


def create_instagram_clips(video_path: str, idea: dict) -> list[str]:
    """
    Cut a YouTube video into 60-90 second Instagram Reels clips using FFmpeg.
    Returns list of clip paths.
    """
    CLIPS_DIR.mkdir(exist_ok=True)
    clip_paths = []

    # Check FFmpeg available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("WARNING: FFmpeg not found. Install from https://ffmpeg.org/download.html")
        return []

    # Get video duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Could not probe video: {video_path}")
        return []

    info = json.loads(result.stdout)
    total_duration = float(info["format"]["duration"])

    safe_id = idea["id"][:20]

    # Strategy: take clips at 10%, 40%, 70% of the video (best moments)
    clip_points = [
        (total_duration * 0.10, 60, "intro_hook"),
        (total_duration * 0.40, 90, "mid_highlight"),
        (total_duration * 0.70, 75, "outro_cta"),
    ]

    for start, duration, label in clip_points:
        # Don't exceed video length
        if start + duration > total_duration:
            continue

        out_path = CLIPS_DIR / f"{safe_id}_{label}.mp4"

        # FFmpeg: cut + scale to 9:16 (1080x1920) for Reels
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(int(start)),
            "-i", video_path,
            "-t", str(duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            str(out_path)
        ]

        print(f"  Creating clip: {label}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            clip_paths.append(str(out_path))
            print(f"  ✓ {out_path}")
        else:
            print(f"  ✗ FFmpeg error: {result.stderr[-200:]}")

    return clip_paths


def process_approved_ideas():
    """Generate scripts for all approved ideas."""
    ideas = load_json(APPROVED_IDEAS)
    if not ideas:
        print("No approved ideas found. Run approval_cli.py first.")
        return

    pending_videos = load_json(PENDING_VIDEOS)
    processed_ids = {v["idea_id"] for v in pending_videos}

    new_scripts = 0
    for idea in ideas:
        if idea["id"] in processed_ids:
            continue

        print(f"\nGenerating script for: {idea['title']}")
        try:
            script = generate_script(idea)
            script_path = save_script(idea, script)

            # Add to pending videos queue
            video_entry = {
                "id": f"vid_{idea['id']}",
                "idea_id": idea["id"],
                "title": script["title"],
                "pillar": idea["pillar"],
                "script_path": script_path,
                "description": script.get("description", ""),
                "tags": script.get("tags", []),
                "file_path": "",  # User fills this after recording
                "platform": "youtube",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }
            pending_videos.append(video_entry)
            new_scripts += 1
            print(f"  ✓ Script saved: {script_path}")

        except Exception as e:
            print(f"  ERROR: {e}")

    save_json(PENDING_VIDEOS, pending_videos)
    print(f"\n{new_scripts} scripts generated.")
    print("Next: Record your videos using the scripts, then add file paths.")
    print("Then run: python approval_cli.py videos")


def add_video_file(video_id: str, file_path: str):
    """After recording, link the actual video file to its queue entry."""
    pending = load_json(PENDING_VIDEOS)
    for v in pending:
        if v["id"] == video_id:
            v["file_path"] = file_path
            v["status"] = "pending"
            print(f"✓ Linked {file_path} to {v['title']}")
            save_json(PENDING_VIDEOS, pending)
            return
    print(f"Video ID not found: {video_id}")


def clip_approved_video(video_path: str, idea_title: str = "clip"):
    """Create Instagram clips from a video file."""
    fake_idea = {"id": f"manual_{datetime.now().strftime('%Y%m%d_%H%M')}", "title": idea_title}
    clips = create_instagram_clips(video_path, fake_idea)
    if clips:
        print(f"\n{len(clips)} Instagram clips created in /clips/")
    return clips


def main():
    print("\n=== JumboPack Video Pipeline ===\n")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "scripts":
            process_approved_ideas()
        elif cmd == "clip" and len(sys.argv) > 2:
            clip_approved_video(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "clip")
        elif cmd == "link" and len(sys.argv) > 3:
            add_video_file(sys.argv[2], sys.argv[3])
        return

    print("Commands:")
    print("  python video_pipeline.py scripts         - Generate scripts for approved ideas")
    print("  python video_pipeline.py clip <file.mp4> - Create Instagram clips from video")
    print("  python video_pipeline.py link <id> <file> - Link recorded video to queue entry")
    print()

    choice = input("Generate scripts for approved ideas now? [Y/n]: ").strip().lower()
    if choice != "n":
        process_approved_ideas()


if __name__ == "__main__":
    main()
