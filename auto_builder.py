"""
JumboPack - Auto Builder (Phase A)
Builds a complete faceless YouTube video from an approved script:
  1. edge-tts voiceover -> MP3
  2. Scene cards (Pillow) or Pexels stock video as visuals
  3. .srt subtitles
  4. FFmpeg assembly -> 1280x720 or 1920x1080 MP4
  5. 9:16 vertical clip for Shorts/Reels

No recording needed. Runs fully automated.
"""

import asyncio
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config from .env ──────────────────────────────────────────────────────────
TTS_VOICE = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural")  # Indian English neural
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
OUTPUT_RES = os.getenv("AUTO_VIDEO_RES", "1280x720")  # or 1920x1080

QUEUE_DIR = Path("queue")
VIDEOS_DIR = Path("videos")
CLIPS_DIR = Path("clips")
ASSETS_DIR = Path("assets")  # temp build workspace


def _check_dep(name: str) -> bool:
    try:
        subprocess.run([name, "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _require_ffmpeg():
    if not _check_dep("ffmpeg"):
        print("[FAIL] FFmpeg not found. Install: winget install --id Gyan.FFmpeg -e")
        sys.exit(1)


def _require_edgetts():
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        print("[FAIL] edge-tts not installed. Run: pip install edge-tts")
        sys.exit(1)


# ── TTS Voiceover ─────────────────────────────────────────────────────────────

async def _tts_async(text: str, out_mp3: Path, out_srt: Path, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    subs = edge_tts.SubMaker()
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                # v7 uses SentenceBoundary; v6 used WordBoundary
                subs.feed(chunk)
    srt_text = subs.get_srt()
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(srt_text)


def generate_voiceover(narration_text: str, out_dir: Path, idea_id: str) -> tuple[Path, Path]:
    """Returns (mp3_path, srt_path)."""
    _require_edgetts()
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = out_dir / f"{idea_id}_vo.mp3"
    srt_path = out_dir / f"{idea_id}_vo.srt"

    voice = TTS_VOICE
    print(f"  [TTS] Generating voiceover ({voice})...")
    asyncio.run(_tts_async(narration_text, mp3_path, srt_path, voice))

    size_kb = mp3_path.stat().st_size // 1024
    print(f"  [OK] Voiceover: {mp3_path.name} ({size_kb} KB)")
    return mp3_path, srt_path


def get_audio_duration(mp3_path: Path) -> float:
    """Return duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        info = json.loads(result.stdout)
        return float(info["format"].get("duration", 0))
    return 0.0


# ── Scene Card Generator (Pillow fallback) ────────────────────────────────────

def _pillow_scene_card(text: str, out_png: Path, width: int, height: int,
                       bg_color=(15, 15, 25), accent=(90, 130, 255)):
    """Render a dark cinematic text card with Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[FAIL] Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle gradient overlay using horizontal bands
    for y in range(height):
        alpha = int(10 * math.sin(math.pi * y / height))
        draw.line([(0, y), (width, y)], fill=(bg_color[0]+alpha, bg_color[1]+alpha, bg_color[2]+alpha))

    # Try to load a font; fall back to default
    font_size = max(28, width // 25)
    font = ImageFont.load_default()
    try:
        # Windows system fonts
        for candidate in [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
        ]:
            if Path(candidate).exists():
                font = ImageFont.truetype(candidate, font_size)
                break
    except Exception:
        pass

    # Word-wrap text
    words = text.split()
    lines, line = [], []
    max_chars = width // (font_size // 2 + 2)
    for word in words:
        if sum(len(w) + 1 for w in line) + len(word) > max_chars:
            if line:
                lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))

    total_h = len(lines) * (font_size + 12)
    y_start = (height - total_h) // 2

    for i, ln in enumerate(lines):
        # Shadow
        draw.text((width // 2 - width // 4 + 2, y_start + i * (font_size + 12) + 2),
                  ln, font=font, fill=(0, 0, 0))
        # Main text
        draw.text((width // 2 - width // 4, y_start + i * (font_size + 12)),
                  ln, font=font, fill=(240, 240, 255))

    # Accent line at bottom
    draw.rectangle([(0, height - 6), (width, height)], fill=accent)

    img.save(out_png)


def _ken_burns_png_to_video(png_path: Path, out_mp4: Path, duration: float,
                             width: int, height: int):
    """Apply Ken Burns zoom effect to a PNG to create a video segment."""
    # zoom from 1.0 to 1.08 over the duration
    zoompan = (
        f"zoompan=z='min(zoom+0.0004,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={int(duration * 25)}:s={width}x{height}:fps=25"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(png_path),
        "-vf", zoompan,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        str(out_mp4)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: simple static image video without zoompan
        cmd_simple = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(png_path),
            "-t", str(duration),
            "-vf", f"scale={width}:{height}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(out_mp4)
        ]
        subprocess.run(cmd_simple, capture_output=True, check=True)


# ── Pexels Stock Video ────────────────────────────────────────────────────────

def _fetch_pexels_video(query: str, out_path: Path, width: int, height: int) -> bool:
    """Download a free Pexels stock video. Returns True on success."""
    if not PEXELS_API_KEY:
        return False
    try:
        import requests as req
        resp = req.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 3, "orientation": "landscape"},
            timeout=10
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return False
        # Pick smallest file close to target resolution
        files = videos[0].get("video_files", [])
        files.sort(key=lambda f: abs(f.get("width", 0) - width))
        url = files[0]["link"]
        video_resp = req.get(url, timeout=30, stream=True)
        with open(out_path, "wb") as f:
            for chunk in video_resp.iter_content(chunk_size=65536):
                f.write(chunk)
        return out_path.stat().st_size > 10000
    except Exception:
        return False


# ── Script Section -> Visual Segment ─────────────────────────────────────────

def build_visual_segment(section: dict, idx: int, work_dir: Path,
                          width: int, height: int) -> Path:
    """
    Build a silent video segment for one script section.
    Tries Pexels first; falls back to animated Pillow scene card.
    """
    duration = float(section.get("duration_sec", 10))
    b_roll = section.get("b_roll") or section.get("section", f"Scene {idx}")
    seg_path = work_dir / f"seg_{idx:02d}.mp4"

    # Try Pexels stock video
    pexels_tmp = work_dir / f"pexels_{idx:02d}.mp4"
    if _fetch_pexels_video(b_roll[:60], pexels_tmp, width, height):
        # Trim to exact duration + scale
        cmd = [
            "ffmpeg", "-y", "-i", str(pexels_tmp),
            "-t", str(duration),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", str(seg_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return seg_path

    # Fallback: Pillow scene card + Ken Burns
    card_text = section.get("text", b_roll)[:120]  # first 120 chars as overlay text
    png_path = work_dir / f"card_{idx:02d}.png"
    _pillow_scene_card(card_text, png_path, width, height)
    _ken_burns_png_to_video(png_path, seg_path, duration, width, height)
    return seg_path


# ── SRT helpers ───────────────────────────────────────────────────────────────

def _srt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total = int(td.total_seconds())
    ms = int((td.total_seconds() - total) * 1000)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_fallback_srt(script_sections: list, out_srt: Path):
    """Generate a simple SRT from script sections when edge-tts SRT is unavailable."""
    lines = []
    t = 0.0
    for i, sec in enumerate(script_sections, 1):
        dur = float(sec.get("duration_sec", 10))
        text = re.sub(r"\s+", " ", sec.get("text", "")[:80]).strip()
        lines.append(str(i))
        lines.append(f"{_srt_time(t)} --> {_srt_time(t + dur)}")
        lines.append(text)
        lines.append("")
        t += dur
    out_srt.write_text("\n".join(lines), encoding="utf-8")


# ── Main Assembly ─────────────────────────────────────────────────────────────

def build_video(video_entry: dict, script_data: dict) -> str:
    """
    Full pipeline: script_data -> voiceover -> visuals -> assembled MP4.
    Returns path to final video file.
    """
    _require_ffmpeg()

    idea_id = video_entry["id"]
    w_str, h_str = OUTPUT_RES.split("x")
    width, height = int(w_str), int(h_str)

    VIDEOS_DIR.mkdir(exist_ok=True)
    ASSETS_DIR.mkdir(exist_ok=True)
    work_dir = ASSETS_DIR / idea_id
    work_dir.mkdir(exist_ok=True)

    sections = script_data.get("script", [])
    if not sections:
        print("[FAIL] Script has no sections.")
        sys.exit(1)

    # ── 1. Voiceover ──────────────────────────────────────────────────────────
    narration = " ".join(s.get("text", "") for s in sections)
    try:
        vo_mp3, vo_srt = generate_voiceover(narration, work_dir, idea_id)
        audio_dur = get_audio_duration(vo_mp3)
        print(f"  Audio duration: {audio_dur:.1f}s")
    except Exception as e:
        print(f"  [!] TTS failed ({e}). Using silent video.")
        vo_mp3 = None
        audio_dur = sum(float(s.get("duration_sec", 10)) for s in sections)
        vo_srt = work_dir / f"{idea_id}_vo.srt"
        _build_fallback_srt(sections, vo_srt)

    # ── 2. Visual segments ────────────────────────────────────────────────────
    print(f"  Building {len(sections)} visual segments...")
    # Distribute audio duration proportionally across sections
    total_script_dur = sum(float(s.get("duration_sec", 10)) for s in sections) or audio_dur
    seg_paths = []
    for idx, section in enumerate(sections):
        ratio = float(section.get("duration_sec", 10)) / total_script_dur
        seg_dur = max(2.0, ratio * audio_dur) if audio_dur > 0 else float(section.get("duration_sec", 10))
        section_copy = dict(section)
        section_copy["duration_sec"] = seg_dur
        seg_path = build_visual_segment(section_copy, idx, work_dir, width, height)
        seg_paths.append(seg_path)
        print(f"  [OK] Segment {idx+1}/{len(sections)}")

    # ── 3. Concatenate visual segments ────────────────────────────────────────
    concat_list = work_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in seg_paths),
        encoding="utf-8"
    )
    silent_video = work_dir / "silent_full.mp4"
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        str(silent_video)
    ]
    print("  Concatenating segments...")
    subprocess.run(cmd_concat, capture_output=True, check=True)

    # ── 4. Burn subtitles ─────────────────────────────────────────────────────
    # Convert SRT path to FFmpeg-safe format (forward slashes, escaped colons)
    srt_safe = str(vo_srt.resolve()).replace("\\", "/").replace(":", "\\:")
    subtitled_video = work_dir / "with_subs.mp4"
    cmd_subs = [
        "ffmpeg", "-y", "-i", str(silent_video),
        "-vf", f"subtitles='{srt_safe}':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3'",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(subtitled_video)
    ]
    result_subs = subprocess.run(cmd_subs, capture_output=True, text=True)
    if result_subs.returncode != 0:
        # Subtitle burning can fail on Windows path issues; skip gracefully
        print("  [!] Subtitle burn failed — skipping (subtitles file kept alongside video)")
        subtitled_video = silent_video

    # ── 5. Mix audio + video ──────────────────────────────────────────────────
    final_path = VIDEOS_DIR / f"final_{idea_id}.mp4"
    if vo_mp3 and vo_mp3.exists():
        cmd_mux = [
            "ffmpeg", "-y",
            "-i", str(subtitled_video),
            "-i", str(vo_mp3),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(final_path)
        ]
        print("  Muxing audio + video...")
        result_mux = subprocess.run(cmd_mux, capture_output=True, text=True)
        if result_mux.returncode != 0:
            print(f"  [!] Mux error: {result_mux.stderr[-200:]}")
            # Fallback: video only
            import shutil
            shutil.copy(str(subtitled_video), str(final_path))
    else:
        import shutil
        shutil.copy(str(subtitled_video), str(final_path))

    size_mb = final_path.stat().st_size / 1024 / 1024
    print(f"\n  [OK] Final video: {final_path} ({size_mb:.1f} MB)")

    # ── 6. Auto-generate 9:16 Short clip ──────────────────────────────────────
    clip_path = _make_shorts_clip(final_path, idea_id)

    return str(final_path)


def _make_shorts_clip(video_path: Path, idea_id: str, duration: int = 59) -> Path | None:
    """Cut first `duration` seconds and center-crop to 9:16."""
    CLIPS_DIR.mkdir(exist_ok=True)
    clip_path = CLIPS_DIR / f"short_{idea_id[:20]}.mp4"

    # Get actual video duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
        capture_output=True, text=True
    )
    actual_dur = duration
    if result.returncode == 0:
        actual_dur = min(duration, float(json.loads(result.stdout)["format"].get("duration", duration)))

    # Center crop: take middle 9:16 portion of 16:9 source
    # For 1280x720 source: crop to 405x720 (720*(9/16)=405) then scale to 1080x1920
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-t", str(int(actual_dur)),
        "-vf", "crop=in_h*9/16:in_h,scale=1080:1920",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(clip_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK] Shorts clip: {clip_path}")
        return clip_path
    else:
        print(f"  [!] Shorts clip failed: {result.stderr[-100:]}")
        return None


# ── Entry point ───────────────────────────────────────────────────────────────

def build_from_queue_entry(video_id: str):
    """Find a pending video entry and auto-build it."""
    pending_path = QUEUE_DIR / "pending_videos.json"
    if not pending_path.exists():
        print("No pending videos found.")
        return

    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    entry = next((v for v in pending if v["id"] == video_id), None)
    if not entry:
        print(f"Video ID not found: {video_id}")
        print("Available IDs:")
        for v in pending:
            print(f"  {v['id']} — {v['title']}")
        return

    # Load script
    script_path = Path(entry.get("script_path", ""))
    if not script_path.exists():
        print(f"Script file not found: {script_path}")
        return

    # Parse script file back to structured data (best-effort)
    script_text = script_path.read_text(encoding="utf-8")
    # Try to find embedded JSON in script; if not, build a simple structure
    script_data = _parse_script_file(script_text, entry)

    print(f"\n=== Auto-Building: {entry['title']} ===\n")
    final_path = build_video(entry, script_data)

    # Update file_path in queue
    entry["file_path"] = final_path
    entry["auto_built"] = True
    pending_path.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Queue updated. file_path = {final_path}")
    print("Next: python approval_cli.py videos  to review and approve for upload")


def _parse_script_file(script_text: str, entry: dict) -> dict:
    """
    Parse a JumboPack script .txt file into a sections list.
    Falls back to splitting by section headers.
    """
    sections = []
    current = None
    duration_re = re.compile(r"\(~(\d+)s\)")

    for line in script_text.splitlines():
        m = re.match(r"^\[([A-Z_ ]+)\]", line)
        if m:
            if current:
                sections.append(current)
            dur_m = duration_re.search(line)
            current = {
                "section": m.group(1).strip(),
                "duration_sec": int(dur_m.group(1)) if dur_m else 30,
                "text": "",
                "b_roll": "",
            }
        elif current:
            if line.startswith("B-ROLL:"):
                current["b_roll"] = line.replace("B-ROLL:", "").strip()
            elif line.strip() and line != "---":
                current["text"] += line.strip() + " "

    if current:
        sections.append(current)

    if not sections:
        # Last resort: treat entire script as one section
        sections = [{"section": "FULL", "duration_sec": 300, "text": script_text[:2000], "b_roll": entry.get("title", "")}]

    return {
        "title": entry.get("title", ""),
        "description": entry.get("description", ""),
        "tags": entry.get("tags", []),
        "script": sections,
    }


def main():
    print("\n=== JumboPack Auto Builder ===\n")

    if len(sys.argv) < 2:
        # List pending videos
        pending_path = QUEUE_DIR / "pending_videos.json"
        if pending_path.exists():
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
            print("Pending videos (need file_path):")
            for v in pending:
                has_file = "[built]" if v.get("file_path") else "[needs build]"
                print(f"  {has_file} {v['id']} — {v['title']}")
        print("\nUsage:")
        print("  python auto_builder.py <video_id>   - Auto-build a specific video")
        print("  python auto_builder.py all          - Build all pending videos")
        return

    target = sys.argv[1]
    if target == "all":
        pending_path = QUEUE_DIR / "pending_videos.json"
        if not pending_path.exists():
            print("No pending videos.")
            return
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        ids = [v["id"] for v in pending if not v.get("file_path")]
        print(f"Building {len(ids)} videos...\n")
        for vid_id in ids:
            build_from_queue_entry(vid_id)
    else:
        build_from_queue_entry(target)


if __name__ == "__main__":
    main()
