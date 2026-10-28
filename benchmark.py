#!/usr/bin/env python3
"""Benchmark: all format/interlace/encryption combinations."""
import os
import sys
import time
import hashlib
import subprocess
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from youtube_cloude.core import crc32_hex

def _find_binary() -> list[str]:
    """Return command to invoke encoder: dist binary if exists, else python -m."""
    candidates = []
    base = os.path.join(os.path.dirname(__file__), 'dist')
    if sys.platform.startswith('win'):
        candidates.append(os.path.join(base, 'youtube-cloude.exe'))
    candidates.append(os.path.join(base, 'youtube-cloude'))
    for p in candidates:
        if os.path.exists(p):
            return [p]
    # fallback: python module (uses .venv / installed package)
    return [sys.executable, '-m', 'youtube_cloude']

BINARY = _find_binary()
# Cross-platform temp handling; INPUT will be generated if missing
DEFAULT_INPUT = os.path.join(os.path.dirname(__file__), 'benchmark_input.png')
WORKDIR = os.path.join(os.path.dirname(__file__), '.benchmark_run')
KEY = 'bench-test-key'

VARIANTS = [
    # (format, interlace, compress, encryption, label)
    ('ytv1', False, False, False, 'YTV1'),
    ('ytv1', False, False, True,  'YTV1 + AES'),
    ('ytv1', True,  False, False, 'YTV1 + interlace'),
    ('ytv1', True,  False, True,  'YTV1 + interlace + AES'),
    ('ytv2', False, False, False, 'YTV2'),
    ('ytv2', False, False, True,  'YTV2 + AES'),
    ('ytv2', True,  False, False, 'YTV2 + interlace'),
    ('ytv2', True,  False, True,  'YTV2 + interlace + AES'),
    ('ytv3', False, False, False, 'YTV3'),
    ('ytv3', False, False, True,  'YTV3 + AES'),
    ('ytv3', False, True,  False, 'YTV3 + compress'),
    ('ytv3', False, True,  True,  'YTV3 + compress + AES'),
]


def run(cmd: list[str], timeout: int = 300) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def get_size(path: str) -> int:
    return os.path.getsize(path) if os.path.exists(path) else 0


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def ensure_input(path: str = DEFAULT_INPUT) -> str:
    """Generate a ~513 KB PNG (800x600 geometric + noise) if *path* missing."""
    if os.path.exists(path):
        return path
    try:
        from PIL import Image, ImageDraw
        import random
        random.seed(42)
        img = Image.new('RGB', (800, 600), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        # geometric shapes
        for _ in range(120):
            x0, y0 = random.randint(0, 700), random.randint(0, 500)
            x1, y1 = x0 + random.randint(20, 120), y0 + random.randint(20, 120)
            fill = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            if random.random() < 0.5:
                draw.rectangle([x0, y0, x1, y1], fill=fill, outline=(0,0,0))
            else:
                draw.ellipse([x0, y0, x1, y1], fill=fill, outline=(0,0,0))
        # noise pixels
        pix = img.load()
        for _ in range(80000):
            pix[random.randint(0,799), random.randint(0,599)] = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
        img.save(path, 'PNG')
        # pad to ~513 KB if smaller (deterministic)
        size = os.path.getsize(path)
        target = 513 * 1024
        if size < target:
            with open(path, 'ab') as f:
                f.write(os.urandom(target - size))
        return path
    except Exception as e:
        # fallback tiny file
        with open(path, 'wb') as f:
            f.write(os.urandom(513*1024))
        return path

def main():
    inp = ensure_input()
    os.makedirs(WORKDIR, exist_ok=True)

    orig_md5 = md5(inp)
    orig_size = get_size(inp)
    orig_crc = crc32_hex(open(inp, 'rb').read())

    results = []

    import platform
    try:
        import psutil
        mem_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        mem_gb = 0
    print(f"{'='*80}")
    print(f"BENCHMARK: {inp}")
    print(f"  Size: {orig_size:,} bytes ({orig_size/1024:.1f} KB)")
    print(f"  MD5:  {orig_md5}")
    print(f"  CRC:  {orig_crc}")
    print(f"  Host: {platform.processor() or 'unknown'} | {platform.system()} {platform.release()} | Python {platform.python_version()}")
    if mem_gb:
        print(f"  RAM:  {mem_gb:.1f} GB")
    print(f"  Binary: {' '.join(BINARY)}")
    print(f"{'='*80}\n")

    for fmt, interlace, compress, encrypt, label in VARIANTS:
        print(f"--- {label} ---")
        video = os.path.join(WORKDIR, f'test_{fmt}_{"il" if interlace else "noil"}_{"enc" if encrypt else "noenc"}.mp4')
        decode_dir = os.path.join(WORKDIR, f'decode_{fmt}_{"il" if interlace else "noil"}_{"enc" if encrypt else "noenc"}')
        os.makedirs(decode_dir, exist_ok=True)

        # ── Encode ──
        enc_cmd = BINARY + ['encode', inp, video, '--format', fmt]
        if interlace:
            enc_cmd.append('--interlace')
        if compress:
            enc_cmd.append('--compress')
        if encrypt:
            enc_cmd.extend(['--key', KEY])

        t0 = time.time()
        out = run(enc_cmd)
        t_enc = time.time() - t0

        video_size = get_size(video)
        enc_ok = 'Video saved' in out

        # ── Decode ──
        dec_cmd = BINARY + ['decode', video, decode_dir, '--format', fmt]
        if interlace:
            dec_cmd.append('--interlace')
        if encrypt:
            dec_cmd.extend(['--key', KEY])

        t0 = time.time()
        out = run(dec_cmd)
        t_dec = time.time() - t0

        # Find decoded file
        decoded_file = None
        for f in os.listdir(decode_dir):
            decoded_file = os.path.join(decode_dir, f)
            break

        verified = False
        decoded_md5 = 'N/A'
        decoded_size = 0
        if decoded_file and os.path.exists(decoded_file):
            decoded_size = get_size(decoded_file)
            decoded_md5 = md5(decoded_file)
            verified = (decoded_md5 == orig_md5)

        ratio = video_size / orig_size if orig_size else 0

        row = {
            'label': label,
            'format': fmt,
            'interlace': interlace,
            'compress': compress,
            'encryption': encrypt,
            'enc_time': t_enc,
            'dec_time': t_dec,
            'video_size': video_size,
            'ratio': ratio,
            'verified': verified,
            'orig_md5': orig_md5,
            'decoded_md5': decoded_md5,
        }
        results.append(row)

        status = 'OK' if verified else 'FAIL'
        print(f"  Encode: {t_enc:.2f}s | Decode: {t_dec:.2f}s | "
              f"Video: {video_size/1024:.1f} KB ({ratio:.1f}x) | {status}")
        print()

    # ── Summary table ──
    print(f"\n{'='*100}")
    print(f"BENCHMARK RESULTS — {os.path.basename(inp)} ({orig_size/1024:.1f} KB)")
    print(f"{'='*100}")
    print(f"{'Variant':<30} {'Enc time':>9} {'Dec time':>9} {'Video':>10} {'Ratio':>8} {'Verified':>9}")
    print(f"{'-'*30} {'-'*9} {'-'*9} {'-'*10} {'-'*8} {'-'*9}")

    for r in results:
        vsize = f"{r['video_size']/1024:.1f} KB"
        if r['video_size'] > 1024 * 1024:
            vsize = f"{r['video_size']/1024/1024:.1f} MB"
        ratio = f"{r['ratio']:.1f}x"
        verified = 'YES' if r['verified'] else 'NO'
        print(f"{r['label']:<30} {r['enc_time']:>8.2f}s {r['dec_time']:>8.2f}s {vsize:>10} {ratio:>8} {verified:>9}")

    print(f"\nOriginal MD5: {orig_md5}")
    print(f"{'='*100}")

    # Cleanup
    shutil.rmtree(WORKDIR, ignore_errors=True)


if __name__ == '__main__':
    main()
