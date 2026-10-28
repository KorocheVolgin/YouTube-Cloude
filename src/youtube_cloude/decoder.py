#!/usr/bin/env python3
"""YouTube video decoder — extracts files from colour-block frame videos.

No OpenCV dependency — uses numpy, Pillow, and ffmpeg subprocess.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
"""
import os
import re
import time
from pathlib import Path
from typing import Optional, Callable

import numpy as np

from .core import (
    WIDTH, HEIGHT, COLORS, GRAY_COLORS, GRAY_THRESHOLDS, EOF_BYTES,
    get_format, compute_grid, detect_format, detect_format_by_palette,
    blocks_to_bytes, data_to_blocks, blocks_to_bytes_2bit, rs_decode,
    verify_crc32, deinterlace_frame,
)
from .video_io import probe_video, read_frames, resize_frame, bgr_to_gray


class YouTubeDecoder:
    """Decode a colour-block video back into the original file."""

    def __init__(self, key: Optional[str] = None,
                 format_name: Optional[str] = None,
                 interlace: bool = False) -> None:
        self.width = WIDTH
        self.height = HEIGHT
        self.format_name = format_name  # None = auto-detect from video
        self._format_configured = False
        self.interlace = interlace

        if key and str(key).strip():
            self._passphrase: Optional[str] = str(key)
        else:
            self._passphrase = None

        self.is_ytv3 = (format_name or '').lower() == 'ytv3'
        if self.is_ytv3:
            self.colors = GRAY_COLORS
        else:
            self.colors = COLORS
        self.color_values = np.array(list(self.colors.values()), dtype=np.int32)
        self.color_keys = list(self.colors.keys())
        self.color_cache: dict[tuple, str] = {}
        self.cache_hits = 0
        self.cache_misses = 0

        # If format known at init time, configure grid now
        if format_name:
            self._configure_format(get_format(format_name))

        print("=" * 60)
        if format_name:
            print(f"YouTube DECODER ({self.format_name})")
        else:
            print("YouTube DECODER (auto-detect)")
        print("=" * 60)
        if self._format_configured:
            print(f"  Grid:   {self.blocks_x} x {self.blocks_y} blocks")
        print(f"  Key:    {'YES' if self._passphrase else 'NO'}")

        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of ongoing decode."""
        self._cancelled = True

    def _configure_format(self, fmt: dict) -> None:
        """Set grid parameters from a format dict."""
        g = compute_grid(fmt)
        self.format_name = g['name']
        self.is_ytv3 = g['name'] == 'YTV3'
        self.colors = GRAY_COLORS if self.is_ytv3 else COLORS
        self.color_values = np.array(list(self.colors.values()), dtype=np.int32)
        self.color_keys = list(self.colors.keys())
        self.color_cache = {}
        self.block_height = g['block_height']
        self.block_width = g['block_width']
        self.spacing = g['spacing']
        self.marker_size = g['marker_size']
        self.blocks_x = g['blocks_x']
        self.blocks_y = g['blocks_y']
        self.blocks_per_region = g['blocks_per_region']
        self._precompute_coordinates()
        self._format_configured = True

    # ── Coordinate pre-computation ──────────────────────────────────────
    def _detect_marker_size(self, frame: np.ndarray) -> int:
        """Detect marker size from the top-left corner of the first frame.

        Scans the top-left corner for the white marker square.
        Returns the closest known marker size (80 for YTV1, 16 for YTV2).
        """
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = resize_frame(frame, self.width, self.height)
        gray = bgr_to_gray(frame)

        # Scan along multiple rows to find where the white marker ends.
        scores = []
        for cy in [20, 30, 40, 50, 60]:
            for x in range(5, min(200, self.width)):
                if gray[cy, x] < 128:
                    scores.append(x)
                    break

        if not scores:
            # Fallback: scan column-wise
            for cx in [20, 30, 40, 50, 60]:
                for y in range(5, min(200, self.height)):
                    if gray[y, cx] < 128:
                        scores.append(y)
                        break

        if not scores:
            return 80  # ultimate fallback

        # Use the most common detection value
        from collections import Counter
        counter = Counter(scores)
        raw_size = counter.most_common(1)[0][0]

        # Snap to closest known marker size
        known = [16, 80]
        return min(known, key=lambda k: abs(k - raw_size))

    def _precompute_coordinates(self) -> None:
        """Precompute centre pixel coordinates for every block."""
        self.block_coords: list[tuple[int, int]] = []
        for idx in range(self.blocks_per_region):
            y = idx // self.blocks_x
            x = idx % self.blocks_x
            if y < self.blocks_y:
                cx = (
                    self.marker_size
                    + x * (self.block_width + self.spacing)
                    + self.block_width // 2
                )
                cy = (
                    self.marker_size
                    + y * (self.block_height + self.spacing)
                    + self.block_height // 2
                )
                self.block_coords.append((cx, cy))

    # ── Fast colour lookup ──────────────────────────────────────────────
    def color_to_bits_fast(self, color: np.ndarray) -> str:
        """Map a BGR colour to its bit string (4-bit YTV1/2, 2-bit YTV3)."""
        color_key = (int(color[0]), int(color[1]), int(color[2]))

        if color_key in self.color_cache:
            self.cache_hits += 1
            return self.color_cache[color_key]

        self.cache_misses += 1

        if self.is_ytv3:
            # Luma-only: average channels (they are equal for gray) or use mean
            gray = int((int(color[0]) + int(color[1]) + int(color[2])) / 3)
            t0, t1, t2 = GRAY_THRESHOLDS
            if gray < t0:
                result = '00'
            elif gray < t1:
                result = '01'
            elif gray < t2:
                result = '10'
            else:
                result = '11'
            self.color_cache[color_key] = result
            return result

        # Quick path for dominant blue (YTV1/2)
        if color[0] > 200 and color[1] < 50 and color[2] < 50:
            self.color_cache[color_key] = '0000'
            return '0000'

        color_arr = np.array([color[0], color[1], color[2]], dtype=np.int32)
        distances = np.sum((self.color_values - color_arr) ** 2, axis=1)
        best_idx = int(np.argmin(distances))
        result = self.color_keys[best_idx]
        self.color_cache[color_key] = result
        return result

    # ── Frame decoding ──────────────────────────────────────────────────
    def decode_frame_fast(self, frame: np.ndarray) -> list[str]:
        """Decode one frame into 4-bit block strings (region-sampled)."""
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = resize_frame(frame, self.width, self.height)
        if self.interlace:
            frame = deinterlace_frame(frame)

        blocks: list[str] = []
        h, w = frame.shape[:2]

        for cx, cy in self.block_coords:
            if cx < w and cy < h:
                x1, y1 = max(0, cx - 2), max(0, cy - 2)
                x2, y2 = min(w, cx + 3), min(h, cy + 3)
                region = frame[y1:y2, x1:x2]
                avg_color = region.mean(axis=(0, 1))
                bits = self.color_to_bits_fast(avg_color)
                blocks.append(bits)
            else:
                blocks.append('0000')

        return blocks

    # ── EOF detection ───────────────────────────────────────────────────
    @staticmethod
    def find_eof_marker(data: bytes) -> int:
        """Return the byte offset of the EOF marker, or -1 if absent."""
        eof_bytes = EOF_BYTES
        for i in range(len(data) - len(eof_bytes) + 1):
            if data[i:i + len(eof_bytes)] == eof_bytes:
                return i
        return -1

    # ── Main decode routine ─────────────────────────────────────────────
    def decode(
        self,
        video_file: str,
        output_dir: str = '.',
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Decode *video_file* and write recovered file(s) into *output_dir*."""

        print("\n  DECODE VIDEO")
        print("-" * 40)

        if not Path(video_file).exists():
            print(f"  Error: file not found: {video_file}")
            return False

        # Probe video metadata
        try:
            meta = probe_video(video_file)
        except (FileNotFoundError, ValueError) as e:
            print(f"  Error: {e}")
            return False

        total_frames = meta['total_frames']
        fps = meta['fps']
        width = meta['width']
        height = meta['height']

        print(f"  Frames:  {total_frames}")
        print(f"  FPS:     {fps}")
        print(f"  Size:    {width}x{height}")

        self.cache_hits = 0
        self.cache_misses = 0
        start_time = time.perf_counter()

        # If format not yet configured, detect from first frame's marker
        if not self._format_configured:
            try:
                # Read just the first frame
                first_gen = read_frames(video_file, start_frame=0, max_frames=1)
                first_frame = None
                for _, f in first_gen:
                    first_frame = f
                    break

                if first_frame is not None:
                    # Deinterlace first so marker detection sees clean markers
                    if self.interlace:
                        first_frame = deinterlace_frame(first_frame)
                    detected_ms = self._detect_marker_size(first_frame)
                    print(f"  Detected marker size: {detected_ms}px")
                    self._configure_format(detect_format(detected_ms))
                    # YTV2 and YTV3 share marker_size 16 — disambiguate by palette
                    if detected_ms == 16:
                        try:
                            pal_fmt = detect_format_by_palette(first_frame)
                            if pal_fmt['name'] == 'YTV3':
                                self._configure_format(pal_fmt)
                                print(f"  Palette suggests YTV3 (grayscale)")
                        except Exception:
                            pass
                    print(f"  Auto-detected format: {self.format_name}")
                    print(f"  Grid: {self.blocks_x} x {self.blocks_y} blocks")
                else:
                    # Can't read first frame → default to YTV1
                    self._configure_format(get_format('ytv1'))
                    print("  Warning: cannot read first frame, defaulting to YTV1")
            except Exception as e:
                self._configure_format(get_format('ytv1'))
                print(f"  Warning: format detection failed ({e}), defaulting to YTV1")

        all_blocks: list[str] = []
        frames_processed = 0

        for frame_num, frame in read_frames(video_file):
            if self._cancelled:
                print("\n  Cancelled by user")
                return False
            if progress_callback:
                progress_callback(frame_num + 1, total_frames)

            frames_processed += 1

            if frame_num % 100 == 0:
                elapsed = time.perf_counter() - start_time
                speed = frames_processed / elapsed if elapsed > 0 else 0
                total_cache = self.cache_hits + self.cache_misses
                cache_ratio = (
                    (self.cache_hits / total_cache * 100) if total_cache > 0 else 0
                )
                print(
                    f"  Progress: {frame_num}/{total_frames} | "
                    f"Speed: {speed:.1f} fps | "
                    f"Cache: {cache_ratio:.1f}%"
                )

            frame_blocks = self.decode_frame_fast(frame)
            all_blocks.extend(frame_blocks)

        elapsed = time.perf_counter() - start_time
        print(f"\n  Stats: {len(all_blocks)} blocks in {elapsed:.1f}s")
        total_cache = self.cache_hits + self.cache_misses
        print(
            f"  Cache: {self.cache_hits} hits, {self.cache_misses} misses"
        )
        print(f"  Frames processed: {frames_processed}")

        if self.is_ytv3:
            raw_rs = blocks_to_bytes_2bit(all_blocks)
            print(f"  Raw RS bytes: {len(raw_rs)} (2-bit blocks)")
            bytes_data = rs_decode(raw_rs)
            print(f"  RS decoded: {len(bytes_data)} bytes")
        else:
            bytes_data = blocks_to_bytes(all_blocks)
        print(f"  Bytes recovered: {len(bytes_data)}")

        eof_pos = self.find_eof_marker(bytes_data)
        if eof_pos > 0:
            bytes_data = bytes_data[:eof_pos]
            print(f"  EOF marker found at position {eof_pos}")
            print(f"  Bytes after trim: {len(bytes_data)}")
        else:
            print("  Warning: EOF marker not found")

        # Parse header — GCM only (legacy CBC removed)
        #   GCM:      FORMAT:..:FILE:n:SIZE:123:ENC_SIZE:456:SALT:..:NONCE:..:TAG:..:CRC:abcd|
        #   CRC:      FORMAT:..:FILE:n:SIZE:123:CRC:abcd|
        #   Plain:    FORMAT:..:FILE:n:SIZE:123|
        data_str = bytes_data[:2000].decode('utf-8', errors='ignore')
        if 'FORMAT:' not in data_str:
            data_str = bytes_data[:2000].decode('latin-1', errors='ignore')

        # Try patterns from most specific to least specific
        patterns = [
            # GCM compressed — PBKDF2 + AES-GCM with :COMPRESS:zlib
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+):COMPRESS:([^:]+):ENC_SIZE:(\d+):SALT:([0-9a-fA-F]{32}):NONCE:([0-9a-fA-F]{24}):TAG:([0-9a-fA-F]{32}):CRC:([0-9a-fA-F]{8})\|',
             'gcm_compress'),
            # GCM — PBKDF2 + AES-GCM
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+):ENC_SIZE:(\d+):SALT:([0-9a-fA-F]{32}):NONCE:([0-9a-fA-F]{24}):TAG:([0-9a-fA-F]{32}):CRC:([0-9a-fA-F]{8})\|',
             'gcm'),
            # CRC only with COMPRESS
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+):COMPRESS:([^:]+):CRC:([0-9a-fA-F]{8})\|',
             'crc_compress'),
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+):CRC:([0-9a-fA-F]{8})\|',
             'crc'),
            # Plain with COMPRESS
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+):COMPRESS:([^:]+)\|',
             'plain_compress'),
            (r'FORMAT:([^:]+):FILE:([^:]+):SIZE:(\d+)\|',
             'plain'),
        ]

        expected_crc: Optional[str] = None
        salt_hex: Optional[str] = None
        nonce_hex: Optional[str] = None
        tag_hex: Optional[str] = None
        enc_size: Optional[int] = None
        header_format = None
        filename = None
        filesize = None
        header_str = None
        matched_type = None

        compress_algo: Optional[str] = None
        for pat, htype in patterns:
            match = re.search(pat, data_str)
            if match:
                matched_type = htype
                header_str = match.group(0)
                if htype == 'gcm_compress':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                    compress_algo = match.group(4)
                    enc_size = int(match.group(5))
                    salt_hex = match.group(6)
                    nonce_hex = match.group(7)
                    tag_hex = match.group(8)
                    expected_crc = match.group(9).lower()
                elif htype == 'gcm':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                    enc_size = int(match.group(4))
                    salt_hex = match.group(5)
                    nonce_hex = match.group(6)
                    tag_hex = match.group(7)
                    expected_crc = match.group(8).lower()
                elif htype == 'crc_compress':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                    compress_algo = match.group(4)
                    expected_crc = match.group(5).lower()
                elif htype == 'crc':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                    expected_crc = match.group(4).lower()
                elif htype == 'plain_compress':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                    compress_algo = match.group(4)
                elif htype == 'plain':
                    header_format = match.group(1)
                    filename = match.group(2)
                    filesize = int(match.group(3))
                break

        if not match:
            print("  Error: header not found")
            output_path = os.path.join(output_dir, "decoded_data.bin")
            with open(output_path, 'wb') as f:
                f.write(bytes_data)
            print(f"\n  Raw data saved: {output_path}")
            return False

        # Auto-configure format
        if header_format and not self._format_configured:
            try:
                self._configure_format(get_format(header_format))
                print(f"  Auto-detected format: {self.format_name}")
            except ValueError:
                print(f"  Warning: unknown format '{header_format}', using defaults")
        elif not self._format_configured:
            self._configure_format(get_format('ytv1'))
            print("  Auto-detected format: YTV1 (legacy header)")

        print(f"\n  Header found: {filename}, size: {filesize} bytes")
        print(f"  Header type:  {matched_type}")
        if compress_algo:
            print(f"  Compress:     {compress_algo}")
        if salt_hex:
            print(f"  SALT:         {salt_hex}")
            print(f"  NONCE:        {nonce_hex}")
            print(f"  TAG:          {tag_hex}")
        if expected_crc:
            print(f"  CRC32:        {expected_crc}")

        # header bytes — try utf-8 first (new), fallback latin-1 (old)
        try:
            header_bytes_enc = header_str.encode('utf-8')
            header_pos = bytes_data.find(header_bytes_enc)
            if header_pos < 0:
                header_bytes_enc = header_str.encode('latin-1')
                header_pos = bytes_data.find(header_bytes_enc)
        except Exception:
            header_bytes_enc = header_str.encode('latin-1', errors='ignore')
            header_pos = bytes_data.find(header_bytes_enc)

        if header_pos >= 0:
            # Use enc_size if available, otherwise use filesize
            data_len = enc_size if enc_size else filesize
            encrypted_data = bytes_data[
                header_pos + len(header_bytes_enc):
                header_pos + len(header_bytes_enc) + data_len
            ]

            if salt_hex and nonce_hex and tag_hex:
                # AES-256-GCM + PBKDF2
                if self._passphrase:
                    from .core import derive_key_pbkdf2, decrypt_data_gcm, PBKDF2_ITERATIONS
                    try:
                        salt = bytes.fromhex(salt_hex)
                        nonce = bytes.fromhex(nonce_hex)
                        tag = bytes.fromhex(tag_hex)
                        gcm_key = derive_key_pbkdf2(self._passphrase, salt, PBKDF2_ITERATIONS)
                        file_data = decrypt_data_gcm(encrypted_data, gcm_key, nonce, tag)
                        print("  Data decrypted (AES-256-GCM, PBKDF2)")
                    except Exception as e:
                        print(f"  GCM decryption failed: {e}")
                        print("  Saving raw data instead...")
                        file_data = encrypted_data
                else:
                    print("  Warning: GCM encrypted data but no key provided")
                    file_data = encrypted_data
            else:
                file_data = encrypted_data
                if salt_hex:
                    print("  Warning: encrypted data but no key provided")
                else:
                    print("  Data not encrypted")

            # ── Decompress if header indicated compression ──────────────
            if compress_algo and file_data:
                if compress_algo.lower() == 'zlib':
                    from .core import decompress_data
                    try:
                        file_data = decompress_data(file_data)
                        print(f"  Decompressed (zlib): {len(encrypted_data)} -> {len(file_data)} bytes")
                    except Exception as e:
                        print(f"  Decompression failed: {e}")
                else:
                    print(f"  Warning: unknown compress algo '{compress_algo}'")

            output_path = os.path.join(output_dir, filename)
            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(output_path):
                output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
                counter += 1

            with open(output_path, 'wb') as f:
                f.write(file_data)

            print(f"\n  File restored: {output_path}")
            print(f"  Size: {len(file_data)} bytes")

            if len(file_data) == filesize:
                print("  Size matches original")
            else:
                print(f"  Size mismatch: {len(file_data)} != {filesize}")

            if expected_crc:
                if verify_crc32(encrypted_data, expected_crc):
                    print("  CRC32 verified OK")
                else:
                    print(f"  WARNING: CRC32 MISMATCH — data may be corrupted!")

            return True

        # Fallback: save raw bytes
        output_path = os.path.join(output_dir, "decoded_data.bin")
        with open(output_path, 'wb') as f:
            f.write(bytes_data)
        print(f"\n  Raw data saved: {output_path}")
        return False
