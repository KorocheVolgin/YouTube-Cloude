#!/usr/bin/env python3
"""Kivy GUI for YouTube-Cloude Android.

Touch-friendly interface with Encode/Decode/Settings screens.
Uses the same backend (encoder/decoder) as desktop versions.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.core.window import Window

# ── Kivy KV Layout ───────────────────────────────────────────────────────
KV = """
#:import C kivy.utils.get_color_from_hex

ScreenManager:
    MDScreen:
        name: 'encode'
        md_bg_color: C('#0d1117')

        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)

            Label:
                text: 'Encode file to video'
                font_size: sp(20)
                bold: True
                color: C('#58a6ff')
                size_hint_y: None
                height: dp(36)

            Label:
                text: 'Input file:'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            TextInput:
                id: enc_input
                hint_text: 'Select file to encode...'
                readonly: True
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                padding: [dp(12), dp(10)]

            Button:
                text: 'Browse...'
                background_color: C('#21262d')
                color: C('#c9d1d9')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                on_release: app.browse_input()

            Label:
                text: 'Output video:'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            TextInput:
                id: enc_output
                text: 'output.mp4'
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                padding: [dp(12), dp(10)]

            Button:
                id: encode_btn
                text: '▶  Encode'
                background_color: C('#238636')
                color: C('#ffffff')
                font_size: sp(16)
                bold: True
                size_hint_y: None
                height: dp(52)
                on_release: app.start_encode()

            ProgressBar:
                id: enc_progress
                max: 100
                value: 0
                size_hint_y: None
                height: dp(20)

            TextInput:
                id: enc_log
                readonly: True
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_name: ' monospace'
                font_size: sp(11)
                size_hint_y: 1

            BoxLayout:
                size_hint_y: None
                height: dp(56)
                spacing: dp(8)

                Button:
                    text: '▶ Encode'
                    background_color: C('#1f6feb')
                    color: C('#ffffff')
                    on_release: app.switch_screen('encode')

                Button:
                    text: '◀ Decode'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('decode')

                Button:
                    text: '⚙ Settings'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('settings')

    MDScreen:
        name: 'decode'
        md_bg_color: C('#0d1117')

        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)

            Label:
                text: 'Decode video to file'
                font_size: sp(20)
                bold: True
                color: C('#58a6ff')
                size_hint_y: None
                height: dp(36)

            Label:
                text: 'Video file:'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            TextInput:
                id: dec_input
                hint_text: 'Select video to decode...'
                readonly: True
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                padding: [dp(12), dp(10)]

            Button:
                text: 'Browse...'
                background_color: C('#21262d')
                color: C('#c9d1d9')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                on_release: app.browse_video()

            Label:
                text: 'Output directory:'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            TextInput:
                id: dec_output
                text: '.'
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                padding: [dp(12), dp(10)]

            Button:
                id: decode_btn
                text: '▶  Decode'
                background_color: C('#238636')
                color: C('#ffffff')
                font_size: sp(16)
                bold: True
                size_hint_y: None
                height: dp(52)
                on_release: app.start_decode()

            ProgressBar:
                id: dec_progress
                max: 100
                value: 0
                size_hint_y: None
                height: dp(20)

            TextInput:
                id: dec_log
                readonly: True
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_name: ' monospace'
                font_size: sp(11)
                size_hint_y: 1

            BoxLayout:
                size_hint_y: None
                height: dp(56)
                spacing: dp(8)

                Button:
                    text: '▶ Encode'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('encode')

                Button:
                    text: '◀ Decode'
                    background_color: C('#1f6feb')
                    color: C('#ffffff')
                    on_release: app.switch_screen('decode')

                Button:
                    text: '⚙ Settings'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('settings')

    MDScreen:
        name: 'settings'
        md_bg_color: C('#0d1117')

        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)

            Label:
                text: 'Settings'
                font_size: sp(20)
                bold: True
                color: C('#58a6ff')
                size_hint_y: None
                height: dp(36)

            Label:
                text: 'Video format:'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            Spinner:
                id: format_spinner
                text: 'YTV3 — Resilient (30 FPS, RS + luma)'
                values: [
                    'YTV1 — Standard (6 FPS)',
                    'YTV2 — Dense (15 FPS, 21× denser)',
                    'YTV3 — Resilient (30 FPS, RS + luma)',
                ]
                background_color: C('#161b22')
                color: C('#c9d1d9')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)

            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(8)

                Label:
                    text: 'Interlace:'
                    color: C('#8b949e')
                    size_hint_x: 0.4

                Switch:
                    id: interlace_switch
                    active: False
                    size_hint_x: 0.2

                Label:
                    text: 'Better YouTube retention\\n(larger files)'
                    color: C('#484f58')
                    font_size: sp(11)
                    size_hint_x: 0.4

            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(8)

                Label:
                    text: 'Compress (zlib):'
                    color: C('#8b949e')
                    size_hint_x: 0.4

                Switch:
                    id: compress_switch
                    active: False
                    size_hint_x: 0.2

                Label:
                    text: 'Smaller video if compressible'
                    color: C('#484f58')
                    font_size: sp(11)
                    size_hint_x: 0.4

            Label:
                text: 'Encryption key (optional):'
                color: C('#8b949e')
                halign: 'left'
                size_hint_y: None
                height: dp(24)
                text_size: self.size

            TextInput:
                id: key_input
                hint_text: 'Enter key or leave blank...'
                password: True
                background_color: C('#161b22')
                foreground_color: C('#c9d1d9')
                cursor_color: C('#58a6ff')
                font_size: sp(14)
                size_hint_y: None
                height: dp(44)
                padding: [dp(12), dp(10)]

            Label:
                text: 'Key is hashed with SHA-256. Leave blank to disable.'
                color: C('#484f58')
                font_size: sp(12)
                size_hint_y: None
                height: dp(32)

            Widget:

            Label:
                text: 'Credits:\\n  @Hinderchik — original concept\\n  @IvanSCP — argparse CLI\\n  @sosatel30000 — YTV2 format\\n  @Maksim4081862 — GUI concepts\\n  @Verdgil — AES-256-CBC'
                color: C('#484f58')
                font_size: sp(12)
                size_hint_y: None
                height: dp(100)

            BoxLayout:
                size_hint_y: None
                height: dp(56)
                spacing: dp(8)

                Button:
                    text: '▶ Encode'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('encode')

                Button:
                    text: '◀ Decode'
                    background_color: C('#161b22')
                    color: C('#8b949e')
                    on_release: app.switch_screen('decode')

                Button:
                    text: '⚙ Settings'
                    background_color: C('#1f6feb')
                    color: C('#ffffff')
                    on_release: app.switch_screen('settings')
"""


class YouTubeCloudeApp(App):
    """Kivy app for YouTube-Cloude."""

    # Current settings
    format_name = StringProperty('ytv3')
    interlace = BooleanProperty(False)
    key = StringProperty('')

    def build(self):
        self.title = 'YouTube-Cloude'
        self.root = Builder.load_string(KV)
        return self.root

    def switch_screen(self, name: str) -> None:
        self.root.current = name

    # ── Settings ──────────────────────────────────────────────────────
    def _get_settings(self) -> dict:
        spinner_text = self.root.ids.format_spinner.text
        if 'YTV1' in spinner_text:
            fmt = 'ytv1'
        elif 'YTV3' in spinner_text:
            fmt = 'ytv3'
        else:
            fmt = 'ytv2'
        return {
            'format': fmt,
            'interlace': self.root.ids.interlace_switch.active,
            'compress': self.root.ids.compress_switch.active,
            'key': self.root.ids.key_input.text.strip() or None,
        }

    # ── File browsers (Android intent) ────────────────────────────────
    def browse_input(self) -> None:
        """Open file picker — on Android uses plyer, fallback to manual."""
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=self._on_input_selected,
                filters=['All files (*.*)'],
            )
        except ImportError:
            path = '/sdcard/Download/file.bin'
            self.root.ids.enc_input.text = path
            self._auto_set_output(path)

    def _auto_set_output(self, input_path: str) -> None:
        """Set output video to <input_dir>/<stem>.mp4."""
        import os

        if not input_path.strip():
            return
        stem = os.path.splitext(os.path.basename(input_path))[0]
        if not stem:
            stem = os.path.basename(input_path)
        suggested = os.path.join(os.path.dirname(input_path), stem + ".mp4")
        self.root.ids.enc_output.text = suggested

    def _on_input_selected(self, selection: list) -> None:
        if selection:
            path = selection[0]
            self.root.ids.enc_input.text = path
            self._auto_set_output(path)

    def browse_video(self) -> None:
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=self._on_video_selected,
                filters=['MP4 video (*.mp4)', 'All files (*.*)'],
            )
        except ImportError:
            self.root.ids.dec_input.text = '/sdcard/Download/video.mp4'

    def _on_video_selected(self, selection: list) -> None:
        if selection:
            self.root.ids.dec_input.text = selection[0]

    # ── Encode ────────────────────────────────────────────────────────
    def start_encode(self) -> None:
        # Toggle: if already running -> cancel
        if getattr(self, '_enc_thread', None) is not None and self._enc_thread.is_alive():
            enc = getattr(self, '_enc_encoder', None)
            if enc is not None:
                try:
                    enc.cancel()
                except Exception:
                    pass
            self.root.ids.encode_btn.text = '⏳ Cancelling...'
            self.root.ids.enc_log.text += '\nCancelling...'
            return

        input_file = self.root.ids.enc_input.text.strip()
        output_file = self.root.ids.enc_output.text.strip() or 'output.mp4'

        if not input_file:
            self.root.ids.enc_log.text = '⚠ Please select a file to encode.'
            return

        settings = self._get_settings()
        self.root.ids.encode_btn.text = '⏹  Stop'
        self.root.ids.encode_btn.disabled = False
        self.root.ids.enc_log.text = ''
        self.root.ids.enc_progress.value = 0

        def _worker():
            try:
                from youtube_cloude.encoder import YouTubeEncoder

                self._enc_encoder = YouTubeEncoder(
                    settings['key'],
                    format_name=settings['format'],
                    interlace=settings['interlace'],
                    compress=settings['compress'],
                )

                def cb(done: int, total: int):
                    if getattr(self._enc_encoder, '_cancelled', False):
                        return
                    pct = int(done / total * 100) if total else 0
                    Clock.schedule_once(lambda dt: self._update_enc_progress(pct))

                ok = self._enc_encoder.encode(input_file, output_file, progress_callback=cb)
                if getattr(self._enc_encoder, '_cancelled', False):
                    Clock.schedule_once(lambda dt: self._encode_cancelled())
                else:
                    Clock.schedule_once(lambda dt: self._encode_done(ok, output_file))
            except Exception as e:
                if getattr(self, '_enc_encoder', None) and getattr(self._enc_encoder, '_cancelled', False):
                    Clock.schedule_once(lambda dt: self._encode_cancelled())
                else:
                    Clock.schedule_once(lambda dt: self._encode_error(str(e)))
            finally:
                self._enc_encoder = None

        self._enc_thread = threading.Thread(target=_worker, daemon=True)
        self._enc_thread.start()

    def _update_enc_progress(self, pct: int) -> None:
        self.root.ids.enc_progress.value = pct
        self.root.ids.enc_log.text += f'  Progress: {pct}%\n'

    def _encode_done(self, ok: bool, path: str) -> None:
        self.root.ids.encode_btn.disabled = False
        self.root.ids.encode_btn.text = '▶  Encode'
        self.root.ids.enc_progress.value = 0 if not ok else 100
        if ok:
            self.root.ids.enc_log.text += f'\n✅ Done! Saved to: {path}'
        else:
            self.root.ids.enc_log.text += '\n❌ Encoding failed.'

    def _encode_cancelled(self) -> None:
        self.root.ids.encode_btn.disabled = False
        self.root.ids.encode_btn.text = '▶  Encode'
        self.root.ids.enc_progress.value = 0
        self.root.ids.enc_log.text += '\n⏹ Cancelled.'

    def _encode_error(self, msg: str) -> None:
        self.root.ids.encode_btn.disabled = False
        self.root.ids.encode_btn.text = '▶  Encode'
        self.root.ids.enc_log.text += f'\n❌ Error: {msg}'

    # ── Decode ────────────────────────────────────────────────────────
    def start_decode(self) -> None:
        if getattr(self, '_dec_thread', None) is not None and self._dec_thread.is_alive():
            dec = getattr(self, '_dec_decoder', None)
            if dec is not None:
                try:
                    dec.cancel()
                except Exception:
                    pass
            self.root.ids.decode_btn.text = '⏳ Cancelling...'
            self.root.ids.dec_log.text += '\nCancelling...'
            return

        video_file = self.root.ids.dec_input.text.strip()
        output_dir = self.root.ids.dec_output.text.strip() or '.'

        if not video_file:
            self.root.ids.dec_log.text = '⚠ Please select a video to decode.'
            return

        settings = self._get_settings()
        self.root.ids.decode_btn.text = '⏹  Stop'
        self.root.ids.decode_btn.disabled = False
        self.root.ids.dec_log.text = ''
        self.root.ids.dec_progress.value = 0

        def _worker():
            try:
                from youtube_cloude.decoder import YouTubeDecoder

                self._dec_decoder = YouTubeDecoder(
                    settings['key'],
                    interlace=settings['interlace'],
                )

                def cb(done: int, total: int):
                    if getattr(self._dec_decoder, '_cancelled', False):
                        return
                    pct = int(done / total * 100) if total else 0
                    Clock.schedule_once(lambda dt: self._update_dec_progress(pct))

                ok = self._dec_decoder.decode(video_file, output_dir, progress_callback=cb)
                if getattr(self._dec_decoder, '_cancelled', False):
                    Clock.schedule_once(lambda dt: self._decode_cancelled())
                else:
                    Clock.schedule_once(lambda dt: self._decode_done(ok))
            except Exception as e:
                if getattr(self, '_dec_decoder', None) and getattr(self._dec_decoder, '_cancelled', False):
                    Clock.schedule_once(lambda dt: self._decode_cancelled())
                else:
                    Clock.schedule_once(lambda dt: self._decode_error(str(e)))
            finally:
                self._dec_decoder = None

        self._dec_thread = threading.Thread(target=_worker, daemon=True)
        self._dec_thread.start()

    def _update_dec_progress(self, pct: int) -> None:
        self.root.ids.dec_progress.value = pct
        self.root.ids.dec_log.text += f'  Progress: {pct}%\n'

    def _decode_done(self, ok: bool) -> None:
        self.root.ids.decode_btn.disabled = False
        self.root.ids.decode_btn.text = '▶  Decode'
        if ok:
            self.root.ids.dec_log.text += '\n✅ Decode complete!'
        else:
            self.root.ids.dec_log.text += '\n⚠ Decode finished with issues.'

    def _decode_cancelled(self) -> None:
        self.root.ids.decode_btn.disabled = False
        self.root.ids.decode_btn.text = '▶  Decode'
        self.root.ids.dec_progress.value = 0
        self.root.ids.dec_log.text += '\n⏹ Cancelled.'

    def _decode_error(self, msg: str) -> None:
        self.root.ids.decode_btn.disabled = False
        self.root.ids.decode_btn.text = '▶  Decode'
        self.root.ids.dec_log.text += f'\n❌ Error: {msg}'


def main() -> None:
    YouTubeCloudeApp().run()


if __name__ == '__main__':
    main()
