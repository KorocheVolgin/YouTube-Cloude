#!/usr/bin/env python3
"""YouTube upload / download helpers for YouTube File Storage.

Uses yt-dlp for downloads and YouTube Data API v3 (OAuth 2) for uploads.

Improvements based on work by @Hinderchik, @IvanSCP, and @sosatel30000.
See: https://github.com/Hinderchik/YouTube-Cloude-Fork
     https://github.com/IvanSCP/YouTube-Cloude
     https://github.com/sosatel30000/YouTube-Cloude
GUI concepts from @Maksim4081862.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ── yt-dlp availability check ──────────────────────────────────────────────
def _check_ytdlp() -> bool:
    """Return *True* if yt-dlp is installed."""
    return shutil.which('yt-dlp') is not None


def _warn_ytdlp_missing() -> None:
    print(
        "Warning: yt-dlp is not installed.  Install it with:\n"
        "  pip install yt-dlp\n"
        "or visit https://github.com/yt-dlp/yt-dlp"
    )


# ── Download ────────────────────────────────────────────────────────────────
def download_from_youtube(
    url: str,
    output_dir: str = '.',
) -> Optional[str]:
    """Download a video from *url* into *output_dir* using yt-dlp.

    Returns the path to the downloaded file, or *None* on failure.
    """
    if not _check_ytdlp():
        _warn_ytdlp_missing()
        return None

    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)

    out_template = str(dest / '%(title)s.%(ext)s')

    try:
        subprocess.run(
            [
                'yt-dlp',
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                '-o', out_template,
                url,
            ],
            check=True,
            capture_output=True,
        )
        # Find the most recently created file in output_dir
        files = sorted(dest.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            if f.is_file():
                print(f"Downloaded: {f}")
                return str(f)
        return None
    except subprocess.CalledProcessError as exc:
        print(f"Download failed: {exc.stderr.decode(errors='ignore')}")
        return None


# ── Upload (YouTube Data API v3) ───────────────────────────────────────────
def _print_upload_instructions() -> None:
    """Print setup instructions for YouTube Data API v3 OAuth2 upload."""
    print(
        "\n"
        "=== YouTube Data API v3 Upload Setup ===\n"
        "\n"
        "1. Go to https://console.cloud.google.com/\n"
        "2. Create a project (or select an existing one).\n"
        "3. Enable the 'YouTube Data API v3' for the project.\n"
        "4. Under 'Credentials', create an OAuth 2.0 Client ID\n"
        "   (type: Desktop App).  Download the JSON as\n"
        "   'client_secret.json' and place it next to this script.\n"
        "5. Install the Google client library:\n"
        "       pip install google-api-python-client google-auth-oauthlib\n"
        "6. On first upload, a browser window will open asking you to\n"
        "   authorise the app.  A token.json will be cached afterwards.\n"
        "\n"
        "See: https://developers.google.com/youtube/v3/guides/uploading_a_video\n"
    )


def upload_to_youtube(
    video_file: str,
    title: str,
    description: str = '',
    key_file: str | None = None,
) -> Optional[str]:
    """Upload *video_file* to YouTube.

    Parameters
    ----------
    video_file : str
        Path to the MP4 file.
    title : str
        Video title.
    description : str
        Video description.
    key_file : str or None
        Path to an OAuth2 *client_secret.json*.  Defaults to
        ``client_secret.json`` next to this script.

    Returns
    -------
    str or None
        The YouTube video URL on success, or *None* on failure.
    """
    vpath = Path(video_file)
    if not vpath.is_file():
        print(f"Error: file not found: {video_file}")
        return None

    # Try the google client library
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        _print_upload_instructions()
        return None

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    token_path = Path('token.json')
    client_secret = Path(key_file) if key_file else Path('client_secret.json')

    if not client_secret.exists():
        print("Error: OAuth client secret file not found.")
        _print_upload_instructions()
        return None

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['YouTube-Cloude', 'file-storage'],
            'categoryId': '22',
        },
        'status': {
            'privacyStatus': 'unlisted',
        },
    }

    media = MediaFileUpload(str(vpath), mimetype='video/mp4', resumable=True)

    req = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")

    video_id = response['id']
    url = f"https://youtu.be/{video_id}"
    print(f"Uploaded: {url}")
    return url


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description='YouTube upload / download helper')
    sub = ap.add_subparsers(dest='action', required=True)

    dl = sub.add_parser('download', help='Download a video')
    dl.add_argument('url', help='YouTube video URL')
    dl.add_argument(
        '-o', '--output-dir', default='.', help='Output directory'
    )

    ul = sub.add_parser('upload', help='Upload a video')
    ul.add_argument('video', help='Video file to upload')
    ul.add_argument('-t', '--title', required=True, help='Video title')
    ul.add_argument('-d', '--description', default='', help='Description')
    ul.add_argument('--key-file', default=None, help='OAuth2 client_secret.json')

    args = ap.parse_args()

    if args.action == 'download':
        download_from_youtube(args.url, args.output_dir)
    elif args.action == 'upload':
        upload_to_youtube(args.video, args.title, args.description, args.key_file)
