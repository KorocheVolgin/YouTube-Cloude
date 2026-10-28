<div align="center">

# 🎥 YouTube-Cloude

### Hide files in YouTube videos — steganographic file storage

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-required-orange)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-None%20(yet)-red)](#license)
[![Tests](https://github.com/valeksan/YouTube-Cloude/actions/workflows/test.yml/badge.svg)](https://github.com/valeksan/YouTube-Cloude/actions/workflows/test.yml)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

*Cross-platform app (CLI + Qt/Kivy GUI, Windows/Linux/macOS/Android) to hide any file in a YouTube video and restore it later — YTV1/YTV2/YTV3 (Reed-Solomon), AES-256-GCM, bundled ffmpeg.*

</div>

---

## How It Works

```
File → [Encoder] → Coloured blocks in video frames → YouTube
YouTube → [Decoder] → Coloured blocks → Original file
```

Each 4-bit chunk of your file is mapped to one of 16 colours and drawn as a block on a 1920×1080 frame. Three redundant copies per frame survive YouTube's compression. An end-of-file marker and header with filename/size ensure reliable recovery.

## ⚠️ Risks and Disclaimer

<details>
<summary>Educational / ToS / Legal — click to expand</summary>

This project is an **educational and research tool** for steganography vs lossy video compression. Not for production or ToS-violating use.

**Not an attack:** does not damage infra, disrupt users, bypass auth, or distribute malware — concern is *misuse of service* (YouTube is for video, not covert storage).

**YouTube ToS:** [Terms](https://www.youtube.com/t/terms) §5.1/§5.5 — non-intended use may lead to removal/suspension. Automated systems may detect such content.

**Legal:** unauthorised concealment may fall under CMA 1990 (UK) / 18 U.S.C. §1030 (US); ToS breach may cause civil liability.

**No warranty:** provided “as is”; use only lawfully and at your own risk. By using it you accept this.

</details>

## Features

- 🔐 **AES-256-GCM encryption** — PBKDF2-HMAC-SHA256 (200k iters) + random salt/nonce/tag, legacy CBC still decodes
- 🎞️ **Three formats** — YTV1 (standard), YTV2 (21× denser), **YTV3** (30 FPS, RS + luma, yuv420p-resilient)
- 📊 **Reed-Solomon[^rs] + CRC32** — RS(255,223) corrects 16 byte errors/chunk (YTV3) + CRC32 on all formats
- 🔀 **Interlacing[^il]** — improved YouTube retention (YTV1/YTV2, ignored for YTV3)
- 🗜️ **zlib compression** — `--compress` before encoding, auto-skipped if would enlarge
- 🖥️ **GUI** — PySide6 (Qt) primary, unified `gui_service` layer; Tkinter deprecated, Kivy for Android
- 📱 **Android** — Buildozer APK (arm64, API 33), Kivy GUI
- 📦 **Batch mode** — encode entire directories at once
- 📤 **YouTube upload/download** — via yt-dlp and YouTube Data API v3 (planned)

## Quick Start

### Install Dependencies

```bash
# Using Makefile (creates .venv/ automatically)
make setup         # runtime only
make setup-dev     # + pytest for development

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Required: FFmpeg (install separately, not included in pip)
sudo apt install ffmpeg    # Linux
brew install ffmpeg        # macOS
```

### Encode a File

```bash
# Basic encoding (YTV1 format)
youtube-cloude encode secret.zip video.mp4

# With encryption (PBKDF2 + AES-GCM)
youtube-cloude encode secret.zip video.mp4 --key "my-password"

# YTV2 format (21× denser, 15 FPS)
youtube-cloude encode secret.zip video.mp4 --format ytv2

# YTV3 format (30 FPS, RS + grayscale luma — best for YouTube, no interlace needed)
youtube-cloude encode secret.zip video.mp4 --format ytv3

# With compression (zlib, auto-skipped if would enlarge)
youtube-cloude encode secret.zip video.mp4 --compress

# YTV3 + GCM + compress (recommended for text/logs)
youtube-cloude encode secret.zip video.mp4 --format ytv3 --key "my-password" --compress

# With interlacing (YTV1/YTV2 only, better YouTube quality)
youtube-cloude encode secret.zip video.mp4 --interlace

# Override max file size (default: 100 MB YTV1, 500 MB YTV2/YTV3)
youtube-cloude encode big.iso video.mp4 --max-size 200

# Or via Makefile
make run CMD="encode secret.zip video.mp4"
```

### Decode a Video

```bash
# Auto-detects format, interlacing, RS, compression and CRC from the video
youtube-cloude decode video.mp4

# With decryption key (PBKDF2 + GCM, legacy CBC also supported)
youtube-cloude decode video.mp4 --key "my-password"
```

### Batch Encode a Directory

```bash
youtube-cloude encode-dir ./my-data/ ./output/ --format ytv3 --compress
```

> **Note:** Output `.mp4` can be freely renamed — the original filename is stored inside the video header (`FORMAT:...:FILE:<name>`). On decode the file is always restored with its original name, regardless of what the `.mp4` is called (including YouTube's `videoplayback.mp4` after download).

### Launch GUI

```bash
# PySide6 (Qt) — recommended, responsive layout
youtube-cloude-gui-qt
make gui-qt

# Tkinter — legacy, simpler
youtube-cloude-gui
make gui
```
```

### Windows SmartScreen

The `.exe` files in Releases are **unsigned** (no paid code-signing certificate). On first launch Windows may show:

> **"Windows protected your PC" / "SmartScreen prevented an unrecognized app"**

Click `More info` → `Run anyway` to start. Alternative: right-click the `.exe` → `Properties` → check `Unblock`, or in PowerShell:

```powershell
Unblock-File .\youtube-cloude-gui-*.exe
# or for all downloads
Get-ChildItem -Recurse | Unblock-File
```

The warning disappears after the file gains reputation (enough installs without detections). Future signed builds will not show this.

### Build Standalone Binaries

```bash
make build          # CLI binary via PyInstaller
make build-gui      # GUI app via PyInstaller (--windowed, no console)
make build-nuitka   # CLI binary via Nuitka (alternative)
# Output: dist/youtube-cloude  or  dist/youtube-cloude-gui
```

### Run Tests

```bash
make test           # full suite
make test-fast      # stop on first failure
```

## Format Comparison

| Property | YTV1 | YTV2 | **YTV3** |
|----------|------|------|----------|
| Block size | 24×16 px | 8×8 px | 8×8 px |
| Spacing | 4 px | 1 px | 2 px |
| Markers | 80 px | 16 px | 16 px |
| Grid | 62×46 | 209×116 | 188×104 |
| Blocks/frame | 2,852 | 24,244 | 19,552 |
| FPS | 6 | 15 | **30** |
| Palette | 16 colours (4 bit) | 16 colours (4 bit) | **4 grays (2 bit luma)** |
| ECC | none | 3× replication | **RS[^rs] (255,223)** |
| **Density** | **1×** | **21.3×** | **~16× + RS** |
| yuv420p safe | No (needs interlace[^il]) | No (needs interlace[^il]) | **Yes** |
| Max file (default) | 100 MB (~3.4h) | 500 MB (~48 min) | 500 MB (~32 min) |
| Max file (override) | `--max-size 200` | `--max-size 200` | `--max-size 200` |

## Benchmark

**Test system (2026-08-31):** AMD Ryzen 3 PRO 4350G (4C/8T, 3.8 GHz), 28 GB RAM, Windows 11, Python 3.13, FFmpeg N-111283, `benchmark_input.png` 550 KB (800×600 geometric + 80k noise pixels). All variants verified with MD5 — **12/12 passed**.

| Variant | Encode | Decode | Video Size | Overhead | Verified |
|---------|--------|--------|------------|----------|----------|
| YTV1 | 45.8s | 13.4s | 45.8 MB | 85.2× | YES |
| YTV1 + AES | 45.0s | 13.5s | 45.8 MB | 85.2× | YES |
| YTV1 + interlace | 39.5s | 13.9s | 367.7 MB | 684.3× | YES |
| YTV1 + interlace + AES | 39.0s | 14.7s | 368.5 MB | 685.8× | YES |
| YTV2 | 18.0s | 13.8s | 17.9 MB | 33.2× | YES |
| YTV2 + AES | 18.2s | 13.8s | 17.9 MB | 33.3× | YES |
| YTV2 + interlace | 15.4s | 10.7s | 137.3 MB | 255.5× | YES |
| YTV2 + interlace + AES | 16.3s | 12.1s | 137.6 MB | 256.2× | YES |
| **YTV3** | 32.6s | 26.4s | 21.0 MB | 39.1× | YES |
| **YTV3 + AES** | 32.0s | 26.4s | 21.0 MB | 39.0× | YES |
| **YTV3 + compress** | 31.8s | 26.2s | 21.0 MB | 39.1× | YES |
| **YTV3 + compress + AES** | 31.9s | 26.4s | 21.0 MB | 39.0× | YES |

### Key Findings

- **YTV2 is 2.5× faster/smaller than YTV1** (18s/17.9 MB vs 46s/45.8 MB)
- **YTV3** is `yuv420p`-safe without interlace + RS(255,223) for 16-byte correction — avoids 15× interlace bloat

## How Interlace Works

> Interlace[^il] — see footnote below.

<details>
<summary>Details (diagrams + when to use)</summary>

### The Pipeline

```
Interlaced encoding:       YouTube:              Downloaded:
┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐
│ 365 MB lossless │ → │ Re-encode H.264  │ → │ ~5-10 MB     │
│ yuv444p CRF 0   │   │ yuv420p CRF ~23  │   │ yuv420p      │
└─────────────────┘   └──────────────────┘   └──────────────┘
                                               ↓ deinterlace
                                          ┌──────────────┐
                                          │ File identical│
                                          │ to original!  │
                                          └──────────────┘
```

YouTube **destroys** lossless and `yuv444p` — leaving lossy H.264. But the block data survives because interlacing has already "hidden" it between rows. The codec sees a "noisy" frame and preserves detail. On download — deinterlace, and blocks are intact.

### The Problem

YouTube re-encodes every uploaded video with H.264. This codec uses **chroma subsampling (yuv420p)** which halves vertical color resolution. For our coloured blocks this is catastrophic — the encoder sees sharp colour transitions and "smooths" them, destroying the block data.

```
Original blocks:     After yuv420p subsampling:
┌───┬───┬───┐        ┌───┬───┬───┐
│RED│GRN│BLU│   →    │RED│GRN│BLU│  ← looks ok...
├───┼───┼───┤        ├───┼───┼───┤
│BLU│RED│GRN│        │???│???│???│  ← colors blend together
└───┴───┴───┘        └───┴───┴───┘
```

Adjacent rows with different colours get merged by the encoder — it doesn't know those colours are "important data" and treats them as noise to compress.

### The Solution: Interlace

**Before encoding**, we interlace the frame — interleave rows from the top and bottom halves:

```
Original:              After interlace:
Row 0: ██ RED ██       Row 0: ██ RED ██     (from top half)
Row 1: ██ GRN ██       Row 1: ██ BLU ██     (from bottom half)
Row 2: ██ BLU ██       Row 2: ██ GRN ██     (from top half)
Row 3: ██ RED ██       Row 3: ██ RED ██     (from bottom half)
Row 4: ██ GRN ██       Row 4: ██ GRN ██     (from top half)
Row 5: ██ BLU ██       Row 5: ██ GRN ██     (from bottom half)
```

Now adjacent rows are **spatially distant** in the original image. H.264's motion compensation and DCT transforms can't correlate them — the codec treats the frame as "noisy" and preserves more detail. After YouTube re-encodes and downloads, we **deinterlace** to restore the original layout.

### Why the File is 20× Larger

Interlace requires **lossless encoding** (CRF 0) to preserve the exact block colours. Lossless H.264 with **yuv444p** (full chroma resolution) produces massive files — but it's the only way to guarantee the blocks survive YouTube's processing pipeline.

### When to Use Interlace

| Scenario | Use Interlace? |
|----------|---------------|
| Local storage / backup | No — wastes space |
| Upload to YouTube | **Yes** — blocks survive re-encoding |
| Testing locally | No — not needed |
| Research / demos | Optional — for completeness |

</details>

## Project Structure

```
YouTube-Cloude/
├── src/youtube_cloude/  # encoder, decoder, core (RS/GCM), GUI (Qt/Kivy)
├── tests/               # 36 tests
├── .github/workflows/   # test.yml / release.yml
├── pyproject.toml / Makefile / README.md
```

## Encryption

**Supported:** `AES-256-GCM` with `PBKDF2-HMAC-SHA256` (200 000 iterations).

```bash
# Key from command line
youtube-cloude encode file.zip video.mp4 --key "secret"

# Key from file (auto-loaded if key.txt exists)
echo "my-secret-key" > key.txt
youtube-cloude encode file.zip video.mp4
youtube-cloude decode video.mp4   # key.txt auto-detected
```

> ℹ️ New files use `SALT:NONCE:TAG` (GCM); old `IV` (CBC) files auto-fallback. Wrong key fails with `MAC check failed`.

## Compression

Optional zlib compression before encoding (auto-skipped if would enlarge):

```bash
youtube-cloude encode big.log video.mp4 --compress
youtube-cloude encode big.log video.mp4 --format ytv3 --compress --key "secret"
```

Header carries `:COMPRESS:zlib` and the decoder decompresses transparently.

## Credits

This project builds on the work of:

| Author | Contribution |
|--------|-------------|
| [**@KorocheVolgin**](https://github.com/KorocheVolgin) | Original concept and implementation |
| [**@Hinderchik**](https://github.com/Hinderchik) | Security hardening, code quality |
| [**@IvanSCP**](https://github.com/IvanSCP) | argparse CLI, key-file support |
| [**@sosatel30000**](https://github.com/sosatel30000) | YTV2 format, region sampling, progress callbacks |
| [**@Maksim4081862**](https://github.com/Maksim4081862) | GUI concepts, tkinter implementation |
| [**@Verdgil**](https://github.com/Verdgil) | AES-256-CBC encryption (PR [#10](https://github.com/KorocheVolgin/YouTube-Cloude/pull/10)) |

<details>
<summary>Related Projects</summary>

- [YouTube-Cloude (original)](https://github.com/KorocheVolgin/YouTube-Cloude)
- [YouTube-Cloude-Fork](https://github.com/Hinderchik/YouTube-Cloude-Fork)
- [YouTube-Cloude](https://github.com/IvanSCP/YouTube-Cloude)
- [YouTube-Cloud-GUI](https://github.com/Maksim4081862/YouTube-Cloud-GUI)

</details>

## Contributing

PRs welcome — fork, branch, `make setup-dev` + `make test`, push.

## License

The `LICENSE` file on this branch contains the GNU GPL version 3 text. The
project's code provenance and the scope of that license have not yet been
verified for every retained contribution. Adding a license file does not by
itself establish permission to relicense code authored by others. See the
[licensing audit](docs/LICENSING_AUDIT.md) and
[third-party notices](THIRD_PARTY_NOTICES.md); please do not treat the entire
repository or previously distributed binaries as verified GPL-3.0 until the
relevant rights and dependency obligations have been checked.

[^rs]: **Reed-Solomon (RS)** — error-correcting code used in QR codes, CDs and satellite links. `RS(255,223)` means each 255-byte chunk carries 223 data bytes + 32 parity bytes and can fix up to 16 erroneous bytes per chunk. In YTV3 it is applied before 2-bit luma blocking, so a few color shifts or lost blocks after YouTube's `yuv420p` re-encode are automatically repaired — no interlacing needed.

[^il]: **Interlacing** — mitigation for YouTube's H.264 `yuv420p` chroma subsampling. Before encoding, the frame's top and bottom halves are interleaved row-by-row (`even ← top`, `odd ← bottom`), which makes adjacent rows spatially uncorrelated; the codec then preserves more detail under lossy re-encode. On decode the rows are de-interleaved. Cost: requires lossless `yuv444p` `CRF 0`, so files become ~15× larger (e.g. 17.9 MB → 137 MB for YTV2). YTV3 avoids this by using luma-only grayscale blocks + Reed-Solomon.

---

<!-- SEO Keywords (hidden, indexed in raw + topics): youtube cloud storage, free cloud drive, store files on youtube, hide files in video, video steganography, file storage, covert channel, youtube as cloud -->
