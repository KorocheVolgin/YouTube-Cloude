#!/usr/bin/env python3
"""Shared service layer for all GUIs (Qt/Kivy/Tkinter).

Extracts common encode/decode/settings logic so the three GUI
implementations no longer duplicate ~80% of workflow code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class EncodeSettings:
    format: str = 'ytv3'
    interlace: bool = False
    compress: bool = False
    key: Optional[str] = None


@dataclass
class DecodeSettings:
    interlace: bool = False
    key: Optional[str] = None
    format: Optional[str] = None  # None = auto-detect


def encode_file(
    input_file: str,
    output_file: str,
    settings: EncodeSettings,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Run YouTubeEncoder with shared settings."""
    from .encoder import YouTubeEncoder

    enc = YouTubeEncoder(
        settings.key,
        format_name=settings.format,
        interlace=settings.interlace,
        compress=settings.compress,
    )
    return enc.encode(input_file, output_file, progress_callback=progress_callback)


def decode_file(
    video_file: str,
    output_dir: str,
    settings: DecodeSettings,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Run YouTubeDecoder with shared settings."""
    from .decoder import YouTubeDecoder

    dec = YouTubeDecoder(
        settings.key,
        format_name=settings.format,
        interlace=settings.interlace,
    )
    return dec.decode(video_file, output_dir, progress_callback=progress_callback)


def validate_encode_input(path: str) -> Optional[str]:
    """Return error message or None if valid."""
    import os

    if not path.strip():
        return "Please select a file to encode."
    if not os.path.exists(path):
        return f"File not found: {path}"
    return None


def validate_decode_input(path: str) -> Optional[str]:
    import os

    if not path.strip():
        return "Please select a video to decode."
    if not os.path.exists(path):
        return f"File not found: {path}"
    return None
