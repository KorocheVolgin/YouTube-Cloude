#!/usr/bin/env python3
"""PySide6 GUI for YouTube-Cloude.

Responsive layout:
  - Desktop: sidebar navigation + content area
  - Mobile:  bottom navigation bar + stacked pages

Features: Encode, Decode, Settings, Camera (Android).
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, Slot, QSize, QSettings, QTimer,
)
from PySide6.QtGui import QFont, QIcon, QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QTabBar, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QFrame, QSizePolicy, QSpacerItem, QGroupBox,
    QGridLayout, QFormLayout, QScrollArea, QToolButton,
)

# ── Version ──────────────────────────────────────────────────────────────
try:
    from youtube_cloude import __version__
except ImportError:
    __version__ = "dev"


# ── Dark theme QSS ──────────────────────────────────────────────────────
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', 'SF Pro', 'Ubuntu', sans-serif;
    font-size: 14px;
}

QLabel {
    color: #c9d1d9;
    background: transparent;
}

QLineEdit {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: #1f6feb;
    min-height: 20px;
}

QLineEdit:focus {
    border-color: #58a6ff;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
}

QPushButton:pressed {
    background-color: #1f6feb;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton#primary {
    background-color: #238636;
    border-color: #2ea043;
    color: #ffffff;
    font-weight: bold;
    padding: 10px 24px;
}

QPushButton#primary:hover {
    background-color: #2ea043;
}

QPushButton#primary:disabled {
    background-color: #1a4b2e;
    color: #484f58;
}

QPushButton#danger {
    background-color: #da3633;
    border-color: #f85149;
    color: #ffffff;
}

QComboBox {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #58a6ff;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
}

QCheckBox {
    color: #c9d1d9;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #30363d;
    background-color: #161b22;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #2ea043;
}

QProgressBar {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    text-align: center;
    color: #c9d1d9;
    min-height: 22px;
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 5px;
}

QTextEdit {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px;
    font-family: 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
}

QGroupBox {
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #58a6ff;
}

/* Bottom nav bar (mobile) */
QFrame#bottomNav {
    background-color: #161b22;
    border-top: 1px solid #30363d;
}

QPushButton#navBtn {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 8px 4px;
    color: #8b949e;
    font-size: 11px;
    min-width: 60px;
}

QPushButton#navBtn:checked {
    color: #58a6ff;
    border-top: 2px solid #58a6ff;
}

/* Sidebar nav (desktop) */
QPushButton#sideBtn {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    color: #8b949e;
    font-size: 14px;
}

QPushButton#sideBtn:hover {
    background-color: #21262d;
    color: #c9d1d9;
}

QPushButton#sideBtn:checked {
    background-color: #1f6feb20;
    color: #58a6ff;
    font-weight: bold;
}

/* Version label */
QLabel#version {
    color: #484f58;
    font-size: 11px;
}
"""


# ── Worker threads ───────────────────────────────────────────────────────
class EncodeWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(bool, str)
    error = Signal(str)

    def __init__(
        self, input_file: str, output_file: str,
        key: Optional[str], fmt: str, interlace: bool, compress: bool = False,
    ):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.key = key
        self.fmt = fmt
        self.interlace = interlace
        self.compress = compress
        self._cancelled = False
        self.encoder = None

    def cancel(self) -> None:
        self._cancelled = True
        if self.encoder is not None:
            try:
                self.encoder.cancel()
            except Exception:
                pass

    def run(self) -> None:
        try:
            from youtube_cloude.encoder import YouTubeEncoder

            self.encoder = YouTubeEncoder(
                self.key, format_name=self.fmt,
                interlace=self.interlace, compress=self.compress,
            )

            def cb(done: int, total: int) -> None:
                if self._cancelled or self.isInterruptionRequested():
                    return
                pct = int(done / total * 100) if total else 0
                self.progress.emit(pct)
                self.log.emit(f"  Frame progress: {pct}%")

            self.log.emit(f"Starting encode ({self.fmt.upper()}, "
                          f"interlace={'ON' if self.interlace else 'OFF'}, "
                          f"compress={'ON' if self.compress else 'OFF'})...")
            ok = self.encoder.encode(self.input_file, self.output_file,
                                     progress_callback=cb)
            if self._cancelled:
                self.log.emit("Cancelled by user")
                self.finished.emit(False, "")
            elif ok:
                self.finished.emit(True, self.output_file)
            else:
                self.finished.emit(False, "")
        except Exception as e:
            if self._cancelled:
                self.finished.emit(False, "")
            else:
                self.error.emit(str(e))


class DecodeWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(bool)
    error = Signal(str)

    def __init__(
        self, video_file: str, output_dir: str,
        key: Optional[str], interlace: bool,
    ):
        super().__init__()
        self.video_file = video_file
        self.output_dir = output_dir
        self.key = key
        self.interlace = interlace
        self._cancelled = False
        self.decoder = None

    def cancel(self) -> None:
        self._cancelled = True
        if self.decoder is not None:
            try:
                self.decoder.cancel()
            except Exception:
                pass

    def run(self) -> None:
        try:
            from youtube_cloude.decoder import YouTubeDecoder

            self.decoder = YouTubeDecoder(self.key, interlace=self.interlace)

            def cb(done: int, total: int) -> None:
                if self._cancelled or self.isInterruptionRequested():
                    return
                pct = int(done / total * 100) if total else 0
                self.progress.emit(pct)
                self.log.emit(f"  Block progress: {pct}%")

            self.log.emit("Starting decode...")
            ok = self.decoder.decode(self.video_file, self.output_dir,
                                     progress_callback=cb)
            if self._cancelled:
                self.log.emit("Cancelled by user")
                self.finished.emit(False)
            else:
                self.finished.emit(ok)
        except Exception as e:
            if self._cancelled:
                self.finished.emit(False)
            else:
                self.error.emit(str(e))


# ── Responsive detection ────────────────────────────────────────────────
def is_mobile() -> bool:
    """Detect if running on a small screen (mobile/tablet)."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return False
    dpi = screen.logicalDotsPerInch()
    size = screen.availableGeometry()
    # < 7 inches or high DPI + small physical = mobile
    inches = ((size.width() ** 2 + size.height() ** 2) ** 0.5) / dpi
    return inches < 7.5 or (size.width() < 800 and dpi > 200)


# ── Page widgets ────────────────────────────────────────────────────────
class EncodePage(QWidget):
    """Encode file → video."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._worker: Optional[EncodeWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Title ──
        title = QLabel("Encode file to video")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(title)

        # ── Input file ──
        layout.addWidget(QLabel("Input file:"))
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select file to hide in video...")
        self.input_edit.setReadOnly(True)
        self.input_edit.textChanged.connect(self._auto_set_output)
        input_row.addWidget(self.input_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_input)
        input_row.addWidget(browse_btn)
        layout.addLayout(input_row)

        # ── Output video ──
        layout.addWidget(QLabel("Output video:"))
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setText("output.mp4")
        output_row.addWidget(self.output_edit)
        save_btn = QPushButton("Save as...")
        save_btn.setFixedWidth(90)
        save_btn.clicked.connect(self._browse_output)
        output_row.addWidget(save_btn)
        layout.addLayout(output_row)

        # ── Encode button ──
        self.encode_btn = QPushButton("▶  Encode")
        self.encode_btn.setObjectName("primary")
        self.encode_btn.setMinimumHeight(44)
        self.encode_btn.clicked.connect(self._start_encode)
        layout.addWidget(self.encode_btn)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # ── Log ──
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(120)
        layout.addWidget(self.log_area)

        layout.addStretch()

    def _auto_set_output(self, input_path: str) -> None:
        """Set output file to <input_dir>/<stem>.mp4 (without original ext)."""
        if not input_path.strip():
            return
        import os

        stem = os.path.splitext(os.path.basename(input_path))[0]
        if not stem:  # e.g. ".hidden" or no basename
            stem = os.path.basename(input_path)
        suggested = os.path.join(os.path.dirname(input_path), stem + ".mp4")
        self.output_edit.setText(suggested)

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select file to encode", "",
            "All files (*)",
        )
        if path:
            self.input_edit.setText(path)
            self._auto_set_output(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save video as", "output.mp4",
            "MP4 video (*.mp4)",
        )
        if path:
            self.output_edit.setText(path)

    def get_settings(self) -> dict:
        """Collect settings from SettingsPage (parent widget)."""
        win = self.window()
        if hasattr(win, 'settings_page'):
            sp = win.settings_page
            return {
                'format': sp.format_combo.currentData() or 'ytv1',
                'interlace': sp.interlace_check.isChecked(),
                'compress': sp.compress_check.isChecked(),
                'key': sp.key_edit.text().strip() or None,
            }
        return {'format': 'ytv1', 'interlace': False, 'compress': False, 'key': None}

    def _start_encode(self) -> None:
        # Toggle: if already running -> cancel
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.requestInterruption()
            self.encode_btn.setText("⏳  Cancelling...")
            self.encode_btn.setEnabled(False)
            self.log_area.append("Cancelling...")
            return

        input_file = self.input_edit.text().strip()
        output_file = self.output_edit.text().strip() or 'output.mp4'

        if not input_file:
            QMessageBox.warning(self, "Input needed",
                                "Please select a file to encode.")
            return

        settings = self.get_settings()

        self.encode_btn.setText("⏹  Stop")
        self.encode_btn.setEnabled(True)
        self.log_area.clear()
        self.progress.setValue(0)

        self._worker = EncodeWorker(
            input_file, output_file,
            settings['key'], settings['format'], settings['interlace'], settings['compress'],
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @Slot(int)
    def _on_progress(self, pct: int) -> None:
        self.progress.setValue(pct)

    @Slot(str)
    def _on_log(self, msg: str) -> None:
        self.log_area.append(msg)

    @Slot(bool, str)
    def _on_finished(self, ok: bool, path: str) -> None:
        self.encode_btn.setEnabled(True)
        self.encode_btn.setText("▶  Encode")
        is_cancel = self._worker is not None and getattr(self._worker, '_cancelled', False)
        if ok:
            self.log_area.append(f"\n✅ Done! Video saved to: {path}")
            QMessageBox.information(
                self, "Encode complete",
                f"Video saved to:\n{path}",
            )
        elif is_cancel:
            self.log_area.append("\n⏹ Cancelled.")
            self.progress.setValue(0)
        else:
            self.log_area.append("\n❌ Encoding failed.")
            QMessageBox.warning(self, "Failed", "Encoding failed. See log.")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        is_cancel = self._worker is not None and getattr(self._worker, '_cancelled', False)
        self.encode_btn.setEnabled(True)
        self.encode_btn.setText("▶  Encode")
        if is_cancel:
            self.log_area.append("\n⏹ Cancelled.")
            self.progress.setValue(0)
            return
        self.log_area.append(f"\n❌ Error: {msg}")
        QMessageBox.critical(self, "Error", msg)


class DecodePage(QWidget):
    """Decode video → file."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._worker: Optional[DecodeWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Decode video to file")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(title)

        # ── Video file ──
        layout.addWidget(QLabel("Video file:"))
        video_row = QHBoxLayout()
        self.video_edit = QLineEdit()
        self.video_edit.setPlaceholderText("Select video to decode...")
        self.video_edit.setReadOnly(True)
        video_row.addWidget(self.video_edit)
        browse_video = QPushButton("Browse...")
        browse_video.setFixedWidth(90)
        browse_video.clicked.connect(self._browse_video)
        video_row.addWidget(browse_video)
        layout.addLayout(video_row)

        # ── Output dir ──
        layout.addWidget(QLabel("Output directory:"))
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setText(".")
        dir_row.addWidget(self.dir_edit)
        browse_dir = QPushButton("Browse...")
        browse_dir.setFixedWidth(90)
        browse_dir.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_dir)
        layout.addLayout(dir_row)

        # ── Decode button ──
        self.decode_btn = QPushButton("▶  Decode")
        self.decode_btn.setObjectName("primary")
        self.decode_btn.setMinimumHeight(44)
        self.decode_btn.clicked.connect(self._start_decode)
        layout.addWidget(self.decode_btn)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # ── Log ──
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(120)
        layout.addWidget(self.log_area)

        layout.addStretch()

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video to decode", "",
            "MP4 video (*.mp4);;All files (*)",
        )
        if path:
            self.video_edit.setText(path)

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select output directory",
        )
        if path:
            self.dir_edit.setText(path)

    def _start_decode(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.requestInterruption()
            self.decode_btn.setText("⏳  Cancelling...")
            self.decode_btn.setEnabled(False)
            self.log_area.append("Cancelling...")
            return

        video_file = self.video_edit.text().strip()
        output_dir = self.dir_edit.text().strip() or '.'

        if not video_file:
            QMessageBox.warning(self, "Input needed",
                                "Please select a video to decode.")
            return

        win = self.window()
        key = None
        interlace = False
        if hasattr(win, 'settings_page'):
            sp = win.settings_page
            key = sp.key_edit.text().strip() or None
            interlace = sp.interlace_check.isChecked()

        self.decode_btn.setText("⏹  Stop")
        self.decode_btn.setEnabled(True)
        self.log_area.clear()
        self.progress.setValue(0)

        self._worker = DecodeWorker(video_file, output_dir, key, interlace)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @Slot(int)
    def _on_progress(self, pct: int) -> None:
        self.progress.setValue(pct)

    @Slot(str)
    def _on_log(self, msg: str) -> None:
        self.log_area.append(msg)

    @Slot(bool)
    def _on_finished(self, ok: bool) -> None:
        self.decode_btn.setEnabled(True)
        self.decode_btn.setText("▶  Decode")
        is_cancel = self._worker is not None and getattr(self._worker, '_cancelled', False)
        if ok:
            self.log_area.append("\n✅ Decode complete!")
            QMessageBox.information(self, "Done", "File recovered successfully.")
        elif is_cancel:
            self.log_area.append("\n⏹ Cancelled.")
            self.progress.setValue(0)
        else:
            self.log_area.append("\n⚠️ Decode finished with issues.")
            QMessageBox.warning(self, "Decode",
                                "Decode finished with issues. See log.")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        is_cancel = self._worker is not None and getattr(self._worker, '_cancelled', False)
        if is_cancel:
            self.decode_btn.setEnabled(True)
            self.decode_btn.setText("▶  Decode")
            self.log_area.append("\n⏹ Cancelled.")
            self.progress.setValue(0)
            return
        self.decode_btn.setEnabled(True)
        self.decode_btn.setText("▶  Decode")
        self.log_area.append(f"\n❌ Error: {msg}")
        QMessageBox.critical(self, "Error", msg)


class SettingsPage(QWidget):
    """Settings: format, interlace, encryption key."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(title)

        # ── Format ──
        fmt_group = QGroupBox("Video format")
        fmt_layout = QVBoxLayout(fmt_group)
        self.format_combo = QComboBox()
        self.format_combo.addItem("YTV1 — Standard (6 FPS, 2852 blocks/frame)", "ytv1")
        self.format_combo.addItem("YTV2 — Dense (15 FPS, 24244 blocks/frame)", "ytv2")
        self.format_combo.addItem("YTV3 — Resilient (30 FPS, RS + luma, yuv420p safe)", "ytv3")
        self.format_combo.setCurrentIndex(2)  # default YTV3
        fmt_layout.addWidget(self.format_combo)
        layout.addWidget(fmt_group)

        # ── Interlace ──
        self.interlace_check = QCheckBox("Interlace frames (improves YouTube retention)")
        self.interlace_check.setToolTip(
            "Encodes with lossless yuv444p to survive YouTube re-encoding.\n"
            "Produces ~20× larger video files. Use only when uploading to YouTube."
        )
        layout.addWidget(self.interlace_check)

        # ── Compression ──
        self.compress_check = QCheckBox("Compress with zlib before encoding")
        self.compress_check.setToolTip("Compress file with zlib before encoding.\nAuto-skipped if would enlarge. Saves huge space for text/logs.")
        layout.addWidget(self.compress_check)

        # ── FFmpeg ──
        ff_group = QGroupBox("FFmpeg (advanced)")
        ff_layout = QVBoxLayout(ff_group)
        ff_desc = QLabel("Custom ffmpeg/ffprobe binary. Leave blank to use bundled.")
        ff_desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        ff_layout.addWidget(ff_desc)
        ff_row = QHBoxLayout()
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setPlaceholderText("Path to ffmpeg.exe / ffmpeg (blank = bundled)")
        ff_row.addWidget(self.ffmpeg_edit)
        self.ffmpeg_browse_btn = QPushButton("Browse...")
        self.ffmpeg_browse_btn.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(self.ffmpeg_browse_btn)
        self.ffmpeg_reset_btn = QPushButton("Use bundled")
        self.ffmpeg_reset_btn.setToolTip("Clear and use bundled ffmpeg")
        self.ffmpeg_reset_btn.clicked.connect(self._reset_ffmpeg)
        ff_row.addWidget(self.ffmpeg_reset_btn)
        ff_layout.addLayout(ff_row)
        self.ffmpeg_status = QLabel("")
        self.ffmpeg_status.setStyleSheet("color: #8b949e; font-size: 11px;")
        ff_layout.addWidget(self.ffmpeg_status)
        self.ffmpeg_edit.textChanged.connect(self._on_ffmpeg_changed)
        layout.addWidget(ff_group)
        self._load_ffmpeg_setting()

        # ── Encryption ──
        enc_group = QGroupBox("Encryption (AES-256-GCM)")
        enc_layout = QVBoxLayout(enc_group)

        enc_layout.addWidget(QLabel("Encryption key (optional):"))
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Enter key or leave blank...")
        key_row.addWidget(self.key_edit)
        self.show_key_check = QCheckBox("Show")
        self.show_key_check.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_check)
        enc_layout.addLayout(key_row)

        enc_info = QLabel(
            "Key is hashed with SHA-256 before use.\n"
            "Leave blank to disable encryption."
        )
        enc_info.setStyleSheet("color: #8b949e; font-size: 12px;")
        enc_layout.addWidget(enc_info)
        layout.addWidget(enc_group)

        layout.addStretch()

        # ── Credits ──
        credits = QLabel(
            "Credits:\n"
            "  @Hinderchik  — original concept & security\n"
            "  @IvanSCP     — argparse CLI\n"
            "  @sosatel30000 — YTV2 format\n"
            "  @Maksim4081862 — GUI concepts\n"
            "  @Verdgil      — AES-256-CBC encryption"
        )
        credits.setStyleSheet("color: #484f58; font-size: 12px;")
        layout.addWidget(credits)

    def _load_ffmpeg_setting(self) -> None:
        s = QSettings("valeksan", "YouTube-Cloude")
        path = s.value("ffmpeg_path", "", type=str) or os.environ.get("YOUTUBE_CLOUDE_FFMPEG", "")
        if path:
            self.ffmpeg_edit.setText(path)
            self._apply_ffmpeg_path(path)
        else:
            self._update_ffmpeg_status()

    def _apply_ffmpeg_path(self, path: str) -> None:
        path = path.strip()
        s = QSettings("valeksan", "YouTube-Cloude")
        if path:
            s.setValue("ffmpeg_path", path)
            os.environ["YOUTUBE_CLOUDE_FFMPEG"] = path
            # derive ffprobe from same dir if not set separately
            p = os.path.dirname(path)
            probe = os.path.join(p, "ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
            if os.path.exists(probe):
                os.environ["YOUTUBE_CLOUDE_FFPROBE"] = probe
        else:
            s.remove("ffmpeg_path")
            os.environ.pop("YOUTUBE_CLOUDE_FFMPEG", None)
            os.environ.pop("YOUTUBE_CLOUDE_FFPROBE", None)
        self._update_ffmpeg_status()

    def _update_ffmpeg_status(self) -> None:
        path = self.ffmpeg_edit.text().strip()
        if not path:
            # check bundled
            try:
                from youtube_cloude.video_io import _find_ffmpeg
                found = _find_ffmpeg()
                self.ffmpeg_status.setText(f"Using: {found} (bundled/system)")
                self.ffmpeg_status.setStyleSheet("color: #3fb950; font-size: 11px;")
            except Exception as e:
                self.ffmpeg_status.setText(str(e))
                self.ffmpeg_status.setStyleSheet("color: #f85149; font-size: 11px;")
            return
        if os.path.exists(path):
            self.ffmpeg_status.setText(f"Using custom: {path}")
            self.ffmpeg_status.setStyleSheet("color: #58a6ff; font-size: 11px;")
        else:
            self.ffmpeg_status.setText("File not found")
            self.ffmpeg_status.setStyleSheet("color: #f85149; font-size: 11px;")

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg binary", "", "Executable (*.exe);;All files (*.*)")
        if path:
            self.ffmpeg_edit.setText(path)
            self._apply_ffmpeg_path(path)

    def _reset_ffmpeg(self) -> None:
        self.ffmpeg_edit.clear()
        self._apply_ffmpeg_path("")

    def _on_ffmpeg_changed(self, _text: str) -> None:
        # apply on change but don't spam; save on edit finish via apply
        self._apply_ffmpeg_path(self.ffmpeg_edit.text())

    @Slot(bool)
    def _toggle_key_visibility(self, checked: bool) -> None:
        mode = (QLineEdit.EchoMode.Normal if checked
                else QLineEdit.EchoMode.Password)
        self.key_edit.setEchoMode(mode)


class CameraPage(QWidget):
    """Camera capture — Android / desktop with camera."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Camera")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(title)

        info = QLabel(
            "Capture photo or video and encode data directly.\n\n"
            "Android: requires camera permission.\n"
            "Desktop: requires webcam."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #8b949e;")
        layout.addWidget(info)

        # Placeholder buttons
        self.capture_btn = QPushButton("📷  Capture Photo")
        self.capture_btn.setMinimumHeight(48)
        self.capture_btn.setEnabled(False)
        layout.addWidget(self.capture_btn)

        self.record_btn = QPushButton("🎬  Record Video")
        self.record_btn.setMinimumHeight(48)
        self.record_btn.setEnabled(False)
        layout.addWidget(self.record_btn)

        coming_soon = QLabel("Coming soon: camera integration via PySide6 QtMultimedia")
        coming_soon.setStyleSheet("color: #d29922; font-style: italic;")
        layout.addWidget(coming_soon)

        layout.addStretch()


# ── Main window ─────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Responsive main window with sidebar (desktop) or bottom nav (mobile)."""

    PAGES = {
        'encode': ('Encode', '▶'),
        'decode': ('Decode', '◀'),
        'settings': ('Settings', '⚙'),
        'camera': ('Camera', '📷'),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"YouTube-Cloude v{__version__}")
        self.setMinimumSize(400, 500)

        self._mobile = is_mobile()
        self._nav_buttons: list[QPushButton] = []
        self._current_page = 'encode'

        self._build_pages()

        if self._mobile:
            self._build_mobile_nav()
            self.resize(400, 700)
        else:
            self._build_sidebar()
            self.resize(820, 640)

    def _build_pages(self) -> None:
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.encode_page = EncodePage()
        self.decode_page = DecodePage()
        self.settings_page = SettingsPage()
        self.camera_page = CameraPage()

        self.stack.addWidget(self.encode_page)
        self.stack.addWidget(self.decode_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.camera_page)

        self.setCentralWidget(self.stack)

    def _build_sidebar(self) -> None:
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("QFrame { border-right: 1px solid #30363d; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 16, 8, 8)
        sidebar_layout.setSpacing(4)

        # Logo
        logo = QLabel("🎬 YouTube-Cloude")
        logo.setStyleSheet("font-size: 15px; font-weight: bold; color: #58a6ff; "
                           "padding: 8px;")
        sidebar_layout.addWidget(logo)

        sidebar_layout.addSpacing(12)

        for key, (label, icon) in self.PAGES.items():
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName("sideBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        version = QLabel(f"v{__version__}")
        version.setObjectName("version")
        sidebar_layout.addWidget(version)

        # Add sidebar to window
        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)
        self.setCentralWidget(container)

    def _build_mobile_nav(self) -> None:
        bottom_nav = QFrame()
        bottom_nav.setObjectName("bottomNav")
        bottom_nav.setFixedHeight(64)
        nav_layout = QHBoxLayout(bottom_nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        for key, (label, icon) in self.PAGES.items():
            btn = QPushButton(f"{icon}\n{label}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # Rebuild central widget
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stack)
        main_layout.addWidget(bottom_nav)
        self.setCentralWidget(container)

    def _switch_page(self, key: str) -> None:
        pages = [self.encode_page, self.decode_page,
                 self.settings_page, self.camera_page]
        keys = list(self.PAGES.keys())
        idx = keys.index(key)
        self.stack.setCurrentIndex(idx)
        self._current_page = key

        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == idx)


# ── Entry point ─────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    font = QFont()
    font.setPointSize(13)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
