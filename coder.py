# youtube_storage_fixed.py
import hashlib
import os
import math
import subprocess
import tempfile
import shutil
import sys
import re

import cv2
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class YouTubeEncoder:
    def __init__(self, key=None):
        self.width = 1920
        self.height = 1080
        self.fps = 6  # ИЗМЕНЕНО: теперь 6 кадров в секунду
        
        # Параметры
        self.block_height = 16
        self.block_width = 24
        self.spacing = 4
        
        # Ключ шифрования
        self.key = key
        self.iv = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        self.use_encryption = key is not None
        
        # 16 цветов
        self.colors = {
            '0000': (255, 0, 0),      # Ярко-синий
            '0001': (0, 255, 0),      # Ярко-зеленый
            '0010': (0, 0, 255),      # Ярко-красный
            '0011': (255, 255, 0),    # Желтый
            '0100': (255, 0, 255),    # Пурпурный
            '0101': (0, 255, 255),    # Голубой
            '0110': (255, 128, 0),    # Оранжевый
            '0111': (128, 0, 255),    # Фиолетовый
            '1000': (0, 128, 128),    # Бирюзовый
            '1001': (128, 128, 0),    # Оливковый
            '1010': (128, 0, 128),    # Темно-пурпурный
            '1011': (0, 128, 0),      # Темно-зеленый
            '1100': (128, 0, 0),      # Бордовый
            '1101': (0, 0, 128),      # Темно-синий
            '1110': (192, 192, 192),  # Светло-серый
            '1111': (255, 255, 255)   # Белый
        }
        
        # Маркеры по углам
        self.marker_size = 80
        
        # Расчет сетки
        self.blocks_x = (self.width - 2*self.marker_size) // (self.block_width + self.spacing)
        self.blocks_y = (self.height - 2*self.marker_size) // (self.block_height + self.spacing)
        self.blocks_per_region = self.blocks_x * self.blocks_y
        self.blocks_per_frame = self.blocks_per_region * 3
        
        # Маркер конца
        self.eof_marker = "█" * 64
        self.eof_bytes = self.eof_marker.encode('utf-8')
        
        print("="*60)
        print("🎬 КОДИРОВЩИК YouTube (6 FPS)")
        print("="*60)
        print(f"📊 Сетка: {self.blocks_x} x {self.blocks_y} блоков на регион")
        print(f"🎞️  FPS: {self.fps}")
        print(f"🔐 Шифрование: {'ВКЛ' if self.use_encryption else 'ВЫКЛ'}")
    
    def _encrypt_data(self, data):
        """AES шифрование с ключом"""
        if not self.use_encryption:
            return data

        key = hashlib.sha256(self.key.encode()).digest()
        cipher = AES.new(key, AES.MODE_CBC, self.iv.encode())
        padded_plaintext = pad(data, AES.block_size)
        ciphertext = cipher.encrypt(padded_plaintext)
        return ciphertext
    
    def _draw_markers(self, frame):
        """Рисует маркеры по углам"""
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
        """Рисует один блок"""
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
        """4 бита -> цвет"""
        while len(bits) < 4:
            bits = '0' + bits
        return self.colors.get(bits, (255, 0, 0))
    
    def _data_to_blocks(self, data):
        """Конвертирует данные в 4-битные блоки"""
        all_bits = []
        for byte in data:
            for i in range(7, -1, -1):
                all_bits.append(str((byte >> i) & 1))
        
        while len(all_bits) % 4 != 0:
            all_bits.append('0')
        
        blocks = [''.join(all_bits[i:i+4]) for i in range(0, len(all_bits), 4)]
        return blocks
    
    def encode(self, input_file, output_file):
        """Кодирует файл в видео с опциональным шифрованием"""
        
        print("\n📤 КОДИРОВАНИЕ ФАЙЛА")
        print("-" * 40)
        
        # Читаем файл
        with open(input_file, 'rb') as f:
            data = f.read()
        
        print(f"📄 Файл: {input_file}")
        print(f"📦 Размер: {len(data)} байт")
        
        # Шифруем данные если нужно
        if self.use_encryption:
            encrypted_data = self._encrypt_data(data)
            print(f"🔐 Данные зашифрованы")
        else:
            encrypted_data = data
        
        # Создаем заголовок
        header = (
            f"FILE:{os.path.basename(input_file)}:"
            f"SIZE:{len(data)}:"
            f"ENCRYPTED_SIZE:{len(encrypted_data)}:"
            f"IV:{self.iv}|"
        )
        header_bytes = header.encode('latin-1')
        print(f"📋 Заголовок: {header}")
        
        # Конвертируем в блоки
        header_blocks = self._data_to_blocks(header_bytes)
        data_blocks = self._data_to_blocks(encrypted_data)
        eof_blocks = self._data_to_blocks(self.eof_bytes)
        all_blocks = header_blocks + data_blocks + eof_blocks
        
        print(f"🎨 Всего блоков: {len(all_blocks)}")
        print(f"🏁 Маркер конца: {len(eof_blocks)} блоков")
        
        # Рассчитываем количество кадров
        frames_needed = math.ceil(len(all_blocks) / self.blocks_per_region)
        # Добавляем 5 защитных кадров
        frames_needed += 5
        print(f"🎬 Требуется кадров: {frames_needed}")
        print(f"⏱️  Длительность видео: {frames_needed/self.fps:.1f} сек")
        
        # Создаем временную папку
        temp_dir = tempfile.mkdtemp()
        print(f"📁 Временная папка: {temp_dir}")
        
        # Создаем кадры
        for frame_num in range(frames_needed - 5):
            print(f"\n🖼️  Кадр {frame_num + 1}/{frames_needed}")
            
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frame = self._draw_markers(frame)
            
            start_idx = frame_num * self.blocks_per_region
            end_idx = min(start_idx + self.blocks_per_region, len(all_blocks))
            frame_blocks = all_blocks[start_idx:end_idx]
            
            # Основные блоки
            for idx, bits in enumerate(frame_blocks):
                y = idx // self.blocks_x
                x = idx % self.blocks_x
                if y < self.blocks_y:
                    color = self._bits_to_color(bits)
                    self._draw_block(frame, x, y, color)
            
            # Резерв 1
            for idx, bits in enumerate(frame_blocks):
                y = idx // self.blocks_x
                x = idx % self.blocks_x + self.blocks_x
                if x < self.blocks_x * 2 and y < self.blocks_y:
                    color = self._bits_to_color(bits)
                    self._draw_block(frame, x, y, color)
            
            # Резерв 2
            for idx, bits in enumerate(frame_blocks):
                y = idx // self.blocks_x + self.blocks_y
                x = idx % self.blocks_x
                if x < self.blocks_x and y < self.blocks_y * 2:
                    color = self._bits_to_color(bits)
                    self._draw_block(frame, x, y, color)
            
            # Сохраняем кадр
            frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
            cv2.imwrite(frame_file, frame)
        
        # Создаем защитные кадры (синий фон)
        print("\n🛡️  Создание защитных кадров...")
        for i in range(5):
            frame_num = frames_needed - 5 + i
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frame = self._draw_markers(frame)
            for y in range(self.blocks_y * 2):
                for x in range(self.blocks_x * 2):
                    self._draw_block(frame, x, y, (255, 0, 0))
            frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
            cv2.imwrite(frame_file, frame)
            print(f"  🟦 Защитный кадр {i+1}/5")
        
        # Конвертируем в MP4
        print("\n🎞️  Конвертация в MP4...")
        
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            
            cmd = [
                'ffmpeg',
                '-framerate', str(self.fps),
                '-i', os.path.join(temp_dir, 'frame_%05d.png'),
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-an',
                '-movflags', '+faststart',
                '-y',
                output_file
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            print("✅ FFmpeg конвертация успешна")
            
        except Exception as e:
            print(f"⚠️ FFmpeg не доступен, использую OpenCV...")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_file, fourcc, self.fps, (self.width, self.height))
            
            for frame_num in range(frames_needed):
                frame_file = os.path.join(temp_dir, f"frame_{frame_num:05d}.png")
                frame = cv2.imread(frame_file)
                if frame is not None:
                    out.write(frame)
            out.release()
        
        # Удаляем временные файлы
        shutil.rmtree(temp_dir)
        print("🧹 Временные файлы удалены")
        
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"\n✅ Видео сохранено: {output_file}")
            print(f"📊 Размер: {size} байт ({size/1024/1024:.2f} MB)")
            print(f"🎬 Кадров: {frames_needed}")
            print(f"⏱️  Длительность: {frames_needed/self.fps:.1f} сек")
            return True
        return False


class YouTubeDecoder:
    def __init__(self, key=None, iv=None):
        self.width = 1920
        self.height = 1080
        self.block_height = 16
        self.block_width = 24
        self.spacing = 4
        self.marker_size = 80
        
        # Ключ шифрования
        self.key = key
        self.iv = iv
        
        # 16 цветов
        self.colors = {
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
            '1111': (255, 255, 255)
        }
        
        # Оптимизации
        self.color_values = np.array(list(self.colors.values()), dtype=np.int32)
        self.color_keys = list(self.colors.keys())
        self.color_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Расчет сетки
        self.blocks_x = (self.width - 2*self.marker_size) // (self.block_width + self.spacing)
        self.blocks_y = (self.height - 2*self.marker_size) // (self.block_height + self.spacing)
        self.blocks_per_region = self.blocks_x * self.blocks_y
        
        # Предвычисление координат
        self._precompute_coordinates()
        
        print("="*60)
        print("🎬 ДЕКОДЕР YouTube")
        print("="*60)
        print(f"📊 Сетка: {self.blocks_x} x {self.blocks_y} блоков")
        print(f"🔐 Ключ: {'ЕСТЬ' if self.key else 'НЕТ'}")
    
    def _precompute_coordinates(self):
        """Предвычисляет координаты блоков"""
        self.block_coords = []
        for idx in range(self.blocks_per_region):
            y = idx // self.blocks_x
            x = idx % self.blocks_x
            if y < self.blocks_y:
                cx = self.marker_size + x * (self.block_width + self.spacing) + self.block_width // 2
                cy = self.marker_size + y * (self.block_height + self.spacing) + self.block_height // 2
                self.block_coords.append((cx, cy))
    
    def _decrypt_data(self, data, iv):
        """XOR дешифрование с ключом  """
        if not self.key:
            return data

        key = hashlib.sha256(self.key.encode()).digest()
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_text = cipher.decrypt(data)
        unpadded_text = unpad(decrypted_text, AES.block_size)
        return unpadded_text
    
    def _color_to_bits_fast(self, color):
        """Оптимизированный поиск цвета"""
        color_key = (color[0], color[1], color[2])
        
        if color_key in self.color_cache:
            self.cache_hits += 1
            return self.color_cache[color_key]
        
        self.cache_misses += 1
        
        # Быстрая проверка на синий фон
        if color[0] > 200 and color[1] < 50 and color[2] < 50:
            self.color_cache[color_key] = '0000'
            return '0000'
        
        # NumPy векторизация
        color_arr = np.array([color[0], color[1], color[2]], dtype=np.int32)
        distances = np.sum((self.color_values - color_arr) ** 2, axis=1)
        best_idx = np.argmin(distances)
        result = self.color_keys[best_idx]
        
        self.color_cache[color_key] = result
        return result
    
    def decode_frame_fast(self, frame):
        """Быстрое декодирование одного кадра с масштабированием"""
        # Принудительное масштабирование к оригинальному размеру
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), 
                              interpolation=cv2.INTER_NEAREST)
        
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
        """4-битные блоки -> байты"""
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
        """Поиск маркера конца █████... в данных"""
        eof_bytes = b'\xe2\x96\x88' * 64
        
        for i in range(len(data) - len(eof_bytes)):
            if data[i:i+len(eof_bytes)] == eof_bytes:
                return i
        return -1
    
    def decode(self, video_file, output_dir='.'):
        """Декодирует видео"""
        
        print("\n📥 ДЕКОДИРОВАНИЕ ВИДЕО")
        print("-" * 40)
        
        if not os.path.exists(video_file):
            print(f"❌ Файл не найден: {video_file}")
            return False
        
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            print("❌ Не удалось открыть видео")
            return False
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"📹 Всего кадров: {total_frames}")
        print(f"📹 FPS: {fps}")
        print(f"📹 Разрешение: {width}x{height}")
        
        # Сброс статистики
        self.cache_hits = 0
        self.cache_misses = 0
        start_time = cv2.getTickCount()
        
        # Сбор блоков
        all_blocks = []
        frames_processed = 0
        
        for frame_num in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            
            frames_processed += 1
            
            # Прогресс
            if frame_num % 100 == 0:
                elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
                speed = frames_processed / elapsed if elapsed > 0 else 0
                cache_ratio = (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) if (self.cache_hits + self.cache_misses) > 0 else 0
                print(f"  Прогресс: {frame_num}/{total_frames} | "
                      f"Скорость: {speed:.1f} кадр/сек | "
                      f"Кэш: {cache_ratio:.1f}%")
            
            # Декодирование кадра с масштабированием
            frame_blocks = self.decode_frame_fast(frame)
            all_blocks.extend(frame_blocks)
        
        cap.release()
        
        # Статистика
        elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
        print(f"\n📊 Статистика: {len(all_blocks)} блоков за {elapsed:.1f} сек")
        print(f"  🎯 Кэш: попаданий {self.cache_hits}, промахов {self.cache_misses}")
        print(f"  🔄 Кадров обработано: {frames_processed}")
        
        # Конвертация в байты
        bytes_data = self._blocks_to_bytes(all_blocks)
        print(f"📦 Получено байт: {len(bytes_data)}")
        
        # Поиск маркера конца
        eof_pos = self._find_eof_marker(bytes_data)
        if eof_pos > 0:
            bytes_data = bytes_data[:eof_pos]
            print(f"✅ Найден маркер конца на позиции {eof_pos}")
            print(f"📦 Байт после обрезки: {len(bytes_data)}")
        else:
            print("⚠️ Маркер конца не найден")
        
        # Поиск заголовка
        data_str = bytes_data[:1000].decode('latin-1', errors='ignore')
        pattern = r'FILE:([^:]+):SIZE:(\d+):ENCRYPTED_SIZE:(\d+):IV:([^:]{16})\|'
        match = re.search(pattern, data_str)
        
        if match:
            filename = match.group(1)
            filesize = int(match.group(2))
            encrypted_size = int(match.group(3))
            iv = match.group(4).encode()
            
            print(f"\n✅ Найден заголовок: {filename}, размер: {filesize} байт")
            
            header_str = match.group(0)
            header_bytes = header_str.encode('latin-1')
            header_pos = bytes_data.find(header_bytes)
            
            if header_pos >= 0:
                # Извлекаем зашифрованные данные
                encrypted_data = bytes_data[header_pos + len(header_bytes):header_pos + len(header_bytes) + encrypted_size]
                
                # Дешифруем если есть ключ
                if self.key:
                    file_data = self._decrypt_data(encrypted_data, iv)
                    print(f"🔓 Данные расшифрованы")
                else:
                    file_data = encrypted_data
                    print(f"⚠️ Данные без расшифровки")
                
                # Сохраняем файл
                output_path = os.path.join(output_dir, filename)
                counter = 1
                base, ext = os.path.splitext(filename)
                while os.path.exists(output_path):
                    output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
                    counter += 1
                
                with open(output_path, 'wb') as f:
                    f.write(file_data)
                
                print(f"\n✅ Файл восстановлен: {output_path}")
                print(f"📏 Размер: {len(file_data)} байт")
                
                # Проверка размера
                if len(file_data) == filesize:
                    print("✅ Размер совпадает с оригиналом")
                else:
                    print(f"⚠️ Размер не совпадает: {len(file_data)} != {filesize}")
                
                return True
        else:
            print("❌ Заголовок не найден")
        
        # Если не нашли заголовок
        output_path = os.path.join(output_dir, "decoded_data.bin")
        with open(output_path, 'wb') as f:
            f.write(bytes_data)
        print(f"\n💾 Данные сохранены: {output_path}")
        return False


def read_key_from_file(key_file='key.txt'):
    """Читает ключ из файла key.txt"""
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    print(f"🔑 Ключ загружен из {key_file}")
                    return key
                else:
                    print(f"⚠️ Файл {key_file} пуст")
        else:
            print(f"ℹ️ Файл {key_file} не найден, шифрование не используется")
    except Exception as e:
        print(f"⚠️ Ошибка чтения ключа: {e}")
    
    return None


def main():
    if len(sys.argv) < 2:
        print("\n" + "="*60)
        print("🎥 YouTube File Storage (6 FPS)")
        print("="*60)
        print("\nИспользование:")
        print("  encode <файл> [output.mp4]  - закодировать файл")
        print("  decode <видео> [папка]      - декодировать видео")
        print("\nХарактеристики:")
        print("  • Частота кадров: 6 FPS")
        print("  • Масштабирование к 1920x1080")
        print("  • Маркер конца данных")
        print("  • 5 защитных кадров")
        print("\nШифрование:")
        print("  • Для шифрования создайте key.txt с ключом")
        return
    
    # Читаем ключ из файла
    key = read_key_from_file()
    
    if sys.argv[1] == "encode":
        encoder = YouTubeEncoder(key)
        input_file = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else "output.mp4"
        encoder.encode(input_file, output)
        
    elif sys.argv[1] == "decode":
        decoder = YouTubeDecoder(key)
        video_file = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "."
        decoder.decode(video_file, output_dir)
    else:
        print(f"❌ Неизвестная команда: {sys.argv[1]}")


if __name__ == "__main__":
    main()
