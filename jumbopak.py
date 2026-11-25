"""
JumboPack - Main Entry Point
Run this to manage your entire content pipeline.
"""

import sys
import os
import subprocess

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed yet; run setup.py first


MENU = """
╔══════════════════════════════════════════╗
║          JUMBOPACK v2.0 - Phase A       ║
║    Faceless AI Video Autopilot          ║
╚══════════════════════════════════════════╝

  IDEAS:
  1. Generate ideas (manual pillars)   (content_brain.py)
  t. Trending topics today             (content_brain.py --trending)
  2. Approve/reject ideas              (approval_cli.py ideas)

  FACELESS VIDEO PIPELINE:
  3. Generate scripts                  (video_pipeline.py scripts)
  b. Auto-build faceless video         (auto_builder.py <id>)
  B. Auto-build ALL pending videos     (auto_builder.py all)
  5. Approve videos for upload         (approval_cli.py videos)
  6. Upload to YouTube                 (uploader.py upload)
  7. Create Instagram/Shorts clips     (video_pipeline.py clip <file>)

  UTILS:
  8. Queue status                      (approval_cli.py status)
  9. Weekly report                     (reporter.py)
  0. Exit

"""

COMMANDS = {
    "1": ["python", "content_brain.py"],
    "t": ["python", "content_brain.py", "--trending"],
    "2": ["python", "approval_cli.py", "ideas"],
    "3": ["python", "video_pipeline.py", "scripts"],
    "B": ["python", "auto_builder.py", "all"],
    "5": ["python", "approval_cli.py", "videos"],
    "6": ["python", "uploader.py", "upload"],
    "8": ["python", "approval_cli.py", "status"],
    "9": ["python", "reporter.py"],
}


def run(cmd: list):
    """Run a subprocess command and wait for it to finish."""
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[!] Command exited with code {result.returncode}")


def main():
    while True:
        print(MENU)
        choice = input("Enter number: ").strip()

        if choice == "0":
            print("Bye!")
            break
        elif choice == "4":
            print("\n[YOU] Record your video using the script in /videos/")
            print("OR use auto-build (option b) for faceless video — no recording needed!")
            print("To link your own recorded file, run:")
            print("  python video_pipeline.py link <id> <file.mp4>")
            input("\nPress Enter to continue...")
        elif choice == "b":
            vid_id = input("Enter video ID to auto-build: ").strip()
            if vid_id:
                run(["python", "auto_builder.py", vid_id])
            input("\nPress Enter to continue...")
        elif choice == "7":
            file_path = input("Enter video file path: ").strip().strip('"')
            run(["python", "video_pipeline.py", "clip", file_path])
        elif choice in COMMANDS:
            run(COMMANDS[choice])
            input("\nPress Enter to continue...")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
