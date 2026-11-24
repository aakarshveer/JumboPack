"""
JumboPack - Main Entry Point
Run this to manage your entire content pipeline.
"""

import sys
import os


MENU = """
╔══════════════════════════════════════════╗
║          JUMBOPACK v1.0                 ║
║    Your YouTube/Instagram Autopilot     ║
╚══════════════════════════════════════════╝

  PIPELINE:
  1. Generate content ideas       (content_brain.py)
  2. Approve/reject ideas         (approval_cli.py ideas)
  3. Generate scripts             (video_pipeline.py scripts)
  4. [YOU] Record videos
  5. Approve videos for upload    (approval_cli.py videos)
  6. Upload to YouTube            (uploader.py upload)
  7. Create Instagram clips       (video_pipeline.py clip <file>)

  UTILS:
  8. Queue status                 (approval_cli.py status)
  9. Weekly report                (reporter.py)
  0. Exit

"""

COMMANDS = {
    "1": "python content_brain.py",
    "2": "python approval_cli.py ideas",
    "3": "python video_pipeline.py scripts",
    "5": "python approval_cli.py videos",
    "6": "python uploader.py upload",
    "8": "python approval_cli.py status",
    "9": "python reporter.py",
}


def main():
    while True:
        print(MENU)
        choice = input("Enter number: ").strip()

        if choice == "0":
            print("Bye!")
            break
        elif choice == "4":
            print("\n[YOU] Record your video using the script in /videos/")
            print("Then run option 7 to link the file: python video_pipeline.py link <id> <file>")
            input("\nPress Enter to continue...")
        elif choice == "7":
            file_path = input("Enter video file path: ").strip().strip('"')
            os.system(f'python video_pipeline.py clip "{file_path}"')
        elif choice in COMMANDS:
            os.system(COMMANDS[choice])
            input("\nPress Enter to continue...")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
