"""
JumboPack - Setup Script
Run once to install dependencies and configure API keys.
"""

import subprocess
import sys
import os
from pathlib import Path


REQUIRED_PACKAGES = [
    "google-genai",             # New official Gemini SDK (replaces google-generativeai)
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "requests",
    "python-dotenv",
    "edge-tts",                 # Free Microsoft TTS for voiceover
    "Pillow",                   # Scene card image generation
    "feedparser",               # RSS feed parsing (optional, used by trend_scout)
]

ENV_FILE = Path(".env")
GITIGNORE = Path(".gitignore")


def install_packages():
    print("Installing Python packages...")
    for pkg in REQUIRED_PACKAGES:
        print(f"  Installing {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=False)
    print("Done.\n")


def setup_env():
    if ENV_FILE.exists():
        print(".env already exists. Edit it manually if needed.\n")
        return

    print("Setting up .env file...")
    gemini_key = input("Enter your Gemini API key (get free at aistudio.google.com): ").strip()

    env_content = f"""# JumboPack Environment Variables
# DO NOT commit this file to git

GEMINI_API_KEY={gemini_key}

# YouTube: Put your client_secret.json from Google Cloud Console in credentials/
YOUTUBE_CLIENT_SECRET_PATH=credentials/youtube_client_secret.json

# Instagram (optional - set up later)
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_ACCOUNT_ID=
"""
    ENV_FILE.write_text(env_content, encoding="utf-8")
    print(".env created.\n")


def setup_gitignore():
    if GITIGNORE.exists():
        print(".gitignore already exists — skipping to preserve your entries.\n")
        return
    gitignore_content = """.env
credentials/
*.pickle
__pycache__/
*.pyc
queue/rejected/
videos/*.mp4
clips/
reports/
*.egg-info/
.DS_Store
Thumbs.db
"""
    GITIGNORE.write_text(gitignore_content, encoding="utf-8")
    print(".gitignore created.\n")


def create_dirs():
    dirs = ["queue", "videos", "clips", "reports", "credentials"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    Path("credentials/.gitkeep").touch()
    print("Directories created: queue/, videos/, clips/, reports/, credentials/\n")


def main():
    print("\n=== JumboPack Setup ===\n")

    install_packages()
    setup_gitignore()
    create_dirs()
    setup_env()

    print("""
Setup complete! Next steps:

1. Load .env:
   Windows: set GEMINI_API_KEY=your_key (or use python-dotenv)

2. YouTube API:
   - Go to console.cloud.google.com
   - Create project → Enable YouTube Data API v3
   - Create OAuth 2.0 credentials → Download as credentials/youtube_client_secret.json

3. Start the pipeline:
   python jumbopak.py

4. Or run directly:
   python content_brain.py    → Generate ideas
   python approval_cli.py     → Review ideas
   python video_pipeline.py   → Generate scripts
   python reporter.py         → Weekly report
""")


if __name__ == "__main__":
    main()
