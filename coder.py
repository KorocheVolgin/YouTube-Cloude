import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
import tempfile
import shutil
import re
import math
import cv2
import numpy as np
from collections import Counter

# ============================================================================
# YouTubeEncoder (из вашего скрипта)
# ============================================================================
class YouTubeEncoder:
    def __init__(self, key=None, progress_callback=None):
        self.width = 1920
        self.height = 1080
        self.fps = 6
        self.block_height = 16
        self.block_width = 24
        self.spacing = 4
        self.key = key
        self.use_encryption = key is not None
        self.progress_callback = progress_callback
        
        self.colors = {
            '0000': (255, 0, 0), '0001': (0, 255, 0), '0010': (0, 0, 255),
            '0011': (255, 255, 0), '0100': (255, 0, 255), '0101': (0, 255, 255),
            '0110': (255, 128, 0), '0111': (128, 0, 255), '1000': (0, 128, 128),
            '1001': (128, 128, 0), '1010': (128, 0, 128), '1011': (0, 128, 0),
            '1100': (128, 0, 0), '1101': (0, 0, 128), '1110': (192, 192, 192),
            '1111': (255, 255, 255)
        }
        
        self.marker_size = 80
        self.blocks_x = (self.width - 2*self.marker_size) // (self.block_width + self.spacing)
        self.blocks_y = (self.height - 2*self.marker_size) // (self.block_height + self.spacing)
        self.blocks_per_region = self.blocks_x * self.blocks_y
        self.blocks_per_frame = self.blocks_per_region * 3
        self.eof_marker = "█" * 64
        self.eof_bytes = self.eof_marker.encode('utf-8')

    def _encrypt_data(self, data):
        if not self.use_encryption:
            return data
        key_bytes = self.key.encode()
        result = bytearray()
        for i, byte in enumerate(data):
            key_byte = key_bytes[i % len(key_bytes)]
            result.append(byte ^ key_byte)
        return result

    def _draw_markers(self, frame):
        cv2.rectangle(frame, (0, 0), (self.marker_size, self.marker_size), (255, 255, 255), -1)
        cv2.rectangle(frame, (self.width-self.marker_size, 0), (self.width, self.marker_size), (255, 255, 255), -1)
        cv2.rectangle(frame, (0, self.height-self.marker_size), (self.marker_size, self.height), (255, 255, 255), -1)
        cv2.rectangle(frame, (self.width-self.marker_size, self.height-self.marker_size), (self.width, self.height), (255, 255, 255), -1)
        cv2.rectangle(frame, (0, 0), (self.marker_size, self.marker_size), (0, 0, 0), 2)
        cv2.rectangle(frame, (self.width-self.marker_size, 0), (self.width, self.marker_size), (0, 0, 0), 2)
        cv2.rectangle(frame, (0, self.height-self.marker_size), (self.marker_size, self.height), (0, 0, 0), 2)
        cv2.rectangle(frame, (self.width-self.marker_size, self.height-self.marker_size), (self.width, self.height), (0, 0, 0), 2)
        return frame

    def _draw_block(self, frame, x, y, color):
        x1 = self.marker_size + x * (self.block_width + self.spacing)
        y1 = self.marker_size + y * (self.block_height + self.spacing)
        x2 = x1 + self.block_width
        y2 = y1 + self.block_height
        if x2 > self.width - self.marker_size or y2 > self.height - self.marker_size:
            return False
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 1)
        return True

    def _bits_to_color(self, bits):
        while len(bits) < 4:
            bits = '0' + bits
        return self.colors.get(bits, (255, 0, 0))

    def _data_to_blocks(self, data):
        all_bits = []
        for byte in data:
            for i in range(7, -1, -1):
                all_bits.append(str((byte >> i) & 1))
        while len(all_bits) % 4 != 0:
            all_bits.append('0')
        blocks = [''.join(all_bits[i:i+4]) for i in range(0, len(all_bits), 4)]
        return blocks

    def encode(self, input_file, output_file):
        try:
            if self.progress_callback:
                self.progress_callback("📤 Чтение файла...", 5)
            
            with open(input_file, 'rb') as f:
                data = f.read()
            
            if self.progress_callback:
                self.progress_callback("🔐 Шифрование данных...", 10)
            
            if self.use_encryption:
                encrypted_data = self._encrypt_data(data)
            else:
                encrypted_data = data
            
            header = f"FILE:{os.path.basename(input_file)}:SIZE:{len(data)}|"
            header_bytes = header.encode('latin-1')
            
            header_blocks = self._data_to_blocks(header_bytes)
            data_blocks = self._data_to_blocks(encrypted_data)
            eof_blocks = self._data_to_blocks(self.eof_bytes)
            all_blocks = header_blocks + data_blocks + eof_blocks
            
            frames_needed = math.ceil(len(all_blocks) / self.blocks_per_region) + 5
            
            if self.progress_callback:
                self.progress_callback(f"🎬 Создание кадров: {frames_needed}...", 15)
            
            temp_dir = tempfile.mkdtemp()
            
            for frame_num in range(frames_needed - 5):
                if self.progress_callback and frame_num % 50 == 0:
                    progress = 15 + int((frame_num / (frames_needed - 5)) * 70)
                    self.progress_callback(f"🖼️  Кадр {frame_num + 1}/{frames_needed - 5}", progress)
                
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                frame = self._draw_markers(frame)
                
                start_idx = frame_num * self.blocks_per_region
                end_idx = min(start_idx + self.blocks_per_region, len(all_blocks))
                frame_blocks = all_blocks[start_idx:end_idx]
                
                for idx, bits in enumerate(frame_blocks):
                    y = idx // self.blocks_x
                    x = idx % self.blocks_x
                    if y < self.blocks_y:
                        color = self._bits_to_color(bits)
                        self._draw_block(frame, x, y, color)
                
                for idx, bits in enumerate(frame_blocks):
                    y = idx // self.blocks_x
                    x = idx % self.blocks_x + self.blocks_x
                    if x < self.blocks_x * 2 and y < self.blocks_y:
                        color = self._bits_to_color(bits)
                        self._draw_block(frame, x, y, color)
                
                for idx, bits in enumerate(frame_blocks):
                    y = idx // self.blocks_x + self.blocks_y
                    x = idx % self.blocks_x
                    if x < self.blocks_x and y < self.blocks_y * 2:
                        color = self._bits_to_color(bits)
                        self._draw_block(frame, x, y, color)
                
                frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
                cv2.imwrite(frame_file, frame)
            
            if self.progress_callback:
                self.progress_callback("🛡️  Создание защитных кадров...", 85)
            
            for i in range(5):
                frame_num = frames_needed - 5 + i
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                frame = self._draw_markers(frame)
                for y in range(self.blocks_y * 2):
                    for x in range(self.blocks_x * 2):
                        self._draw_block(frame, x, y, (255, 0, 0))
                frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
                cv2.imwrite(frame_file, frame)
            
            if self.progress_callback:
                self.progress_callback("🎞️  Конвертация в MP4...", 90)
            
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                cmd = [
                    'ffmpeg', '-framerate', str(self.fps),
                    '-i', os.path.join(temp_dir, 'frame_%05d.png'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
                    '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', '-y', output_file
                ]
                subprocess.run(cmd, check=True, capture_output=True)
            except:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_file, fourcc, self.fps, (self.width, self.height))
                for frame_num in range(frames_needed):
                    frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
                    frame = cv2.imread(frame_file)
                    if frame is not None:
                        out.write(frame)
                out.release()
            
            shutil.rmtree(temp_dir)
            
            if self.progress_callback:
                self.progress_callback("✅ Готово!", 100)
            
            return True
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"❌ Ошибка: {str(e)}", 0)
            return False

# ============================================================================
# YouTubeDecoder (из вашего скрипта)
# ============================================================================
class YouTubeDecoder:
    def __init__(self, key=None, progress_callback=None):
        self.width = 1920
        self.height = 1080
        self.block_height = 16
        self.block_width = 24
        self.spacing = 4
        self.marker_size = 80
        self.key = key
        self.progress_callback = progress_callback
        
        self.colors = {
            '0000': (255, 0, 0), '0001': (0, 255, 0), '0010': (0, 0, 255),
            '0011': (255, 255, 0), '0100': (255, 0, 255), '0101': (0, 255, 255),
            '0110': (255, 128, 0), '0111': (128, 0, 255), '1000': (0, 128, 128),
            '1001': (128, 128, 0), '1010': (128, 0, 128), '1011': (0, 128, 0),
            '1100': (128, 0, 0), '1101': (0, 0, 128), '1110': (192, 192, 192),
            '1111': (255, 255, 255)
        }
        
        self.color_values = np.array(list(self.colors.values()), dtype=np.int32)
        self.color_keys = list(self.colors.keys())
        self.color_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        self.blocks_x = (self.width - 2*self.marker_size) // (self.block_width + self.spacing)
        self.blocks_y = (self.height - 2*self.marker_size) // (self.block_height + self.spacing)
        self.blocks_per_region = self.blocks_x * self.blocks_y
        self._precompute_coordinates()

    def _precompute_coordinates(self):
        self.block_coords = []
        for idx in range(self.blocks_per_region):
            y = idx // self.blocks_x
            x = idx % self.blocks_x
            if y < self.blocks_y:
                cx = self.marker_size + x * (self.block_width + self.spacing) + self.block_width // 2
                cy = self.marker_size + y * (self.block_height + self.spacing) + self.block_height // 2
                self.block_coords.append((cx, cy))

    def _decrypt_data(self, data):
        if not self.key:
            return data
        key_bytes = self.key.encode()
        result = bytearray()
        for i, byte in enumerate(data):
            key_byte = key_bytes[i % len(key_bytes)]
            result.append(byte ^ key_byte)
        return result

    def _color_to_bits_fast(self, color):
        color_key = (color[0], color[1], color[2])
        if color_key in self.color_cache:
            self.cache_hits += 1
            return self.color_cache[color_key]
        self.cache_misses += 1
        if color[0] > 200 and color[1] < 50 and color[2] < 50:
            self.color_cache[color_key] = '0000'
            return '0000'
        color_arr = np.array([color[0], color[1], color[2]], dtype=np.int32)
        distances = np.sum((self.color_values - color_arr) ** 2, axis=1)
        best_idx = np.argmin(distances)
        result = self.color_keys[best_idx]
        self.color_cache[color_key] = result
        return result

    def decode_frame_fast(self, frame):
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_NEAREST)
        blocks = []
        h, w = frame.shape[:2]
        for cx, cy in self.block_coords:
            if cx < w and cy < h:
                color = frame[cy, cx]
                bits = self._color_to_bits_fast(color)
                blocks.append(bits)
            else:
                blocks.append('0000')
        return blocks

    def _blocks_to_bytes(self, blocks):
        all_bits = ''.join(blocks)
        bytes_data = bytearray()
        for i in range(0, len(all_bits) - 7, 8):
            byte_str = all_bits[i:i+8]
            if len(byte_str) == 8:
                try:
                    byte = int(byte_str, 2)
                    bytes_data.append(byte)
                except:
                    bytes_data.append(0)
        return bytes_data

    def _find_eof_marker(self, data):
        eof_bytes = b'\xe2\x96\x88' * 64
        for i in range(len(data) - len(eof_bytes)):
            if data[i:i+len(eof_bytes)] == eof_bytes:
                return i
        return -1

    def decode(self, video_file, output_dir='.'):
        try:
            if self.progress_callback:
                self.progress_callback("📥 Открытие видео...", 5)
            
            if not os.path.exists(video_file):
                if self.progress_callback:
                    self.progress_callback("❌ Файл не найден", 0)
                return False
            
            cap = cv2.VideoCapture(video_file)
            if not cap.isOpened():
                if self.progress_callback:
                    self.progress_callback("❌ Не удалось открыть видео", 0)
                return False
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if self.progress_callback:
                self.progress_callback(f"📹 Всего кадров: {total_frames}", 10)
            
            all_blocks = []
            frames_processed = 0
            
            for frame_num in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    break
                frames_processed += 1
                
                if self.progress_callback and frame_num % 50 == 0:
                    progress = 10 + int((frame_num / total_frames) * 80)
                    self.progress_callback(f"🔄 Обработка: {frame_num}/{total_frames}", progress)
                
                frame_blocks = self.decode_frame_fast(frame)
                all_blocks.extend(frame_blocks)
            
            cap.release()
            
            if self.progress_callback:
                self.progress_callback("📦 Конвертация в байты...", 90)
            
            bytes_data = self._blocks_to_bytes(all_blocks)
            
            eof_pos = self._find_eof_marker(bytes_data)
            if eof_pos > 0:
                bytes_data = bytes_data[:eof_pos]
            
            data_str = bytes_data[:1000].decode('latin-1', errors='ignore')
            pattern = r'FILE:([^:]+):SIZE:(\d+)\|'
            match = re.search(pattern, data_str)
            
            if self.progress_callback:
                self.progress_callback("💾 Сохранение файла...", 95)
            
            if match:
                filename = match.group(1)
                filesize = int(match.group(2))
                header_str = match.group(0)
                header_bytes = header_str.encode('latin-1')
                header_pos = bytes_data.find(header_bytes)
                
                if header_pos >= 0:
                    encrypted_data = bytes_data[header_pos + len(header_bytes):header_pos + len(header_bytes) + filesize]
                    
                    if self.key:
                        file_data = self._decrypt_data(encrypted_data)
                    else:
                        file_data = encrypted_data
                    
                    output_path = os.path.join(output_dir, filename)
                    counter = 1
                    base, ext = os.path.splitext(filename)
                    while os.path.exists(output_path):
                        output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
                        counter += 1
                    
                    with open(output_path, 'wb') as f:
                        f.write(file_data)
                    
                    if self.progress_callback:
                        self.progress_callback("✅ Готово!", 100)
                    
                    return output_path
            else:
                output_path = os.path.join(output_dir, "decoded_data.bin")
                with open(output_path, 'wb') as f:
                    f.write(bytes_data)
                if self.progress_callback:
                    self.progress_callback("✅ Данные сохранены (без заголовка)", 100)
                return output_path
            
            return False
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"❌ Ошибка: {str(e)}", 0)
            return False

# ============================================================================
# GUI Приложение
# ============================================================================
class YouTubeCloudGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 YouTube-Cloud-GUI")
        self.root.geometry("750x700")
        self.root.resizable(True, True)
        
        # Переменные
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.output_dir = tk.StringVar(value=".")
        self.encryption_key = tk.StringVar()
        self.use_encryption = tk.BooleanVar(value=False)
        self.is_processing = False
        
        # Общий лог для всех операций
        self.log_messages = []
        
        self._create_widgets()
        self._load_key_from_file()
    
    def _create_widgets(self):
        # Заголовок
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        title_label = ttk.Label(title_frame, text="🎬 YouTube-Cloud-GUI", 
                               font=("Helvetica", 18, "bold"), foreground="#2196F3")
        title_label.pack()
        
        subtitle_label = ttk.Label(title_frame, text="Кодирование файлов в видео и обратно через YouTube",
                                  font=("Helvetica", 10))
        subtitle_label.pack()
        
        # Вкладки
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка кодирования
        encode_frame = ttk.Frame(notebook, padding="10")
        notebook.add(encode_frame, text="📤 Кодирование")
        self._create_encode_tab(encode_frame)
        
        # Вкладка декодирования
        decode_frame = ttk.Frame(notebook, padding="10")
        notebook.add(decode_frame, text="📥 Декодирование")
        self._create_decode_tab(decode_frame)
        
        # Вкладка логов (НОВАЯ)
        log_frame = ttk.Frame(notebook, padding="10")
        notebook.add(log_frame, text="📋 Логи")
        self._create_log_tab(log_frame)
        
        # Вкладка информации
        info_frame = ttk.Frame(notebook, padding="10")
        notebook.add(info_frame, text="ℹ️ Информация")
        self._create_info_tab(info_frame)
        
        # Прогресс бар
        self.progress_frame = ttk.Frame(self.root, padding="10")
        self.progress_frame.pack(fill=tk.X)
        
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, 
                                           maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(self.progress_frame, text="Готов к работе", 
                                     font=("Helvetica", 10))
        self.status_label.pack()
    
    def _create_encode_tab(self, parent):
        # Выбор файла
        file_frame = ttk.LabelFrame(parent, text="Файл для кодирования", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="Исходный файл:").pack(anchor=tk.W)
        
        file_entry = ttk.Entry(file_frame, textvariable=self.input_file, width=60)
        file_entry.pack(fill=tk.X, pady=5)
        
        file_btn_frame = ttk.Frame(file_frame)
        file_btn_frame.pack(fill=tk.X)
        
        ttk.Button(file_btn_frame, text="📁 Выбрать файл", 
                  command=self._browse_input_file).pack(side=tk.LEFT, padx=5)
        
        # Выходной файл
        ttk.Label(file_frame, text="Выходное видео:").pack(anchor=tk.W, pady=(10, 0))
        
        output_entry = ttk.Entry(file_frame, textvariable=self.output_file, width=60)
        output_entry.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_btn_frame, text="📁 Выбрать место...", 
                  command=self._browse_output_file).pack(side=tk.LEFT, padx=5)
        
        # Шифрование
        encrypt_frame = ttk.LabelFrame(parent, text="Шифрование", padding="10")
        encrypt_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(encrypt_frame, text="Включить шифрование (XOR)", 
                       variable=self.use_encryption, 
                       command=self._toggle_encryption).pack(anchor=tk.W)
        
        self.key_frame = ttk.Frame(encrypt_frame)
        self.key_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.key_frame, text="Ключ шифрования:").pack(anchor=tk.W)
        
        key_entry = ttk.Entry(self.key_frame, textvariable=self.encryption_key, 
                             width=60, show="*")
        key_entry.pack(fill=tk.X, pady=5)
        
        ttk.Button(self.key_frame, text="💾 Сохранить ключ в key.txt", 
                  command=self._save_key_to_file).pack(anchor=tk.W)
        
        self.key_frame.state(['disabled'])
        
        # Кнопка запуска
        self.encode_btn = ttk.Button(parent, text="🎬 Начать кодирование", 
                                    command=self._start_encoding, 
                                    style="Accent.TButton")
        self.encode_btn.pack(pady=20)
        
        # Краткий статус (без лога)
        status_frame = ttk.LabelFrame(parent, text="Статус операции", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        self.encode_status = ttk.Label(status_frame, text="Ожидание запуска...", 
                                      font=("Helvetica", 9), foreground="gray")
        self.encode_status.pack(anchor=tk.W)
    
    def _create_decode_tab(self, parent):
        # Выбор видео
        video_frame = ttk.LabelFrame(parent, text="Видео для декодирования", padding="10")
        video_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(video_frame, text="Видео файл:").pack(anchor=tk.W)
        
        self.decode_input = ttk.Entry(video_frame, width=60)
        self.decode_input.pack(fill=tk.X, pady=5)
        
        btn_frame = ttk.Frame(video_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="📁 Выбрать видео", 
                  command=self._browse_decode_input).pack(side=tk.LEFT, padx=5)
        
        # Папка вывода
        ttk.Label(video_frame, text="Папка для сохранения:").pack(anchor=tk.W, pady=(10, 0))
        
        self.decode_output = ttk.Entry(video_frame, textvariable=self.output_dir, width=60)
        self.decode_output.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="📁 Выбрать папку...", 
                  command=self._browse_output_dir).pack(side=tk.LEFT, padx=5)
        
        # Ключ расшифровки
        decrypt_frame = ttk.LabelFrame(parent, text="Ключ расшифровки", padding="10")
        decrypt_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(decrypt_frame, text="Ключ (если файл был зашифрован):").pack(anchor=tk.W)
        
        self.decode_key = ttk.Entry(decrypt_frame, width=60, show="*")
        self.decode_key.pack(fill=tk.X, pady=5)
        
        ttk.Button(decrypt_frame, text="📄 Загрузить из key.txt", 
                  command=self._load_key_from_file).pack(anchor=tk.W)
        
        # Кнопка запуска
        self.decode_btn = ttk.Button(parent, text="📥 Начать декодирование", 
                                    command=self._start_decoding,
                                    style="Accent.TButton")
        self.decode_btn.pack(pady=20)
        
        # Краткий статус (без лога)
        status_frame = ttk.LabelFrame(parent, text="Статус операции", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        self.decode_status = ttk.Label(status_frame, text="Ожидание запуска...", 
                                      font=("Helvetica", 9), foreground="gray")
        self.decode_status.pack(anchor=tk.W)
    
    def _create_log_tab(self, parent):
        # Панель управления логами
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="🗑️ Очистить лог", 
                  command=self._clear_log).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="💾 Сохранить лог в файл", 
                  command=self._save_log).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="📋 Копировать", 
                  command=self._copy_log).pack(side=tk.LEFT, padx=5)
        
        self.log_count_label = ttk.Label(control_frame, text="Записей: 0", 
                                        font=("Helvetica", 9))
        self.log_count_label.pack(side=tk.RIGHT)
        
        # Основное поле лога
        log_frame = ttk.LabelFrame(parent, text="Журнал операций", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.main_log = scrolledtext.ScrolledText(log_frame, height=20, state='disabled',
                                                  font=("Consolas", 9))
        self.main_log.pack(fill=tk.BOTH, expand=True)
        
        # Настройка тегов для цветов
        self.main_log.tag_config("info", foreground="blue")
        self.main_log.tag_config("success", foreground="green")
        self.main_log.tag_config("warning", foreground="orange")
        self.main_log.tag_config("error", foreground="red")
        self.main_log.tag_config("progress", foreground="gray")
    
    def _create_info_tab(self, parent):
        info_text = """
🎬 YouTube-Cloud-GUI

Как это работает:
• Файлы кодируются в последовательность цветных блоков
• Каждый блок представляет 4 бита данных (16 цветов)
• Видео загружается на YouTube как обычное видео
• При скачивании данные декодируются обратно в файл

Технические параметры:
• Разрешение: 1920x1080 (Full HD)
• FPS: 6 кадров в секунду
• Ёмкость: ~1.5 КБ данных на кадр
• Формат: MP4 (H.264)

Преимущества:
✅ Условно бесконечное хранилище
✅ Файлы любого типа (exe, zip, и т.д.)
✅ Шифрование данных
✅ Восстановление без потерь

Ограничения:
⚠️ Требует много времени на кодирование
⚠️ Большие файлы = длинное видео
⚠️ Риск блокировки аккаунта YouTube
⚠️ Нужен стабильный интернет

Рекомендации:
• Используйте для не критичных данных
• Делайте резервные копии
• Проверяйте файлы после декодирования
• Не нарушайте условия использования YouTube

Вкладка "Логи":
• Все операции записываются в общий журнал
• Можно очистить, сохранить или скопировать лог
• Цветовая индикация типов сообщений
        """
        
        info_label = ttk.Label(parent, text=info_text, justify=tk.LEFT, 
                              font=("Consolas", 9))
        info_label.pack(anchor=tk.W)
    
    def _browse_input_file(self):
        filename = filedialog.askopenfilename(title="Выберите файл для кодирования")
        if filename:
            self.input_file.set(filename)
            if not self.output_file.get():
                base, _ = os.path.splitext(filename)
                self.output_file.set(base + "_encoded.mp4")
    
    def _browse_output_file(self):
        filename = filedialog.asksaveasfilename(title="Сохранить видео как", 
                                                defaultextension=".mp4",
                                                filetypes=[("MP4 files", "*.mp4")])
        if filename:
            self.output_file.set(filename)
    
    def _browse_decode_input(self):
        filename = filedialog.askopenfilename(title="Выберите видео для декодирования",
                                              filetypes=[("MP4 files", "*.mp4"), 
                                                        ("All files", "*.*")])
        if filename:
            self.decode_input.delete(0, tk.END)
            self.decode_input.insert(0, filename)
    
    def _browse_output_dir(self):
        directory = filedialog.askdirectory(title="Выберите папку для сохранения")
        if directory:
            self.output_dir.set(directory)
    
    def _toggle_encryption(self):
        if self.use_encryption.get():
            self.key_frame.state(['!disabled'])
        else:
            self.key_frame.state(['disabled'])
    
    def _save_key_to_file(self):
        key = self.encryption_key.get()
        if key:
            try:
                with open('key.txt', 'w', encoding='utf-8') as f:
                    f.write(key)
                self._log("🔑 Ключ сохранён в key.txt", "success")
                messagebox.showinfo("Успешно", "Ключ сохранён в key.txt")
            except Exception as e:
                self._log(f"❌ Ошибка сохранения ключа: {e}", "error")
                messagebox.showerror("Ошибка", f"Не удалось сохранить ключ: {e}")
        else:
            messagebox.showwarning("Внимание", "Введите ключ шифрования")
    
    def _load_key_from_file(self):
        try:
            if os.path.exists('key.txt'):
                with open('key.txt', 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                if key:
                    self.encryption_key.set(key)
                    self.decode_key.delete(0, tk.END)
                    self.decode_key.insert(0, key)
                    self._log("🔑 Ключ загружен из key.txt", "info")
                    return True
            self._log("ℹ️ key.txt не найден", "warning")
            return False
        except Exception as e:
            self._log(f"⚠️ Ошибка загрузки ключа: {e}", "error")
            return False
    
    def _log(self, message, tag="info"):
        """Добавляет запись в общий лог"""
        self.log_messages.append(f"[{tag.upper()}] {message}")
        
        self.main_log.config(state='normal')
        timestamp = f"[{tk.StringVar().set()}]" if False else ""
        self.main_log.insert(tk.END, f"{message}\n", tag)
        self.main_log.see(tk.END)
        self.main_log.config(state='disabled')
        
        # Обновляем счётчик
        self.log_count_label.config(text=f"Записей: {len(self.log_messages)}")
    
    def _clear_log(self):
        """Очищает лог"""
        self.log_messages.clear()
        self.main_log.config(state='normal')
        self.main_log.delete(1.0, tk.END)
        self.main_log.config(state='disabled')
        self.log_count_label.config(text="Записей: 0")
        self._log("🗑️ Лог очищен", "info")
    
    def _save_log(self):
        """Сохраняет лог в файл"""
        if not self.log_messages:
            messagebox.showwarning("Внимание", "Лог пуст")
            return
        
        filename = filedialog.asksaveasfilename(title="Сохранить лог как",
                                                defaultextension=".txt",
                                                filetypes=[("Text files", "*.txt")])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(self.log_messages))
                self._log(f"💾 Лог сохранён: {filename}", "success")
                messagebox.showinfo("Успешно", f"Лог сохранён:\n{filename}")
            except Exception as e:
                self._log(f"❌ Ошибка сохранения лога: {e}", "error")
                messagebox.showerror("Ошибка", f"Не удалось сохранить лог: {e}")
    
    def _copy_log(self):
        """Копирует лог в буфер обмена"""
        if not self.log_messages:
            messagebox.showwarning("Внимание", "Лог пуст")
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(self.log_messages))
        self._log("📋 Лог скопирован в буфер обмена", "info")
        messagebox.showinfo("Успешно", "Лог скопирован в буфер обмена")
    
    def _update_progress(self, message, value):
        self.status_label.config(text=message)
        self.progress_var.set(value)
        self.root.update_idletasks()
        
        # Также пишем в лог
        if "Ошибка" in message or "❌" in message:
            self._log(message, "error")
        elif "Готово" in message or "✅" in message:
            self._log(message, "success")
        elif value < 100:
            self._log(message, "progress")
    
    def _start_encoding(self):
        if self.is_processing:
            messagebox.showwarning("Внимание", "Операция уже выполняется")
            return
        
        input_file = self.input_file.get()
        output_file = self.output_file.get()
        
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Ошибка", "Выберите корректный исходный файл")
            return
        
        if not output_file:
            messagebox.showerror("Ошибка", "Укажите путь для выходного файла")
            return
        
        self.is_processing = True
        self.encode_btn.config(state='disabled')
        self.encode_status.config(text="⏳ Кодирование запущено...", foreground="blue")
        
        self._log(f"📤 Начало кодирования: {os.path.basename(input_file)}", "info")
        
        key = self.encryption_key.get() if self.use_encryption.get() else None
        
        thread = threading.Thread(target=self._encoding_thread, 
                                 args=(input_file, output_file, key))
        thread.daemon = True
        thread.start()
    
    def _encoding_thread(self, input_file, output_file, key):
        def progress_callback(message, value):
            self.root.after(0, self._update_progress, message, value)
        
        encoder = YouTubeEncoder(key=key, progress_callback=progress_callback)
        success = encoder.encode(input_file, output_file)
        
        self.root.after(0, self._encoding_complete, success, output_file)
    
    def _encoding_complete(self, success, output_file):
        self.is_processing = False
        self.encode_btn.config(state='normal')
        
        if success:
            size = os.path.getsize(output_file) / 1024 / 1024
            self.encode_status.config(text="✅ Кодирование завершено", foreground="green")
            self._log(f"✅ Файл закодирован: {output_file} ({size:.2f} MB)", "success")
            messagebox.showinfo("Успешно", 
                               f"Файл закодирован!\n\n📁 {output_file}\n📊 Размер: {size:.2f} MB")
        else:
            self.encode_status.config(text="❌ Ошибка кодирования", foreground="red")
            self._log("❌ Ошибка кодирования файла", "error")
            messagebox.showerror("Ошибка", "Не удалось закодировать файл")
    
    def _start_decoding(self):
        if self.is_processing:
            messagebox.showwarning("Внимание", "Операция уже выполняется")
            return
        
        video_file = self.decode_input.get()
        output_dir = self.output_dir.get()
        
        if not video_file or not os.path.exists(video_file):
            messagebox.showerror("Ошибка", "Выберите корректный видео файл")
            return
        
        self.is_processing = True
        self.decode_btn.config(state='disabled')
        self.decode_status.config(text="⏳ Декодирование запущено...", foreground="blue")
        
        self._log(f"📥 Начало декодирования: {os.path.basename(video_file)}", "info")
        
        key = self.decode_key.get() if self.decode_key.get() else None
        
        thread = threading.Thread(target=self._decoding_thread, 
                                 args=(video_file, output_dir, key))
        thread.daemon = True
        thread.start()
    
    def _decoding_thread(self, video_file, output_dir, key):
        def progress_callback(message, value):
            self.root.after(0, self._update_progress, message, value)
        
        decoder = YouTubeDecoder(key=key, progress_callback=progress_callback)
        result = decoder.decode(video_file, output_dir)
        
        self.root.after(0, self._decoding_complete, result)
    
    def _decoding_complete(self, result):
        self.is_processing = False
        self.decode_btn.config(state='normal')
        
        if result:
            self.decode_status.config(text="✅ Декодирование завершено", foreground="green")
            self._log(f"✅ Файл восстановлен: {result}", "success")
            messagebox.showinfo("Успешно", 
                               f"Файл восстановлен!\n\n📁 {result}")
        else:
            self.decode_status.config(text="❌ Ошибка декодирования", foreground="red")
            self._log("❌ Ошибка декодирования видео", "error")
            messagebox.showerror("Ошибка", "Не удалось декодировать видео")

# ============================================================================
# Запуск приложения
# ============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    
    # Стили
    style = ttk.Style()
    style.theme_use('clam')
    
    # Цвета
    style.configure("Accent.TButton", foreground="white", background="#2196F3", 
                   font=("Helvetica", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#1976D2")])
    
    app = YouTubeCloudGUI(root)
    root.mainloop()
