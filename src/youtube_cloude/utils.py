#!/usr/bin/env python3
"""CLI helpers and argparse entry-point for YouTube File Storage.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
GUI concepts from @Maksim4081862.
"""
import argparse
import os
import sys
from typing import Optional

from .core import read_key_from_file
from .encoder import YouTubeEncoder
from .decoder import YouTubeDecoder


def resolve_key(args: argparse.Namespace) -> Optional[str]:
    """Determine encryption key by priority:
      1. --key TEXT
      2. --key-file PATH
      3. key.txt next to the script (legacy)
    """
    if args.key:
        print("Key from --key argument")
        return args.key

    if args.key_file:
        key = read_key_from_file(args.key_file)
        if key is None:
            print(f"Error: could not read key from: {args.key_file}")
            sys.exit(1)
        return key

    return read_key_from_file()


def add_key_args(subparser: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add mutually-exclusive encryption key arguments to *subparser*."""
    group = subparser.add_mutually_exclusive_group()
    group.add_argument(
        '--key',
        metavar='TEXT',
        help='Encryption key as a string',
    )
    group.add_argument(
        '--key-file',
        metavar='PATH',
        help='Path to a file containing the encryption key',
    )


def add_format_arg(subparser: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add format selection argument to *subparser*."""
    subparser.add_argument(
        '--format',
        metavar='FMT',
        choices=['ytv1', 'ytv2', 'ytv3'],
        default='ytv1',
        help='Video format: ytv1 (6 FPS), ytv2 (15 FPS, 21x denser), ytv3 (30 FPS, RS + luma, yuv420p safe)',
    )


def add_interlace_arg(subparser: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add interlace flag to *subparser*."""
    subparser.add_argument(
        '--interlace',
        action='store_true',
        default=False,
        help='Interlace frames for better YouTube compression',
    )


def add_compress_arg(subparser: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add --compress flag."""
    subparser.add_argument(
        '--compress',
        action='store_true',
        default=False,
        help='Compress file with zlib before encoding (auto-skipped if would enlarge)',
    )


def add_ffmpeg_args(parser) -> None:  # type: ignore[type-arg]
    """Add custom ffmpeg/ffprobe path args."""
    parser.add_argument(
        '--ffmpeg',
        metavar='PATH',
        default=None,
        help='Custom ffmpeg binary (default: bundled, then PATH, or $YOUTUBE_CLOUDE_FFMPEG)',
    )
    parser.add_argument(
        '--ffprobe',
        metavar='PATH',
        default=None,
        help='Custom ffprobe binary (default: bundled, then PATH, or $YOUTUBE_CLOUDE_FFPROBE)',
    )


def add_max_size_arg(subparser: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add max file size argument to *subparser*."""
    subparser.add_argument(
        '--max-size',
        metavar='MB',
        type=float,
        default=None,
         help='Max input file size in MB (default: 100 for YTV1, 500 for YTV2/YTV3)',
    )


def main() -> None:
    """CLI entry-point."""
    parser = argparse.ArgumentParser(
        prog='youtube-cloude',
        description='YouTube File Storage - encode files into video',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
commands:
  encode       Encode a file into video
                 --key TEXT | --key-file PATH   encryption
                 --format ytv1|ytv2|ytv3        video format
                 --interlace                    better YouTube quality (ignored for YTV3)
                 --compress                     zlib compress before encoding
                 --max-size MB                  file size limit

  encode-dir   Batch-encode all files in a directory
                 (same flags as encode)

  decode       Decode a video back to a file
                 --key TEXT | --key-file PATH   decryption
                 --format ytv1|ytv2|ytv3        force format
                 --interlace                    deinterlace frames

examples:
  youtube-cloude encode file.zip video.mp4
  youtube-cloude encode file.zip video.mp4 --format ytv2 --interlace
  youtube-cloude encode secret.bin video.mp4 --key "my-password"
  youtube-cloude encode-dir ./data/ ./output/ --format ytv2
  youtube-cloude decode video.mp4 --key "my-password"
""",
    )

    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')
    subparsers.required = True

    # encode
    enc = subparsers.add_parser(
        'encode',
        help='Encode a file into video (--key, --format, --interlace, --ffmpeg, --max-size)',
    )
    enc.add_argument(
        'input_file', metavar='FILE', help='Path to the file to encode'
    )
    enc.add_argument(
        'output_file',
        metavar='VIDEO',
        nargs='?',
        default='output.mp4',
        help='Output MP4 filename (default: output.mp4)',
    )
    add_key_args(enc)
    add_format_arg(enc)
    add_interlace_arg(enc)
    add_compress_arg(enc)
    add_ffmpeg_args(enc)
    add_max_size_arg(enc)

    # encode-dir (batch mode)
    enc_dir = subparsers.add_parser(
        'encode-dir',
        help='Batch-encode all files in a directory (--key, --format, --interlace, --compress, --ffmpeg, --max-size)',
    )
    enc_dir.add_argument(
        'input_dir', metavar='DIR', help='Directory containing files to encode'
    )
    enc_dir.add_argument(
        'output_dir',
        metavar='OUTDIR',
        nargs='?',
        default='.',
        help='Output directory for MP4 files (default: current)',
    )
    add_key_args(enc_dir)
    add_format_arg(enc_dir)
    add_interlace_arg(enc_dir)
    add_compress_arg(enc_dir)
    add_ffmpeg_args(enc_dir)
    add_max_size_arg(enc_dir)

    # decode
    dec = subparsers.add_parser(
        'decode',
        help='Decode a video back to a file (--key, --format, --interlace, --ffmpeg)',
    )
    dec.add_argument(
        'video_file', metavar='VIDEO', help='Path to the MP4 to decode'
    )
    dec.add_argument(
        'output_dir',
        metavar='DIR',
        nargs='?',
        default='.',
        help='Output directory (default: current)',
    )
    add_key_args(dec)
    add_format_arg(dec)
    add_interlace_arg(dec)
    add_ffmpeg_args(dec)

    args = parser.parse_args()
    # Apply custom ffmpeg paths early (env > bundled > PATH)
    if getattr(args, 'ffmpeg', None):
        os.environ['YOUTUBE_CLOUDE_FFMPEG'] = args.ffmpeg
    if getattr(args, 'ffprobe', None):
        os.environ['YOUTUBE_CLOUDE_FFPROBE'] = args.ffprobe
    key = resolve_key(args)

    if args.command == 'encode':
        max_size = int(args.max_size * 1024 * 1024) if args.max_size else None
        encoder = YouTubeEncoder(
            key, format_name=args.format, interlace=args.interlace,
            max_file_size=max_size, compress=args.compress,
        )
        encoder.encode(args.input_file, args.output_file)

    elif args.command == 'encode-dir':
        _encode_dir(args, key)

    elif args.command == 'decode':
        decoder = YouTubeDecoder(
            key, format_name=args.format, interlace=args.interlace,
        )
        decoder.decode(args.video_file, args.output_dir)


def _encode_dir(args: argparse.Namespace, key: Optional[str]) -> None:
    """Batch-encode all files in *args.input_dir*."""
    input_dir = args.input_dir
    output_dir = args.output_dir

    if not os.path.isdir(input_dir):
        print(f"Error: not a directory: {input_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    files = sorted(
        f for f in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, f))
    )
    if not files:
        print(f"No files found in {input_dir}")
        return

    print(f"Batch encode: {len(files)} file(s) from {input_dir} → {output_dir}")
    max_size = int(args.max_size * 1024 * 1024) if args.max_size else None
    encoder = YouTubeEncoder(
        key, format_name=args.format, interlace=args.interlace,
        max_file_size=max_size, compress=args.compress,
    )

    ok_count = 0
    for i, fname in enumerate(files, 1):
        src = os.path.join(input_dir, fname)
        dst = os.path.join(output_dir, os.path.splitext(fname)[0] + '.mp4')
        print(f"\n--- [{i}/{len(files)}] {fname} ---")
        if encoder.encode(src, dst):
            ok_count += 1

    print(f"\n{'='*60}")
    print(f"Batch complete: {ok_count}/{len(files)} succeeded")
