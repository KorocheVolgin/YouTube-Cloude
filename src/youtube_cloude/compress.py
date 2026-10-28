#!/usr/bin/env python3
"""7-Zip compression utility for YouTube File Storage.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
GUI concepts from @Maksim4081862.
"""
import os
import shutil
import subprocess
from pathlib import Path


def _find_7z() -> str:
    """Locate the 7z / 7za binary, raising FileNotFoundError if missing."""
    for name in ('7z', '7za', '7zz'):
        path = shutil.which(name)
        if path:
            return path
    raise FileNotFoundError(
        "7-Zip not found. Install p7zip-full (Debian/Ubuntu) "
        "or 7-Zip (Windows/macOS)."
    )


def compress_7z(
    input_file: str,
    output_file: str | None = None,
    level: int = 5,
) -> bool:
    """Compress *input_file* into a .7z archive.

    Parameters
    ----------
    input_file : str
        Path to the file to compress.
    output_file : str or None
        Destination archive path.  Defaults to ``<input_file>.7z``.
    level : int
        Compression level 0 (store) – 9 (ultra).  Default 5.

    Returns
    -------
    bool
        *True* on success, *False* on failure.
    """
    try:
        bin_path = _find_7z()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return False

    in_path = Path(input_file)
    if not in_path.is_file():
        print(f"Error: input file not found: {input_file}")
        return False

    if output_file is None:
        output_file = str(in_path) + ".7z"

    level = max(0, min(9, level))

    try:
        subprocess.run(
            [
                bin_path,
                'a',                       # add to archive
                f'-mx={level}',             # compression level
                '-mhe=on',                  # encrypt headers (requires password)
                output_file,
                str(in_path),
            ],
            check=True,
            capture_output=True,
        )
        print(f"Compressed: {output_file}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"7z compression failed: {exc.stderr.decode(errors='ignore')}")
        return False


def decompress_7z(
    archive_file: str,
    output_dir: str = '.',
) -> bool:
    """Decompress a .7z archive into *output_dir*.

    Parameters
    ----------
    archive_file : str
        Path to the .7z archive.
    output_dir : str
        Destination directory.  Default is the current directory.

    Returns
    -------
    bool
        *True* on success, *False* on failure.
    """
    try:
        bin_path = _find_7z()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return False

    arc_path = Path(archive_file)
    if not arc_path.is_file():
        print(f"Error: archive not found: {archive_file}")
        return False

    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                bin_path,
                'x',                       # extract with full paths
                f'-o{dest}',
                '-y',                      # overwrite without prompting
                str(arc_path),
            ],
            check=True,
            capture_output=True,
        )
        print(f"Extracted to: {dest}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"7z extraction failed: {exc.stderr.decode(errors='ignore')}")
        return False


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(
        description='7-Zip compression / decompression helper'
    )
    sub = ap.add_subparsers(dest='action', required=True)

    c = sub.add_parser('compress', help='Compress a file')
    c.add_argument('input', help='File to compress')
    c.add_argument('-o', '--output', default=None, help='Output archive path')
    c.add_argument(
        '-l', '--level', type=int, default=5, help='Compression level 0-9'
    )

    d = sub.add_parser('decompress', help='Decompress an archive')
    d.add_argument('archive', help='Archive to extract')
    d.add_argument(
        '-o', '--output-dir', default='.', help='Destination directory'
    )

    args = ap.parse_args()

    if args.action == 'compress':
        compress_7z(args.input, args.output, args.level)
    elif args.action == 'decompress':
        decompress_7z(args.archive, args.output_dir)
