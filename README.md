# JumboPack 🎬

Aakar's automated YouTube + Instagram content pipeline.

## Content Pillars
- **Travel Vlog** — Ghoomne ke videos (Bihar + nearby places)
- **AI/Tech** — AI tools, demos, tutorials for Indian audience  
- **Project Build** — Coding projects documented on camera
- **Daily Interesting** — Day-in-life, experiments, interesting things
- **Bihar Documentary** — History, culture, hidden places of Bihar

## Pipeline Flow

```
IDEA → Approve → Script → [Record] → Approve Video → Upload YouTube → Clip → Instagram
```

## Quick Start

```bash
# 1. Setup (run once)
python setup.py

# 2. Run main menu
python jumbopak.py
```

## Direct Commands

```bash
python content_brain.py          # Generate ideas with Gemini
python approval_cli.py ideas     # Approve/reject ideas
python video_pipeline.py scripts # Generate scripts for approved ideas
python approval_cli.py videos    # Approve videos before upload
python uploader.py upload        # Upload to YouTube
python video_pipeline.py clip <file.mp4>  # Create Instagram clips
python reporter.py               # Weekly Gemini report
```

## Free Tools Used
| Tool | Purpose | Cost |
|------|---------|------|
| Gemini API | Content ideas + scripts + reports | Free (15 req/min) |
| YouTube Data API v3 | Upload videos | Free (10k units/day) |
| FFmpeg | Instagram clip creation | Free & open source |
| Instagram Graph API | Reel uploads | Free (needs Meta Business) |

## Setup Requirements
1. **Gemini API key** — [aistudio.google.com](https://aistudio.google.com) (free)
2. **YouTube credentials** — Google Cloud Console → YouTube Data API v3
3. **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/download.html)
4. **Instagram** (optional) — Meta for Developers → Instagram Graph API
