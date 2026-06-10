
# Stoic Media Factory — Modern Stoic Pipeline
# https://github.com/Hazy019/modern-stoic-pipeline

## What This Is

A fully autonomous, high-retention Python pipeline that generates, assembles, and publishes 
**10-minute faceless YouTube videos** focusing on **Modern Stoicism and Dark Psychology**.

- **Script**: Google Gemini 1.5 Flash / Groq Llama 3.3 (Stoic Master Prompt v4.0)
- **Voice**: edge-tts, `en-US-SteffanNeural`, −20% rate (Commanding/Intellectual)
- **Visuals**: Chapter-based scene switching (60s intervals) using FFmpeg
- **Assets**: Read-only GDrive library for backgrounds and music
- **Publishing**: YouTube Data API v3 (Direct Public Upload)
- **Notifications**: 5 Discord webhook channels

---

## Quick Start

### 1. Prerequisites

```powershell
# FFmpeg must be on PATH
ffmpeg -version

# Python 3.10+
python --version
```

### 2. Install

```powershell
git clone https://github.com/Hazy019/modern-stoic-pipeline.git
cd modern-stoic-pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```powershell
copy .env.example .env
# Edit .env — fill in all keys
```

**Required credentials:**
- `GEMINI_API_KEY`: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- `credentials.json`: Desktop OAuth2 client from Google Cloud Console
- `YOUTUBE_CHANNEL_ID`: Your channel ID

### 4. First Run

```powershell
# Auto-pick next unused topic from config/topics.py
python pipeline.py

# Test script generation only
python pipeline.py --dry-run
```

---

## Pipeline Steps

| Step | Function | Description |
|------|----------|-------------|
| 1 | `sync_assets()` | Downloads latest BG videos/music from GDrive (Read-Only) |
| 2 | `generate_script()` | Gemini/Groq → 1,500 word structured JSON script |
| 3 | `generate_audio()` | edge-tts → `.mp3` (SteffanNeural) |
| 4 | `build_10min_video()` | FFmpeg scene-switching + Quote overlays |
| 5 | `generate_short()` | 60s Shorts extraction with captions |
| 6 | `upload_video()` | Direct YouTube upload (Public) |

---

## Hardware Constraint

**Machine: AMD Ryzen 7 2700U, 12 GB RAM.**

The pipeline uses FFmpeg stream-copy and lightweight re-encoding to minimize CPU load and prevent thermal shutdown. 10-minute videos are processed in segments to keep memory usage low.

---

## Project Structure

```
modern-stoic-pipeline/
├── pipeline.py              # Main orchestrator (v11.0)
├── config/
│   ├── topics.py            # 20 Stoic topic bank
│   └── master_prompt_v3.txt # Stoic v4.0 Master Prompt
├── src/
│   ├── generator.py         # Stoic script generation
│   ├── gdrive_assets.py     # Read-only Drive asset manager
│   ├── audio/tts.py         # edge-tts synthesis
│   ├── video/
│   │   ├── builder_10min.py # 10-minute assembler
│   │   └── shorts_maker.py  # Shorts extraction
│   └── publish/
│       └── youtube_10min.py # Direct YouTube publisher
├── archive/                 # (Cleaned Up) Legacy files
├── assets/                  # Local asset cache
├── outputs/                 # Generated .mp4 and .json files
└── logs/                    # Daily pipeline logs
```
