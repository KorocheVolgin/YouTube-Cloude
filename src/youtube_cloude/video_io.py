#!/usr/bin/env python3
"""Video I/O via ffmpeg subprocess — lightweight replacement for OpenCV.

Uses ffprobe for metadata and ffmpeg pipe for frame-level access.
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Generator, Optional

import numpy as np


def _win_hide_kwargs() -> dict:
    """Return subprocess kwargs to hide console window on Windows."""
    if sys.platform.startswith('win'):
        # CREATE_NO_WINDOW prevents a new console window for ffmpeg/ffprobe
        return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)}
    return {}


def _next_to_exe(name: str) -> Optional[str]:
    """Check for ffmpeg/ffprobe placed next to the main executable on disk (user override)."""
    exe_dir = Path(sys.executable).parent
    for cand in [exe_dir / name, exe_dir / f"{name}.exe"]:
        if cand.exists():
            return str(cand)
    return None


def _bundled_bin(name: str) -> Optional[str]:
    """Check for ffmpeg/ffprobe bundled inside the Nuitka payload (fallback)."""
    # 1) opposite of _next_to_exe: inside extracted temp / package data
    #    (Nuitka onefile extracts data files to a temp dir; check pkg dir)
    pkg_dir = Path(__file__).parent
    for cand in [pkg_dir / name, pkg_dir / f"{name}.exe",
                 pkg_dir.parent.parent / "ffmpeg-bin" / name,
                 pkg_dir.parent.parent / "ffmpeg-bin" / f"{name}.exe"]:
        if cand.exists():
            return str(cand)
    # 2) relative to executable's dist folder (Linux .dist / AppImage usr)
    exe_dir = Path(sys.executable).parent
    for parent in [exe_dir, exe_dir.parent]:
        for cand in [parent / name, parent / f"{name}.exe",
                     parent / "ffmpeg-bin" / name, parent / "ffmpeg-bin" / f"{name}.exe"]:
            # _next_to_exe already checked exe_dir directly; here we check parents/dist subfolders
            # avoid duplicate hit for exe_dir itself (handled above)
            if parent == exe_dir:
                continue
            if cand.exists():
                return str(cand)
    # 3) Nuitka onefile temp: sys._MEIPASS or __nuitka_binary_dir (if available)
    for attr in ['_MEIPASS', '__nuitka_binary_dir']:
        base = getattr(sys, attr, None)
        if base:
            for cand in [Path(base) / name, Path(base) / f"{name}.exe"]:
                if cand.exists():
                    return str(cand)
    return None


def _env_override(name: str) -> Optional[str]:
    """Check env vars for custom ffmpeg/ffprobe path (highest priority)."""
    import os

    # YOUTUBE_CLOUDE_FFMPEG / YOUTUBE_CLOUDE_FFPROBE, plus common FFMPEG_PATH
    keys = {
        'ffmpeg': ['YOUTUBE_CLOUDE_FFMPEG', 'FFMPEG_PATH', 'FFMPEG'],
        'ffprobe': ['YOUTUBE_CLOUDE_FFPROBE', 'FFPROBE_PATH', 'FFPROBE'],
    }
    for k in keys.get(name, []):
        val = os.environ.get(k)
        if val and Path(val).exists():
            return str(Path(val))
        # also allow directory containing the binary
        if val and Path(val).is_dir():
            for cand in [Path(val) / name, Path(val) / f"{name}.exe"]:
                if cand.exists():
                    return str(cand)
    return None


def _find_ffmpeg() -> str:
    """Return path to ffmpeg binary.

    Priority (as requested): --ffmpeg/env > next-to-exe > PATH > bundled.
    This lets a user drop ffmpeg.exe next to youtube-cloude.exe to override,
    uses system ffmpeg if in PATH, and falls back to the static bundled copy.
    """
    env = _env_override('ffmpeg')
    if env:
        return env
    nxt = _next_to_exe('ffmpeg')
    if nxt:
        return nxt
    path = shutil.which('ffmpeg')
    if path:
        return path
    bundled = _bundled_bin('ffmpeg')
    if bundled:
        return bundled
    raise FileNotFoundError(
        "ffmpeg not found. Place ffmpeg next to the executable, "
        "install it (apt/brew/choco), set YOUTUBE_CLOUDE_FFMPEG or --ffmpeg, "
        "or use the bundled build."
    )


def _find_ffprobe() -> str:
    """Return path to ffprobe binary (env > next-to-exe > PATH > bundled) or raise."""
    env = _env_override('ffprobe')
    if env:
        return env
    nxt = _next_to_exe('ffprobe')
    if nxt:
        return nxt
    path = shutil.which('ffprobe')
    if path:
        return path
    bundled = _bundled_bin('ffprobe')
    if bundled:
        return bundled
    raise FileNotFoundError(
        "ffprobe not found. Place ffprobe next to the executable, "
        "install ffmpeg, set YOUTUBE_CLOUDE_FFPROBE, or use bundled build."
    )


# ── Metadata ────────────────────────────────────────────────────────────────

def probe_video(video_file: str) -> dict:
    """Probe a video file and return metadata.

    Returns dict with keys: width, height, fps, total_frames, duration, codec.
    """
    ffprobe = _find_ffprobe()
    cmd = [
        ffprobe,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(video_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, **_win_hide_kwargs())
    info = json.loads(result.stdout)

    # Find the video stream
    video_stream = None
    for stream in info.get('streams', []):
        if stream.get('codec_type') == 'video':
            video_stream = stream
            break

    if video_stream is None:
        raise ValueError(f"No video stream found in {video_file}")

    # Parse fps from r_frame_rate (e.g. "30/1" or "30000/1001")
    r_frame_rate = video_stream.get('r_frame_rate', '0/1')
    num, den = map(int, r_frame_rate.split('/'))
    fps = num / den if den else 0.0

    width = int(video_stream.get('width', 0))
    height = int(video_stream.get('height', 0))

    # Total frames: prefer nb_frames, fall back to duration * fps
    total_frames_str = video_stream.get('nb_frames')
    if total_frames_str and total_frames_str != 'N/A':
        total_frames = int(total_frames_str)
    else:
        duration = float(info.get('format', {}).get('duration', 0))
        total_frames = int(duration * fps) if fps else 0

    codec = video_stream.get('codec_name', 'unknown')

    return {
        'width': width,
        'height': height,
        'fps': fps,
        'total_frames': total_frames,
        'duration': float(info.get('format', {}).get('duration', 0)),
        'codec': codec,
    }


# ── Frame reading ───────────────────────────────────────────────────────────

def read_frames(
    video_file: str,
    start_frame: int = 0,
    max_frames: Optional[int] = None,
) -> Generator[tuple[int, np.ndarray], None, None]:
    """Yield (frame_number, frame_array) tuples from a video file.

    Uses ffmpeg rawvideo pipe — no OpenCV needed.
    Frames are returned as BGR numpy arrays (H, W, 3) dtype=uint8,
    matching OpenCV convention for drop-in compatibility.

    Args:
        video_file: Path to video file.
        start_frame: Frame number to start from (0-indexed).
        max_frames: Maximum number of frames to read (None = all).
    """
    ffmpeg = _find_ffmpeg()
    meta = probe_video(video_file)
    width = meta['width']
    height = meta['height']
    fps = meta['fps']
    total_frames = meta['total_frames']

    if start_frame > 0:
        # Calculate seek time in seconds
        seek_time = start_frame / fps if fps else 0
    else:
        seek_time = 0

    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
    ]
    if seek_time > 0:
        cmd.extend(['-ss', f'{seek_time:.6f}'])
    cmd.extend([
        '-i', str(video_file),
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        'pipe:1',
    ])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_win_hide_kwargs())

    frame_size = width * height * 3  # BGR = 3 bytes per pixel
    frame_num = start_frame
    frames_read = 0

    try:
        while True:
            if max_frames is not None and frames_read >= max_frames:
                break

            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break  # end of video or short read

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            yield frame_num, frame.copy()  # copy to avoid buffer reuse issues

            frame_num += 1
            frames_read += 1
    finally:
        proc.stdout.close()
        proc.stderr.close()
        proc.wait()


# ── Frame writing ───────────────────────────────────────────────────────────

def save_frames_as_png(
    frames_dir: str,
    frame_arrays: list[tuple[int, np.ndarray]],
    prefix: str = 'frame_',
) -> list[str]:
    """Save numpy frames as PNG files using Pillow.

    Returns list of saved file paths.
    """
    from PIL import Image

    saved = []
    for frame_num, frame in frame_arrays:
        filename = f"{prefix}{frame_num:05d}.png"
        filepath = str(Path(frames_dir) / filename)
        # BGR → RGB for Pillow
        img = Image.fromarray(frame[:, :, ::-1])
        img.save(filepath)
        saved.append(filepath)
    return saved


def save_frame_png(frame: np.ndarray, filepath: str) -> None:
    """Save a single numpy frame (BGR) as PNG using Pillow."""
    from PIL import Image
    img = Image.fromarray(frame[:, :, ::-1])
    img.save(filepath)


def read_frame_png(filepath: str) -> np.ndarray:
    """Read a PNG file as a BGR numpy array (for OpenCV compatibility)."""
    from PIL import Image
    img = Image.open(filepath).convert('RGB')
    return np.array(img)[:, :, ::-1]  # RGB → BGR


# ── Video writing (PNG sequence → MP4) ──────────────────────────────────────

def png_sequence_to_mp4(
    input_pattern: str,
    output_file: str,
    fps: int,
    pix_fmt: str = 'yuv420p',
    crf: str = '23',
    preset: str = 'slow',
    extra_args: Optional[list[str]] = None,
) -> bool:
    """Convert a PNG frame sequence to MP4 using ffmpeg.

    Args:
        input_pattern: ffmpeg input pattern, e.g. '/tmp/frames/frame_%05d.png'
        output_file: Output .mp4 file path.
        fps: Frames per second.
        pix_fmt: Pixel format ('yuv420p' for standard, 'yuv444p' for interlaced).
        crf: Constant rate factor (0 = lossless, 23 = default, 28 = low quality).
        preset: Encoding preset ('ultrafast' to 'veryslow').
        extra_args: Additional ffmpeg arguments.

    Returns:
        True on success, False on failure.
    """
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
        '-framerate', str(fps),
        '-i', input_pattern,
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', crf,
        '-pix_fmt', pix_fmt,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend([
        '-an',
        '-movflags', '+faststart',
        '-y',
        output_file,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True, **_win_hide_kwargs())
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr}")
        return False
    return True


# ── Resize using Pillow (nearest-neighbor) ──────────────────────────────────

def resize_frame(
    frame: np.ndarray,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    """Resize a BGR frame using Pillow nearest-neighbor interpolation."""
    from PIL import Image
    h, w = frame.shape[:2]
    if w == target_width and h == target_height:
        return frame
    img = Image.fromarray(frame[:, :, ::-1])  # BGR → RGB
    img = img.resize((target_width, target_height), Image.NEAREST)
    return np.array(img)[:, :, ::-1]  # RGB → BGR


# ── Color conversion (BGR → Gray using numpy) ───────────────────────────────

def bgr_to_gray(frame: np.ndarray) -> np.ndarray:
    """Convert a BGR frame to grayscale using standard luminance formula.

    Uses: 0.114*B + 0.587*G + 0.299*R (OpenCV-compatible formula for BGR input).
    """
    # frame is BGR: channel 0=B, 1=G, 2=R
    gray = 0.114 * frame[:, :, 0].astype(np.float32) \
         + 0.587 * frame[:, :, 1].astype(np.float32) \
         + 0.299 * frame[:, :, 2].astype(np.float32)
    return gray.astype(np.uint8)
