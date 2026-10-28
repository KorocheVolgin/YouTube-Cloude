#!/usr/bin/env python3
"""Shared constants and utilities for YouTube File Storage.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
GUI concepts from @Maksim4081862.
"""
import os
import zlib
from pathlib import Path
from typing import Optional

# ── Dimensions ──────────────────────────────────────────────────────────────
WIDTH: int = 1920
HEIGHT: int = 1080

# ── YTV1 format (default, backward compatible) ─────────────────────────────
YTV1: dict = {
    'name': 'YTV1',
    'fps': 6,
    'block_height': 16,
    'block_width': 24,
    'spacing': 4,
    'marker_size': 80,
}

# ── YTV2 format (125x denser, from @sosatel30000) ──────────────────────────
YTV2: dict = {
    'name': 'YTV2',
    'fps': 15,
    'block_height': 8,
    'block_width': 8,
    'spacing': 1,
    'marker_size': 16,
}

# ── YTV3 format (RS + grayscale, yuv420p resilient, no interlace) ─────────
# 2 bit/block luma-only palette survives YouTube yuv420p chroma subsampling.
# Single region + Reed-Solomon(255,223) instead of wasteful 3x repetition.
# spacing=2 gives 2px gap — survives 2x2 chroma subsample without bleeding.
YTV3: dict = {
    'name': 'YTV3',
    'fps': 30,
    'block_height': 8,
    'block_width': 8,
    'spacing': 2,
    'marker_size': 16,
}

# ── All known formats ───────────────────────────────────────────────────────
FORMATS: dict[str, dict] = {
    'ytv1': YTV1,
    'ytv2': YTV2,
    'ytv3': YTV3,
}


def get_format(name: str = 'ytv1') -> dict:
    """Return format parameters by name ('ytv1' | 'ytv2')."""
    key = name.lower().strip()
    if key not in FORMATS:
        raise ValueError(f"Unknown format: {name!r}. Choose from: {list(FORMATS)}")
    return FORMATS[key]


def compute_grid(fmt: dict) -> dict:
    """Compute derived grid values from a format dict.

    Returns dict with: name, fps, blocks_x, blocks_y, blocks_per_region,
    blocks_per_frame, marker_size, block_width, block_height, spacing.
    """
    bw = fmt['block_width']
    bh = fmt['block_height']
    sp = fmt['spacing']
    ms = fmt['marker_size']
    bx = (WIDTH - 2 * ms) // (bw + sp)
    by = (HEIGHT - 2 * ms) // (bh + sp)
    bpr = bx * by
    # YTV3 uses single region + RS; YTV1/YTV2 use 3x replication
    bpf = bpr if fmt.get('name') == 'YTV3' else bpr * 3
    return {
        'name': fmt['name'],
        'fps': fmt['fps'],
        'block_width': bw,
        'block_height': bh,
        'spacing': sp,
        'marker_size': ms,
        'blocks_x': bx,
        'blocks_y': by,
        'blocks_per_region': bpr,
        'blocks_per_frame': bpf,
    }


def detect_format(marker_size: int) -> dict:
    """Auto-detect format from marker size observed in the first frame.

    YTV1 markers are 80px, YTV2/YTV3 are 16px (disambiguated by palette).
    """
    for fmt in FORMATS.values():
        if fmt['marker_size'] == marker_size:
            # YTV2 and YTV3 share marker_size 16 — prefer YTV2 for
            # marker-only detection; palette detection in decoder
            # upgrades to YTV3 when grayscale is observed.
            if marker_size == 16:
                return YTV2
            return fmt
    # Fallback: small marker → YTV2, large → YTV1
    return YTV2 if marker_size < 40 else YTV1


def detect_format_by_palette(frame) -> dict:
    """Distinguish YTV2 vs YTV3 by sampling block colours (grayscale vs colour).

    YTV3 uses only luma grays (R≈G≈B), YTV2 uses saturated colours.
    We sample block centres for both grids and look for saturated blocks;
    if any saturated colour is found it is YTV2, otherwise YTV3.
    Sparse data (few blocks) can look all-gray, so we require multiple
    saturated hits to decide YTV2.
    """
    import numpy as np
    # Sample block centres for YTV2 grid (covers YTV3 centres as well with overlap)
    for fmt in (YTV2, YTV3):
        g = compute_grid(fmt)
        ms, bw, bh, sp = g['marker_size'], g['block_width'], g['block_height'], g['spacing']
        bx, by = g['blocks_x'], g['blocks_y']
        saturated = 0
        gray = 0
        examined = 0
        for y_idx in range(0, min(by, 40)):
            for x_idx in range(0, min(bx, 60)):
                cx = ms + x_idx * (bw + sp) + bw // 2
                cy = ms + y_idx * (bh + sp) + bh // 2
                if cy >= frame.shape[0] or cx >= frame.shape[1]:
                    continue
                # average 3x3 centre to reduce compression noise
                region = frame[max(0, cy-1):cy+2, max(0, cx-1):cx+2]
                if region.size == 0:
                    continue
                b, g_, r = region.mean(axis=(0, 1)).astype(int)
                # ignore near-black background (empty blocks) — not informative
                if max(b, g_, r) < 15:
                    continue
                examined += 1
                spread = int(max(b, g_, r) - min(b, g_, r))
                if spread > 40:
                    saturated += 1
                else:
                    gray += 1
                if examined >= 200:
                    break
            if examined >= 200:
                break
        # Decide: need several saturated blocks to confidently say YTV2
        if examined >= 20:
            if saturated >= 5:
                return YTV2
            if gray >= 15 and saturated == 0:
                return YTV3
        # Not enough signal — fall through to try next grid
    return YTV2  # conservative fallback

# ── 16-colour palette (4-bit string -> BGR tuple) ──────────────────────────
COLORS: dict[str, tuple[int, int, int]] = {
    '0000': (255, 0, 0),
    '0001': (0, 255, 0),
    '0010': (0, 0, 255),
    '0011': (255, 255, 0),
    '0100': (255, 0, 255),
    '0101': (0, 255, 255),
    '0110': (255, 128, 0),
    '0111': (128, 0, 255),
    '1000': (0, 128, 128),
    '1001': (128, 128, 0),
    '1010': (128, 0, 128),
    '1011': (0, 128, 0),
    '1100': (128, 0, 0),
    '1101': (0, 0, 128),
    '1110': (192, 192, 192),
    '1111': (255, 255, 255),
}

# ── YTV3 grayscale palette (2-bit string -> BGR tuple, luma-only) ─────────
# Survives YouTube yuv420p chroma subsampling — only Y channel matters.
GRAY_COLORS: dict[str, tuple[int, int, int]] = {
    '00': (0, 0, 0),
    '01': (85, 85, 85),
    '10': (170, 170, 170),
    '11': (255, 255, 255),
}
# Thresholds for fast gray classification (mid-points between levels)
GRAY_THRESHOLDS: tuple[int, int, int] = (42, 127, 212)

# ── End-of-file marker ─────────────────────────────────────────────────────
EOF_MARKER: str = "\u2588" * 64
EOF_BYTES: bytes = EOF_MARKER.encode('utf-8')

# ── Dangerous extensions ───────────────────────────────────────────────────
DANGEROUS_EXTENSIONS: set[str] = {
    '.exe', '.bat', '.sh', '.py', '.js', '.dll', '.so', '.com',
}

# ── Max file size defaults (based on format density) ────────────────────────
# YTV1: 100 MB → ~3.4h video. YTV2: 500 MB → ~48 min video. YTV3: 500 MB.
MAX_FILE_SIZES: dict[str, int] = {
    'ytv1': 100 * 1024 * 1024,   # 100 MB
    'ytv2': 500 * 1024 * 1024,   # 500 MB
    'ytv3': 500 * 1024 * 1024,   # 500 MB (single region + RS overhead ~13%)
}
MAX_FILE_SIZE: int = 100 * 1024 * 1024  # fallback for direct callers


# ── AES-GCM encryption (PBKDF2) ────────────────────────────────────────────
# Uses pycryptodome (pip install pycryptodome)

def _get_aes():
    """Lazy-import AES to allow running without pycryptodome when unencrypted."""
    try:
        from Crypto.Cipher import AES as _AES

        return _AES, None, None
    except ImportError:
        raise ImportError(
            "pycryptodome is required for AES encryption. "
            "Install it: pip install pycryptodome"
        )


def generate_salt() -> bytes:
    """Generate a 16-byte random salt for PBKDF2."""
    return os.urandom(16)


def generate_nonce() -> bytes:
    """Generate a 12-byte random nonce for AES-GCM."""
    return os.urandom(12)


PBKDF2_ITERATIONS: int = 200_000


def derive_key_pbkdf2(key_str: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """Derive a 32-byte key via PBKDF2-HMAC-SHA256."""
    import hashlib

    return hashlib.pbkdf2_hmac('sha256', key_str.encode('utf-8'), salt, iterations, dklen=32)


def encrypt_data_gcm(data: bytes, key: bytes, nonce: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt. Returns (ciphertext, tag). No padding."""
    AES, _, _ = _get_aes()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return ciphertext, tag


def decrypt_data_gcm(ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes) -> bytes:
    """AES-256-GCM decrypt. Raises ValueError on authentication failure."""
    AES, _, _ = _get_aes()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


# ── Bit / byte conversions ─────────────────────────────────────────────────
def data_to_blocks(data: bytes) -> list[str]:
    """Convert raw bytes into a list of 4-bit binary strings."""
    all_bits: list[str] = []
    for byte in data:
        for i in range(7, -1, -1):
            all_bits.append(str((byte >> i) & 1))
    while len(all_bits) % 4 != 0:
        all_bits.append('0')
    return [''.join(all_bits[i:i + 4]) for i in range(0, len(all_bits), 4)]


def blocks_to_bytes(blocks: list[str]) -> bytes:
    """Convert a list of 4-bit strings back to raw bytes."""
    all_bits = ''.join(blocks)
    buf = bytearray()
    for i in range(0, len(all_bits) - 7, 8):
        byte_str = all_bits[i:i + 8]
        if len(byte_str) == 8:
            try:
                buf.append(int(byte_str, 2))
            except ValueError:
                buf.append(0)
    return bytes(buf)


# ── YTV3 2-bit conversions ─────────────────────────────────────────────────
def data_to_blocks_2bit(data: bytes) -> list[str]:
    """Convert bytes to 2-bit block strings (YTV3, 4 blocks per byte)."""
    blocks: list[str] = []
    for byte in data:
        blocks.append(f"{(byte >> 6) & 0x3:02b}")
        blocks.append(f"{(byte >> 4) & 0x3:02b}")
        blocks.append(f"{(byte >> 2) & 0x3:02b}")
        blocks.append(f"{byte & 0x3:02b}")
    return blocks


def blocks_to_bytes_2bit(blocks: list[str]) -> bytes:
    """Convert 2-bit block strings back to bytes (YTV3)."""
    all_bits = ''.join(blocks)
    # pad to multiple of 8
    if len(all_bits) % 8 != 0:
        all_bits = all_bits.ljust(((len(all_bits) // 8) + 1) * 8, '0')
    buf = bytearray()
    for i in range(0, len(all_bits) - 7, 8):
        chunk = all_bits[i:i + 8]
        if len(chunk) == 8:
            try:
                buf.append(int(chunk, 2))
            except ValueError:
                buf.append(0)
    return bytes(buf)


# ── Reed-Solomon helpers (YTV3) ────────────────────────────────────────────
RS_NSYM: int = 32   # parity bytes
RS_K: int = 223     # data bytes per chunk (255-32)
RS_N: int = 255     # total bytes per chunk


def _get_rs_codec():
    """Lazy import reedsolo RSCodec."""
    try:
        from reedsolo import RSCodec  # type: ignore
        return RSCodec(RS_NSYM)
    except ImportError:
        raise ImportError(
            "reedsolo is required for YTV3. Install: pip install reedsolo"
        )


def rs_encode(data: bytes) -> bytes:
    """RS(255,223) encode — splits into 223-byte chunks, appends 32 parity each."""
    rs = _get_rs_codec()
    out = bytearray()
    for i in range(0, len(data), RS_K):
        chunk = data[i:i + RS_K]
        # reedsolo handles short last chunk (pads internally with zeros,
        # but we encode exactly the chunk length)
        out.extend(rs.encode(chunk))
    return bytes(out)


def rs_decode(data: bytes) -> bytes:
    """RS(255,223) decode — corrects up to 16 byte errors per 255-byte chunk."""
    rs = _get_rs_codec()
    out = bytearray()
    for i in range(0, len(data), RS_N):
        chunk = data[i:i + RS_N]
        if not chunk:
            break
        try:
            decoded = rs.decode(chunk)
            # reedsolo returns (message, ecc) or just message depending on version
            if isinstance(decoded, tuple):
                decoded = decoded[0]
            out.extend(bytes(decoded))
        except Exception:
            # Uncorrectable chunk — return raw chunk without parity for best-effort
            # (strip parity bytes, keep data portion)
            out.extend(chunk[:RS_K])
    return bytes(out)


# ── File helpers ───────────────────────────────────────────────────────────
def sanitize_filename(filename: str) -> str:
    """Return a safe basename, stripping dangerous extensions."""
    import re
    name = Path(filename).name
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    parts = name.rsplit('.', 1)
    if len(parts) > 1:
        if f".{parts[1].lower()}" in DANGEROUS_EXTENSIONS:
            name = f"{parts[0]}.bin"
    return name or "file.bin"


def validate_input_file(filepath: str, max_size: int = MAX_FILE_SIZE) -> Path:
    """Validate that *filepath* exists, is a file, and is within *max_size*."""
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not path.is_file():
        raise ValueError(f"Not a file: {filepath}")
    size = path.stat().st_size
    if size > max_size:
        raise ValueError(
            f"File too large: {size} bytes (max {max_size})"
        )
    if size == 0:
        raise ValueError("File is empty")
    return path


def read_key_from_file(key_file: str = 'key.txt') -> Optional[str]:
    """Read an encryption key from a text file, or return *None*."""
    import os
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    print(f"Key loaded from {key_file}")
                    return key
                else:
                    print(f"Warning: {key_file} is empty")
        else:
            print(f"Info: {key_file} not found, encryption disabled")
    except IOError as e:
        print(f"Warning: could not read key file: {e}")
    return None


# ── Compression helpers (zlib, pure-python, no external 7z needed) ──────
def compress_data(data: bytes, level: int = 6) -> bytes:
    """Compress *data* with zlib (level 1-9). Returns compressed bytes."""
    return zlib.compress(data, level)


def decompress_data(data: bytes) -> bytes:
    """Decompress zlib-compressed *data*."""
    return zlib.decompress(data)


# ── CRC32 helpers ──────────────────────────────────────────────────────────
def crc32_hex(data: bytes) -> str:
    """Return CRC32 of *data* as an 8-char lowercase hex string."""
    return format(zlib.crc32(data) & 0xFFFFFFFF, '08x')


def verify_crc32(data: bytes, expected_hex: str) -> bool:
    """Return *True* if CRC32 of *data* matches *expected_hex*."""
    return crc32_hex(data) == expected_hex.lower()


# ── Interlacing (better YouTube compression) ───────────────────────────────
def interlace_frame(frame) -> object:
    """Interlace a frame: alternate rows from top and bottom halves.

    YouTube's H.264 encoder compresses better when adjacent rows are
    less correlated. Interlacing breaks spatial locality → less blocking.
    """
    import numpy as np
    h = frame.shape[0]
    mid = h // 2
    top = frame[:mid]      # rows 0..mid-1
    bot = frame[mid:mid + mid]  # rows mid..2*mid-1 (mirror pad if odd)
    out = np.empty_like(frame)
    out[0::2] = top        # even rows from top half
    out[1::2] = bot        # odd rows from bottom half
    return out


def deinterlace_frame(frame) -> object:
    """Reverse the interlace applied by ``interlace_frame``."""
    import numpy as np
    h = frame.shape[0]
    mid = h // 2
    top = frame[0::2][:mid]  # even rows → top half
    bot = frame[1::2][:mid]  # odd rows → bottom half
    out = np.empty_like(frame)
    out[:mid] = top
    out[mid:mid + len(bot)] = bot
    return out
