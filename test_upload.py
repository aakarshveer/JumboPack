"""
JumboPack - Test Upload Script (Test 8 / YouTube Dry-Run)

This script:
  1. Uses FFmpeg to generate a 5-second black test video (requires FFmpeg in PATH)
  2. Creates a clearly labelled [TEST] entry in queue/approved_videos.json
  3. Calls the uploader — which opens your browser for OAuth then uploads PRIVATE

After a successful test run:
  - Visit YouTube Studio, confirm the video is PRIVATE
  - Delete it manually from YouTube Studio
  - Delete test_clip.mp4 from this folder
  - Remove the [TEST] entry from queue/uploaded_log.json
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TEST_VIDEO_PATH = Path("test_clip.mp4")
APPROVED_VIDEOS = Path("queue/approved_videos.json")

TEST_ENTRY = {
    "id": "vid_TEST_dryrun",
    "idea_id": "TEST_dryrun",
    "title": "[TEST - DELETE] JumboPack Upload Test",
    "pillar": "daily_interesting",
    "script_path": "",
    "description": "This is a private test upload from JumboPack setup. Safe to delete.",
    "tags": ["test", "private"],
    "file_path": str(TEST_VIDEO_PATH),
    "platform": "youtube",
    "status": "approved",
    "created_at": datetime.now().isoformat(),
}


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def generate_test_video():
    """Generate a 5-second, 320x240 black video with silent audio."""
    if TEST_VIDEO_PATH.exists():
        print(f"[OK] Test video already exists: {TEST_VIDEO_PATH}")
        return True

    print("Generating 5-second test video with FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=black:size=320x240:rate=24",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", "5",
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
        "-c:a", "aac", "-b:a", "64k",
        "-shortest",
        str(TEST_VIDEO_PATH)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        size_kb = TEST_VIDEO_PATH.stat().st_size // 1024
        print(f"[OK] test_clip.mp4 created ({size_kb} KB)")
        return True
    else:
        print(f"[FAIL] FFmpeg error: {result.stderr[-300:]}")
        return False


def setup_test_queue_entry():
    """Add the [TEST] entry to approved_videos.json."""
    Path("queue").mkdir(exist_ok=True)
    existing = []
    if APPROVED_VIDEOS.exists():
        existing = json.loads(APPROVED_VIDEOS.read_text(encoding="utf-8"))

    # Remove any previous test entry to avoid duplicates
    existing = [v for v in existing if v.get("id") != "vid_TEST_dryrun"]
    existing.append(TEST_ENTRY)

    APPROVED_VIDEOS.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Test entry added to queue/approved_videos.json")
    print(f"     Title: {TEST_ENTRY['title']}")
    print(f"     Privacy: PRIVATE (hardcoded in uploader.py)")


def run_uploader():
    """Launch the uploader — this will open the browser for OAuth."""
    print("\n" + "="*55)
    print("  STARTING YOUTUBE UPLOAD")
    print("  Your browser will open for OAuth consent.")
    print("  Sign in with the Google account you added as")
    print("  a Test User in the Cloud Console.")
    print("="*55 + "\n")
    result = subprocess.run(["python", "uploader.py", "upload"])
    return result.returncode == 0


def cleanup_instructions():
    print("\n" + "="*55)
    print("  AFTER SUCCESSFUL UPLOAD — CLEANUP STEPS:")
    print("  1. Open YouTube Studio")
    print("     https://studio.youtube.com")
    print("  2. Find '[TEST - DELETE] JumboPack Upload Test'")
    print("  3. Delete it (3-dot menu -> Delete)")
    print("  4. Delete test_clip.mp4 from this folder")
    print("="*55)


def main():
    print("\n=== JumboPack Test Upload (Test 8 / Dry-Run) ===\n")

    # Step 1: Check FFmpeg
    if not check_ffmpeg():
        print("[FAIL] FFmpeg is not installed or not in PATH.")
        print()
        print("Install FFmpeg with winget (run this in an ADMIN PowerShell):")
        print("  winget install --id Gyan.FFmpeg -e")
        print()
        print("After install, CLOSE this terminal and open a new one, then re-run:")
        print("  python test_upload.py")
        sys.exit(1)
    print("[OK] FFmpeg found in PATH")

    # Step 2: Generate test video
    if not generate_test_video():
        sys.exit(1)

    # Step 3: Set up queue entry
    setup_test_queue_entry()

    # Step 4: Run uploader
    run_uploader()

    # Step 5: Remind about cleanup
    cleanup_instructions()


if __name__ == "__main__":
    main()
