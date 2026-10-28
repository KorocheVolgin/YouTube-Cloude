#!/usr/bin/env python3
"""YouTube video encoder — encodes arbitrary files into colour-block frames.

No OpenCV dependency — uses numpy, Pillow, and ffmpeg subprocess.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
"""
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable

import numpy as np

from .core import (
    WIDTH, HEIGHT, COLORS, GRAY_COLORS, EOF_MARKER, EOF_BYTES,
    get_format, compute_grid, MAX_FILE_SIZES,
    data_to_blocks, data_to_blocks_2bit, rs_encode,
    sanitize_filename, validate_input_file,
    crc32_hex, interlace_frame,
)
from .video_io import save_frame_png, png_sequence_to_mp4


class YouTubeEncoder:
    """Encode a file into a video of colour-block frames."""

    def __init__(self, key: Optional[str] = None,
                 format_name: str = 'ytv1',
                 interlace: bool = False,
                 max_file_size: Optional[int] = None,
                 compress: bool = False) -> None:
        self.width = WIDTH
        self.height = HEIGHT
        self.max_file_size = max_file_size or MAX_FILE_SIZES.get(format_name, 100 * 1024 * 1024)
        self.interlace = interlace
        self.compress = compress

        # Format-specific parameters
        fmt = get_format(format_name)
        g = compute_grid(fmt)
        self.fps = g['fps']
        self.block_height = g['block_height']
        self.block_width = g['block_width']
        self.spacing = g['spacing']
        self.marker_size = g['marker_size']
        self.blocks_x = g['blocks_x']
        self.blocks_y = g['blocks_y']
        self.blocks_per_region = g['blocks_per_region']
        self.blocks_per_frame = g['blocks_per_frame']
        self.format_name = g['name']

        if key and str(key).strip():
            self._passphrase: Optional[str] = str(key)
            self.use_encryption = True
        else:
            self._passphrase = None
            self.use_encryption = False

        self.is_ytv3 = g['name'] == 'YTV3'
        if self.is_ytv3:
            if self.interlace:
                print("  Note: interlace is ignored for YTV3 (luma-only, yuv420p safe)")
                self.interlace = False
            self.colors = GRAY_COLORS
        else:
            self.colors = COLORS
        self.eof_marker = EOF_MARKER
        self.eof_bytes = EOF_BYTES

        print("=" * 60)
        print(f"YouTube ENCODER ({self.format_name} | {self.fps} FPS)")
        print("=" * 60)
        print(f"  Grid: {self.blocks_x} x {self.blocks_y} blocks per region")
        if self.is_ytv3:
            print(f"  Palette: Grayscale 2-bit (yuv420p resilient) + RS(255,223)")
        print(f"  FPS:  {self.fps}")
        print(f"  Encryption: {'AES-256-GCM PBKDF2' if self.use_encryption else 'OFF'}")
        print(f"  Interlace:  {'ON' if self.interlace else 'OFF'}")
        print(f"  Compress:   {'zlib' if self.compress else 'OFF'}")
        print(f"  Max file:   {self.max_file_size / 1024 / 1024:.0f} MB")

        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of ongoing encode."""
        self._cancelled = True

    # ── Drawing helpers (pure numpy) ───────────────────────────────────
    def draw_markers(self, frame: np.ndarray) -> np.ndarray:
        """Draw alignment markers in each corner (white fill, black border)."""
        ms = self.marker_size
        for x, y in [
            (0, 0),
            (self.width - ms, 0),
            (0, self.height - ms),
            (self.width - ms, self.height - ms),
        ]:
            x2 = x + ms
            y2 = y + ms
            # White fill
            frame[y:y2, x:x2] = (255, 255, 255)
            # Black border (2px)
            frame[y:y2, x:min(x + 2, x2)] = (0, 0, 0)
            frame[y:y2, max(x2 - 2, x):x2] = (0, 0, 0)
            frame[y:min(y + 2, y2), x:x2] = (0, 0, 0)
            frame[max(y2 - 2, y):y2, x:x2] = (0, 0, 0)
        return frame

    def draw_block(
        self,
        frame: np.ndarray,
        x: int,
        y: int,
        color: tuple,
    ) -> bool:
        """Draw a single colour block; return *True* if within bounds."""
        x1 = self.marker_size + x * (self.block_width + self.spacing)
        y1 = self.marker_size + y * (self.block_height + self.spacing)
        x2 = x1 + self.block_width
        y2 = y1 + self.block_height

        if x2 > self.width - self.marker_size or y2 > self.height - self.marker_size:
            return False

        # Fill block with colour
        frame[y1:y2, x1:x2] = color
        # 1px black border
        frame[y1:min(y1 + 1, y2), x1:x2] = (0, 0, 0)
        frame[max(y2 - 1, y1):y2, x1:x2] = (0, 0, 0)
        frame[y1:y2, x1:min(x1 + 1, x2)] = (0, 0, 0)
        frame[y1:y2, max(x2 - 1, x1):x2] = (0, 0, 0)
        return True

    def bits_to_color(self, bits: str) -> tuple:
        """Map a bit string to its palette colour (4-bit for YTV1/2, 2-bit for YTV3)."""
        if self.is_ytv3:
            while len(bits) < 2:
                bits = '0' + bits
            return self.colors.get(bits, (255, 0, 0))
        while len(bits) < 4:
            bits = '0' + bits
        return self.colors.get(bits, (255, 0, 0))

    # ── Main encode routine ─────────────────────────────────────────────
    def encode(
        self,
        input_file: str,
        output_file: str = "output.mp4",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Encode *input_file* into *output_file* (MP4)."""

        print("\n  ENCODE FILE")
        print("-" * 40)

        try:
            input_path = validate_input_file(input_file, self.max_file_size)
        except (FileNotFoundError, ValueError) as e:
            print(f"  Error: {e}")
            return False

        original_filename = sanitize_filename(input_path.name)

        print(f"  File:   {original_filename}")
        print(f"  Size:   {input_path.stat().st_size} bytes")

        try:
            with open(input_path, 'rb') as f:
                data = f.read()
        except IOError as e:
            print(f"  Read error: {e}")
            return False

        orig_size = len(data)
        # ── Compression (zlib) before encryption ──────────────────────────
        was_compressed = False
        if self.compress:
            from .core import compress_data
            compressed = compress_data(data)
            if len(compressed) < len(data):
                data = compressed
                was_compressed = True
                print(f"  Compressed: {orig_size} -> {len(data)} bytes ({len(data)/orig_size*100:.1f}%)")
            else:
                print(f"  Compress skipped (would enlarge: {len(compressed)} >= {orig_size})")

        if self.use_encryption:
            # New: PBKDF2 + AES-GCM (authenticated). Legacy CBC kept for decoding.
            from .core import (
                generate_salt, generate_nonce, derive_key_pbkdf2,
                encrypt_data_gcm, PBKDF2_ITERATIONS,
            )
            passphrase = getattr(self, '_passphrase', None) or ''
            salt = generate_salt()
            nonce = generate_nonce()
            pbkdf2_key = derive_key_pbkdf2(passphrase, salt, PBKDF2_ITERATIONS)
            ciphertext, tag = encrypt_data_gcm(data, pbkdf2_key, nonce)
            encrypted_data = ciphertext
            salt_hex = salt.hex()
            nonce_hex = nonce.hex()
            tag_hex = tag.hex()
            iv_hex = None  # not used for GCM
            print(f"  Data encrypted (AES-256-GCM, PBKDF2 {PBKDF2_ITERATIONS} iters)")
        else:
            encrypted_data = data
            salt_hex = nonce_hex = tag_hex = None
            iv_hex = None

        # CRC32 of encrypted data for integrity check
        data_crc = crc32_hex(encrypted_data)

        # Header — include COMPRESS:zlib when payload was compressed
        compress_field = ":COMPRESS:zlib" if was_compressed else ""
        if self.use_encryption:
            header = (
                f"FORMAT:{self.format_name}:FILE:{original_filename}:"
                f"SIZE:{orig_size}{compress_field}:ENC_SIZE:{len(encrypted_data)}:"
                f"SALT:{salt_hex}:NONCE:{nonce_hex}:TAG:{tag_hex}:CRC:{data_crc}|"
            )
        else:
            header = f"FORMAT:{self.format_name}:FILE:{original_filename}:SIZE:{orig_size}{compress_field}:CRC:{data_crc}|"
            if was_compressed:
                # need ENC_SIZE for symmetry? no, SIZE is orig, CRC is of compressed
                # for plain compressed, header already has COMPRESS
                pass
        try:
            header_bytes = header.encode('utf-8')
        except UnicodeEncodeError:
            print("  Invalid characters in filename")
            return False
        print(f"  Header: {header}")

        if self.is_ytv3:
            # YTV3: RS-encode the whole payload (header+data+EOF), then 2-bit blocks
            raw_payload = header_bytes + encrypted_data + self.eof_bytes
            rs_payload = rs_encode(raw_payload)
            all_blocks = data_to_blocks_2bit(rs_payload)
            print(f"  RS payload: {len(raw_payload)} -> {len(rs_payload)} bytes (+{len(rs_payload)-len(raw_payload)} parity)")
            header_blocks = []  # not used separately for YTV3
            data_blocks = []
            eof_blocks = []
        else:
            header_blocks = data_to_blocks(header_bytes)
            data_blocks = data_to_blocks(encrypted_data)
            eof_blocks = data_to_blocks(self.eof_bytes)
            all_blocks = header_blocks + data_blocks + eof_blocks

        print(f"  Total blocks: {len(all_blocks)}")
        print(f"  EOF marker:   {len(eof_blocks)} blocks")

        frames_needed = math.ceil(len(all_blocks) / self.blocks_per_region) + 5
        print(f"  Frames needed: {frames_needed}")
        print(f"  Duration:      {frames_needed / self.fps:.1f} sec")

        temp_dir = tempfile.mkdtemp(prefix="youtube_encoder_")
        print(f"  Temp dir: {temp_dir}")

        try:
            guard_start = frames_needed - 5
            for frame_num in range(frames_needed):
                if self._cancelled:
                    print("\n  Cancelled by user")
                    return False
                if progress_callback:
                    progress_callback(frame_num + 1, frames_needed)

                guard = frame_num >= guard_start
                if guard:
                    print(f"\n  Creating guard frame {frame_num - guard_start + 1}/5")
                else:
                    print(f"\n  Frame {frame_num + 1}/{frames_needed}")

                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                frame = self.draw_markers(frame)

                if guard:
                    for y in range(self.blocks_y * 2):
                        for x in range(self.blocks_x * 2):
                            self.draw_block(frame, x, y, (255, 0, 0))
                else:
                    start_idx = frame_num * self.blocks_per_region
                    end_idx = min(start_idx + self.blocks_per_region, len(all_blocks))
                    frame_blocks = all_blocks[start_idx:end_idx]

                    if self.is_ytv3:
                        # YTV3: single region, no replication
                        for idx, bits in enumerate(frame_blocks):
                            y = idx // self.blocks_x
                            x = idx % self.blocks_x
                            if y < self.blocks_y:
                                color = self.bits_to_color(bits)
                                self.draw_block(frame, x, y, color)
                    else:
                        # Primary region
                        for idx, bits in enumerate(frame_blocks):
                            y = idx // self.blocks_x
                            x = idx % self.blocks_x
                            if y < self.blocks_y:
                                color = self.bits_to_color(bits)
                                self.draw_block(frame, x, y, color)

                        # Reserve 1
                        for idx, bits in enumerate(frame_blocks):
                            y = idx // self.blocks_x
                            x = idx % self.blocks_x + self.blocks_x
                            if x < self.blocks_x * 2 and y < self.blocks_y:
                                color = self.bits_to_color(bits)
                                self.draw_block(frame, x, y, color)

                        # Reserve 2
                        for idx, bits in enumerate(frame_blocks):
                            y = idx // self.blocks_x + self.blocks_y
                            x = idx % self.blocks_x
                            if x < self.blocks_x and y < self.blocks_y * 2:
                                color = self.bits_to_color(bits)
                                self.draw_block(frame, x, y, color)

                frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
                if self.interlace:
                    frame = interlace_frame(frame)
                save_frame_png(frame, frame_file)

            if self._cancelled:
                print("\n  Cancelled before FFmpeg")
                return False
            # Convert to MP4
            print("\n  Converting to MP4...")
            if self.is_ytv3:
                pix_fmt = 'yuv420p'
                crf = '18'
                preset = 'medium'
            elif self.interlace:
                pix_fmt = 'yuv444p'
                crf = '0'
                preset = 'ultrafast'
            else:
                pix_fmt = 'yuv420p'
                crf = '23'
                preset = 'slow'
            print(f"  FFmpeg: CRF {crf}, preset {preset}, pix_fmt {pix_fmt}")

            input_pattern = os.path.join(temp_dir, 'frame_%05d.png')
            extra_args = []
            if self.interlace:
                extra_args.extend(['-profile:v', 'high444', '-level', '4.1'])

            ok = png_sequence_to_mp4(
                input_pattern=input_pattern,
                output_file=output_file,
                fps=self.fps,
                pix_fmt=pix_fmt,
                crf=crf,
                preset=preset,
                extra_args=extra_args if extra_args else None,
            )
            if ok:
                print("  FFmpeg conversion OK")
            else:
                print("  FFmpeg conversion FAILED")
                return False

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("  Temp files cleaned up")

        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"\n  Video saved: {output_file}")
            print(f"  Size:        {size} bytes ({size / 1024 / 1024:.2f} MB)")
            print(f"  Frames:      {frames_needed}")
            print(f"  Duration:    {frames_needed / self.fps:.1f} sec")
            return True
        return False
