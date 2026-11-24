"""
JumboPack - Uploader
Uploads approved videos to YouTube and clips to Instagram.

YouTube: Uses YouTube Data API v3 (free, 10,000 units/day)
Instagram: Uses Instagram Graph API (free, requires Meta Business account)

Setup:
  YouTube  -> Get credentials from Google Cloud Console
  Instagram -> Get token from Meta for Developers
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

QUEUE_DIR = Path("queue")
APPROVED_VIDEOS = QUEUE_DIR / "approved_videos.json"
UPLOADED_LOG = QUEUE_DIR / "uploaded_log.json"
CLIPS_DIR = Path("clips")

YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "credentials/youtube_client_secret.json")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────
# YOUTUBE UPLOAD
# ─────────────────────────────────────────────

def upload_to_youtube(video: dict) -> str | None:
    """Upload a video to YouTube. Returns video URL or None on failure."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        import pickle
    except ImportError:
        print("Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return None

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    TOKEN_PATH = Path("credentials/youtube_token.pickle")

    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(exist_ok=True)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)

    file_path = video.get("file_path", "")
    if not file_path or not Path(file_path).exists():
        print(f"  ERROR: Video file not found: {file_path}")
        return None

    # Map pillar to category
    pillar_category = {
        "travel_vlog": "19",        # Travel & Events
        "ai_tech": "28",            # Science & Technology
        "project_build": "28",
        "daily_interesting": "22",  # People & Blogs
        "bihar_documentary": "19",
    }
    category_id = pillar_category.get(video.get("pillar", ""), "22")

    body = {
        "snippet": {
            "title": video["title"],
            "description": video.get("description", ""),
            "tags": video.get("tags", []),
            "categoryId": category_id,
            "defaultLanguage": "hi",
        },
        "status": {
            "privacyStatus": "private",  # Upload as private first, then you review
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"  Uploading to YouTube: {video['title']}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  ✓ Uploaded (private): {url}")
    return url


# ─────────────────────────────────────────────
# INSTAGRAM UPLOAD
# ─────────────────────────────────────────────

def upload_reel_to_instagram(clip_path: str, caption: str) -> bool:
    """Upload a Reel to Instagram using Graph API."""
    try:
        import requests
    except ImportError:
        print("Run: pip install requests")
        return False

    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("  ERROR: Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID env vars")
        print("  Guide: https://developers.facebook.com/docs/instagram-api/reference/ig-user/media")
        return False

    # Step 1: Create container
    container_url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media"
    container_data = {
        "media_type": "REELS",
        "video_url": clip_path,  # Must be a public URL - see note below
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    # NOTE: Instagram requires a public URL for video uploads.
    # For now this is a placeholder - in production you'd need to host the clip
    # temporarily (e.g., upload to your server or use a presigned S3 URL).
    print("  NOTE: Instagram upload requires public video URL.")
    print("  Upload clip to your server/cloud storage first, then use that URL.")
    print(f"  Clip ready at: {clip_path}")
    return False


# ─────────────────────────────────────────────
# MAIN UPLOAD FLOW
# ─────────────────────────────────────────────

def upload_all_approved():
    approved = load_json(APPROVED_VIDEOS)
    if not approved:
        print("No approved videos to upload.")
        return

    uploaded_log = load_json(UPLOADED_LOG)
    uploaded_ids = {u["id"] for u in uploaded_log}

    for video in approved:
        if video["id"] in uploaded_ids:
            print(f"Already uploaded: {video['title']}")
            continue

        print(f"\nProcessing: {video['title']}")

        yt_url = upload_to_youtube(video)
        if yt_url:
            # Find corresponding clips
            clip_files = list(CLIPS_DIR.glob(f"*{video.get('idea_id', '')[:15]}*.mp4"))

            log_entry = {
                "id": video["id"],
                "title": video["title"],
                "youtube_url": yt_url,
                "instagram_clips": [str(c) for c in clip_files],
                "uploaded_at": datetime.now().isoformat(),
                "pillar": video.get("pillar"),
            }
            uploaded_log.append(log_entry)
            save_json(UPLOADED_LOG, uploaded_log)

            if clip_files:
                print(f"\n  {len(clip_files)} Instagram clips ready:")
                for c in clip_files:
                    print(f"    {c}")
                print("  Upload these to Instagram manually or set up Graph API.")

    save_json(UPLOADED_LOG, uploaded_log)
    print("\nUpload session complete. Log saved to queue/uploaded_log.json")


def main():
    print("\n=== JumboPack Uploader ===\n")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "upload":
            upload_all_approved()
        elif cmd == "log":
            log = load_json(UPLOADED_LOG)
            for entry in log:
                print(f"  [{entry['uploaded_at'][:10]}] {entry['title']}")
                print(f"    YouTube: {entry.get('youtube_url', 'N/A')}")
                clips = entry.get("instagram_clips", [])
                print(f"    IG Clips: {len(clips)}")
        return

    print("Setup required:")
    print("  YouTube:   Put client_secret.json in credentials/")
    print("  Instagram: Set INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_ACCOUNT_ID env vars")
    print()
    upload_all_approved()


if __name__ == "__main__":
    main()
