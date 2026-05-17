# Apple Music Downloader (Python)

[English](README.md) / [简体中文](README-CN.md)

A Python rewrite of the Apple Music ALAC / Dolby Atmos / AAC Downloader.

## 🚀 Features

- Download ALAC (lossless up to 192kHz), Dolby Atmos (E-AC3), AAC-LC
- Inline cover art and LRC lyrics embedding
- Word-by-word (syllable) lyrics support
- Artist discography download (`--all-album`)
- Interactive search with arrow-key navigation (`--search`)
- Music Video download with Widevine decryption
- Post-download format conversion (FLAC/MP3/Opus/WAV via ffmpeg)
- ALAC packet repair (`alacfix`)

## 📋 Prerequisites

### Required External Tools

| Tool | Install |
|------|---------|
| **MP4Box** (gpac) | [gpac nightly](https://gpac.io/downloads/gpac-nightly-builds/) |
| **mp4decrypt** (Bento4) | [Bento4](https://www.bento4.com/downloads/) |
| **ffmpeg** | `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux) |
| **[wrapper](https://github.com/WorldObservationLog/wrapper)** | FairPlay decryption service (must be running separately) |

### Python Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) (recommended)

## 📦 Installation

```bash
# Clone the repository
git clone <repo-url>
cd apple-music-downloader-py

# Install with Poetry
poetry install

# Or with pip
pip install -e .
```

## ⚙️ Configuration

Copy the example config and fill in your tokens:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:
- `media-user-token`: Required for lyrics, AAC-LC, and MV downloads
- `authorization-token`: Automatically fetched; fill in only if auto-fetch fails
- `storefront`: 2-letter country code matching your Apple Music account

## 🎵 Usage

```bash
# Download an album
am-dl https://music.apple.com/us/album/1989-taylors-version/1713845538

# Download with Dolby Atmos
am-dl --atmos https://music.apple.com/us/album/1989-taylors-version/1713845538

# Download single song
am-dl --song https://music.apple.com/us/song/style/1713845538?i=1713845610

# Interactive track selection
am-dl --select https://music.apple.com/us/album/1989-taylors-version/1713845538

# Download all albums by an artist
am-dl --all-album https://music.apple.com/us/artist/taylor-swift/159260351

# Interactive search
am-dl --search album "1989"

# Debug mode (show quality info)
am-dl --debug https://music.apple.com/us/album/1989-taylors-version/1713845538

# Output JSON summary
am-dl --json https://music.apple.com/us/album/1989-taylors-version/1713845538

# ALAC Fix tool
alacfix input.m4a
alacfix -i input.m4a
```

## 🐳 Docker

```bash
# Build
docker build -t apple-music-downloader .

# Run (wrapper must be accessible via host network)
docker run --network host \
  -v ./downloads:/downloads \
  -v ./config.yaml:/app/config.yaml \
  apple-music-downloader [args]
```

## 🏗️ Project Structure

```
apple-music-downloader-py/
├── am_downloader/
│   ├── cli.py              # CLI entry point
│   ├── api/                # Apple Music API clients
│   ├── models/             # Data models (pydantic)
│   ├── download/           # Download engines (M3U8/AAC/MV)
│   ├── cdm/                # Widevine CDM implementation
│   ├── lyrics/             # TTML → LRC conversion
│   ├── alacfix/            # ALAC packet repair
│   └── utils/              # Utilities
├── cmd/alacfix.py          # Standalone ALAC fix CLI
├── tests/                  # Test suite
├── config.yaml.example     # Configuration template
└── Dockerfile
```

## 🧪 Development

```bash
# Run tests
poetry run pytest tests/ -v

# Lint
poetry run ruff check am_downloader/

# Type check
poetry run mypy am_downloader/
```

## 📝 License

MIT License
