# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-09-01

### Added
- Bundled static `ffmpeg`/`ffprobe` into Nuitka builds (`--include-data-files`) — no external `ffmpeg` install required; still falls back to system `ffmpeg` via `python -m` ([#249fa09](https://github.com/valeksan/YouTube-Cloude/commit/249fa09))
- Hide `ffmpeg`/`ffprobe` console window on Windows (`CREATE_NO_WINDOW`) during encode/decode ([#1878a33](https://github.com/valeksan/YouTube-Cloude/commit/1878a33))
- Custom `ffmpeg` selection: CLI `--ffmpeg`/`--ffprobe`, env `YOUTUBE_CLOUDE_FFMPEG`/`YOUTUBE_CLOUDE_FFPROBE`/`FFMPEG_PATH`, GUI `Settings → FFmpeg` (QSettings persistence) ([#7daaa74](https://github.com/valeksan/YouTube-Cloude/commit/7daaa74), [#b9b1815](https://github.com/valeksan/YouTube-Cloude/commit/b9b1815), [#f1203e1](https://github.com/valeksan/YouTube-Cloude/commit/f1203e1))
- FFmpeg priority: `--ffmpeg`/env → next-to-exe → `PATH` → bundled ([#9216b39](https://github.com/valeksan/YouTube-Cloude/commit/9216b39))
- GUI auto-fill: output video defaults to `<input_stem>.mp4` on file pick (Qt/Kivy/Tkinter) ([#7a860c4](https://github.com/valeksan/YouTube-Cloude/commit/7a860c4))
- GUI Stop button: encode/decode can be cancelled via the same button (`Encode` ↔ `Stop` / `Decode` ↔ `Stop`) with progress reset and `Cancelled` log — core `YouTubeEncoder`/`YouTubeDecoder` cooperative `_cancelled` flag ([#bd534e6](https://github.com/valeksan/YouTube-Cloude/commit/bd534e6))
- Benchmark: 12 variants including YTV3/compress on new hardware (Ryzen 3 PRO 4350G) ([#53c19b0](https://github.com/valeksan/YouTube-Cloude/commit/53c19b0))

### Changed
- `README` `YouTube upload/download` marked as `(planned)` — `uploader.py` exists but not yet integrated into CLI/GUI ([#8774d1a](https://github.com/valeksan/YouTube-Cloude/commit/8774d1a))

### Removed
- Legacy `AES-256-CBC` backward compatibility removed per user request — only `AES-256-GCM` is now supported ([#0cff426](https://github.com/valeksan/YouTube-Cloude/commit/0cff426), [#5b38369](https://github.com/valeksan/YouTube-Cloude/commit/5b38369))

## [1.1.0] - 2026-08-31

### Added
- **YTV3 format**: 30 FPS, 8×8 blocks, 2 px spacing, 4 grays (2-bit luma) + `RS(255,223)` (32 parity bytes, corrects 16 byte errors/chunk) — `yuv420p`-safe without interlacing ([#582beab](https://github.com/valeksan/YouTube-Cloude/commit/582beab))
- `reedsolo` dependency (`>=1.7.0`) for RS, included in Nuitka builds ([#582beab](https://github.com/valeksan/YouTube-Cloude/commit/582beab))
- **PBKDF2-HMAC-SHA256 + AES-256-GCM** encryption (200 000 iterations, `SALT:NONCE:TAG` header, `MAC check failed` on wrong key) — replaces SHA256 + AES-CBC ([#c011147](https://github.com/valeksan/YouTube-Cloude/commit/c011147))
- **zlib `--compress`** flag for `encode`/`encode-dir` (auto-skipped if would enlarge, `:COMPRESS:zlib` header, transparent decompress on decode) — GUI Qt/Kivy/Tkinter checkboxes ([#2705a34](https://github.com/valeksan/YouTube-Cloude/commit/2705a34))
- Unified GUI service layer `src/youtube_cloude/gui_service.py` (`EncodeSettings`/`DecodeSettings`) — removes ~80% duplication between Qt/Kivy/Tkinter ([#09d978c](https://github.com/valeksan/YouTube-Cloude/commit/09d978c))

### Changed
- CLI `--format` now accepts `ytv1|ytv2|ytv3` (default `ytv1`), GUI defaults to YTV3
- `core.py` `compute_grid` now uses single region for YTV3 (`blocks_per_frame = bpr`), `MAX_FILE_SIZES` 500 MB for YTV3
- `video_io.py` YTV3 uses `yuv420p` `CRF 18` `medium` (was `yuv444p` `CRF 0` for interlace)
- Version bump `1.0.0` → `1.1.0`

### Fixed
- Windows GUI console window on launch (`--windows-console-mode=disable` for Nuitka GUI) ([#03a5937](https://github.com/valeksan/YouTube-Cloude/commit/03a5937))
- Encode progress capped at 66% for small files (guard frames now report progress, reaches 100%) ([#03a5937](https://github.com/valeksan/YouTube-Cloude/commit/03a5937))
- Linux/macOS Nuitka packaging empty `dist/` (discover `.dist` dir by binary name `cli.dist`/`gui_qt_cli.dist`) ([#63612d1](https://github.com/valeksan/YouTube-Cloude/commit/63612d1))
- Desktop packaging: Linux `.AppImage` + `.tar.xz`, macOS `.dmg` (Komi Store `.AppImage`/`.dmg` + Reedsolo include) ([#ab676d7](https://github.com/valeksan/YouTube-Cloude/commit/ab676d7))
- Android build: `main.py` entry point, numeric `android.version` stripping, `pip<26.2` pin, `python3` 3.12.9, local `requests`/`kivy` recipes ([#49e7d96](https://github.com/valeksan/YouTube-Cloude/commit/49e7d96), [#ae18fe1](https://github.com/valeksan/YouTube-Cloude/commit/ae18fe1), [#d431b9e](https://github.com/valeksan/YouTube-Cloude/commit/d431b9e), [#25cf6ea](https://github.com/valeksan/YouTube-Cloude/commit/25cf6ea), [#ce96588](https://github.com/valeksan/YouTube-Cloude/commit/ce96588), [#b7a39d4](https://github.com/valeksan/YouTube-Cloude/commit/b7a39d4))

### Security
- Switched from unauthenticated `AES-CBC` (SHA256 KDF) to authenticated `AES-GCM` with `PBKDF2` (no more malleability, brute-force hardened)

## [1.0.2] - 2026-08-31

- Dry-run validation for new Linux/macOS packaging (discovered `.dist` naming, verified AppImage/dmg)

## [1.0.0] - 2026-08-31

- Initial public release with Nuitka-compiled desktop CLI/GUI (Windows `.exe`, Linux binary, macOS arm64), Kivy Android APK (Buildozer, API 33, arm64), YTV1/YTV2 formats, AES-CBC (SHA256) encryption, CRC32, interlacing, zlib/7z helpers, yt-dlp/Google API uploader, PySide6 Qt GUI + Tkinter legacy + Kivy Android, `test.yml`/`release.yml` CI, `src`-layout and `pyproject.toml`.

[Unreleased]: https://github.com/valeksan/YouTube-Cloude/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/valeksan/YouTube-Cloude/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/valeksan/YouTube-Cloude/releases/tag/v1.1.0
[1.0.2]: https://github.com/valeksan/YouTube-Cloude/releases/tag/v1.0.2
[1.0.0]: https://github.com/valeksan/YouTube-Cloude/releases/tag/v1.0.0
