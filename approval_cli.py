"""
JumboPack - Approval CLI
Review and approve/reject content ideas and generated videos.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

QUEUE_DIR = Path("queue")
PENDING_IDEAS = QUEUE_DIR / "pending_ideas.json"
APPROVED_IDEAS = QUEUE_DIR / "approved_ideas.json"
PENDING_VIDEOS = QUEUE_DIR / "pending_videos.json"
APPROVED_VIDEOS = QUEUE_DIR / "approved_videos.json"
REJECTED_DIR = QUEUE_DIR / "rejected"


def load_json(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_json(path: Path, data):
    QUEUE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_idea(idea: dict):
    print(f"\n{'='*60}")
    print(f"PILLAR: {idea.get('pillar', 'unknown').upper()}")
    print(f"TITLE:  {idea['title']}")
    print(f"\nHOOK (first 15s):")
    print(f"  {idea.get('hook', 'N/A')}")
    print(f"\nOUTLINE:")
    for point in idea.get("outline", []):
        print(f"  • {point}")
    print(f"\nTHUMBNAIL: {idea.get('thumbnail_concept', 'N/A')}")
    print(f"DURATION:  ~{idea.get('estimated_duration', '?')} min")
    print(f"TAGS: {', '.join(idea.get('tags', []))}")
    print(f"{'='*60}")


def print_video(video: dict):
    print(f"\n{'='*60}")
    print(f"VIDEO READY FOR UPLOAD")
    print(f"TITLE:    {video.get('title', 'N/A')}")
    print(f"FILE:     {video.get('file_path', 'N/A')}")
    print(f"PLATFORM: {video.get('platform', 'youtube')}")
    print(f"PILLAR:   {video.get('pillar', 'N/A')}")
    desc = video.get("description", "")
    if desc:
        print(f"\nDESCRIPTION PREVIEW:")
        print(f"  {desc[:200]}...")
    print(f"{'='*60}")


def review_ideas():
    ideas = load_json(PENDING_IDEAS)
    pending = [i for i in ideas if i.get("status") == "pending"]

    if not pending:
        print("\nNo pending ideas to review.")
        return

    approved = load_json(APPROVED_IDEAS)
    rejected_log = []
    still_pending = []

    print(f"\n{len(pending)} ideas waiting for your review.\n")

    for idea in pending:
        clear_screen()
        print_idea(idea)
        print("\n[A]pprove  [R]eject  [S]kip  [Q]uit")
        choice = input("Your choice: ").strip().lower()

        if choice == "a":
            idea["status"] = "approved"
            idea["approved_at"] = datetime.now().isoformat()
            approved.append(idea)
            print("[OK] Approved!")
        elif choice == "r":
            reason = input("Reason (optional): ").strip()
            idea["status"] = "rejected"
            idea["rejected_reason"] = reason
            rejected_log.append(idea)
            print("[--] Rejected.")
        elif choice == "q":
            still_pending.append(idea)
            break
        else:
            still_pending.append(idea)

    all_ideas = [i for i in ideas if i.get("status") != "pending"]
    all_ideas.extend(still_pending)
    save_json(PENDING_IDEAS, all_ideas)
    save_json(APPROVED_IDEAS, approved)

    if rejected_log:
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        fname = REJECTED_DIR / f"rejected_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        save_json(fname, rejected_log)

    print(f"\nDone! Approved ideas saved. Run: python video_pipeline.py to process approved ideas.")


def review_videos():
    videos = load_json(PENDING_VIDEOS)
    pending = [v for v in videos if v.get("status") == "pending"]

    if not pending:
        print("\nNo videos pending review.")
        return

    approved = load_json(APPROVED_VIDEOS)
    still_pending = []

    print(f"\n{len(pending)} videos ready for review.\n")

    for video in pending:
        print_video(video)

        # Open the video file for review if it exists
        fpath = video.get("file_path", "")
        if fpath and Path(fpath).exists():
            print(f"\nOpening video: {fpath}")
            os.startfile(fpath) if os.name == "nt" else os.system(f"xdg-open '{fpath}'")

        print("\n[A]pprove  [R]eject  [S]kip  [Q]uit")
        choice = input("Your choice: ").strip().lower()

        if choice == "a":
            video["status"] = "approved"
            video["approved_at"] = datetime.now().isoformat()
            approved.append(video)
            print("[OK] Approved for upload!")
        elif choice == "r":
            video["status"] = "rejected"
            still_pending.append(video)
            print("[--] Rejected.")
        elif choice == "q":
            still_pending.append(video)
            break
        else:
            still_pending.append(video)

    remaining = [v for v in videos if v.get("status") != "pending"] + still_pending
    save_json(PENDING_VIDEOS, remaining)
    save_json(APPROVED_VIDEOS, approved)
    print("\nRun: python uploader.py to upload approved videos.")


def show_status():
    print("\n=== JumboPack Queue Status ===")
    pending_ideas = load_json(PENDING_IDEAS)
    approved_ideas = load_json(APPROVED_IDEAS)
    pending_videos = load_json(PENDING_VIDEOS)
    approved_videos = load_json(APPROVED_VIDEOS)

    print(f"\nIDEAS:")
    print(f"  Pending review:  {len([i for i in pending_ideas if i.get('status') == 'pending'])}")
    print(f"  Approved (ready to script): {len(approved_ideas)}")

    print(f"\nVIDEOS:")
    print(f"  Pending review:  {len([v for v in pending_videos if v.get('status') == 'pending'])}")
    print(f"  Approved (ready to upload): {len(approved_videos)}")
    print()


def main():
    print("\n=== JumboPack Approval CLI ===")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "ideas":
            review_ideas()
        elif cmd == "videos":
            review_videos()
        elif cmd == "status":
            show_status()
        return

    show_status()
    print("\nWhat to review?")
    print("  1. Content Ideas")
    print("  2. Videos (before upload)")
    print("  3. Show status")
    print("  0. Exit")

    choice = input("\nEnter number: ").strip()
    if choice == "1":
        review_ideas()
    elif choice == "2":
        review_videos()
    elif choice == "3":
        show_status()


if __name__ == "__main__":
    main()
