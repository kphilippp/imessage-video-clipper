# iMessage Video Clipper

Split screen recordings of text message conversations into sequential, non-overlapping screenshots — ready to feed into AI.

## Problem

You want to put a text message thread into AI, but it doesn't accept video. You have a screen recording of scrolling through the conversation. This tool automatically splits that recording into clean screenshots with minimal overlap, regardless of scroll speed.

## How It Works

The tool uses **phase correlation** (FFT-based image comparison) to measure exactly how many pixels the content scrolls between consecutive video frames. It accumulates scroll displacement over time and captures a screenshot whenever a full screen's worth of new content has appeared. This naturally adapts to any scroll speed.

## Installation

```bash
git clone https://github.com/kphilippp/imessage-video-clipper.git
cd imessage-video-clipper
pip install -e .
```

## Usage

### Web UI (Recommended)

Launch the web interface for a visual drag-and-drop experience:

```bash
imessage-video-clipper-web
```

Then open **http://127.0.0.1:5050** in your browser.

- Drag & drop a `.mov` or `.mp4` screen recording
- Adjust overlap and crop settings via the gear icon
- Click **Process** and wait for extraction
- Preview screenshots in-app, then **Download All** as a ZIP

To use a custom port:

```bash
imessage-video-clipper-web --port 8080
```

### CLI

```bash
# Basic usage
imessage-video-clipper recording.mov

# Custom output directory
imessage-video-clipper recording.mov -o screenshots/

# Less overlap between screenshots
imessage-video-clipper recording.mov --overlap 0.10

# Adjust crop areas (e.g., larger status bar)
imessage-video-clipper recording.mov --top-crop 0.20 --bottom-crop 0.10

# Verbose mode (see per-frame scroll measurements)
imessage-video-clipper recording.mov -v

# Faster processing (skip every other frame)
imessage-video-clipper recording.mov --frame-skip 2
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `video` | (required) | Path to the input video file |
| `-o, --output` | `./output` | Output directory for screenshots |
| `--overlap` | `0.15` | Fraction of overlap between consecutive captures (0.0-0.5) |
| `--top-crop` | `0.15` | Fraction of frame height to exclude from top (status bar) |
| `--bottom-crop` | `0.15` | Fraction of frame height to exclude from bottom (keyboard/nav) |
| `--frame-skip` | `1` | Process every Nth frame (increase for speed) |
| `--min-confidence` | `0.05` | Minimum confidence for scroll measurement |
| `-v, --verbose` | off | Show per-frame scroll measurements |

## Output

Screenshots are saved as numbered PNGs:
```
output/
├── screenshot_001.png
├── screenshot_002.png
├── screenshot_003.png
└── ...
```

The web UI also provides a **Download All** button that packages all screenshots into a single ZIP file.

## Algorithm Details

1. **First frame** is always captured as screenshot #1
2. For each subsequent frame, **phase correlation** measures vertical pixel displacement vs. the previous frame
3. Displacement is **accumulated** over time (only downward scroll counts)
4. When accumulated scroll reaches ~85% of the content area height, the tool **waits for scrolling to settle** (for a sharp, non-blurry frame) and captures
5. After processing all frames, a **final screenshot** is captured if >20% new content remains

Edge cases handled:
- **Variable scroll speed**: adapts automatically (measures spatial displacement, not time)
- **Paused scrolling**: no displacement = no false captures
- **Fast scroll / motion blur**: low-confidence frames are skipped; settle-wait ensures sharp captures
- **iOS elastic bounce**: negative (upward) displacement is ignored
- **Notifications / overlays**: corrupted frames rejected by confidence filter
