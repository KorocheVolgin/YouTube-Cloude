# YouTube-Cloude

Утилита для кодирования произвольных файлов в видео формата MP4 и их последующего восстановления. Опционально поддерживает шифрование данных.

---

## Установка зависимостей

```
pip install opencv-python numpy
```

---

## Использование

### Кодирование файла в видео

```
python coder.py encode FILENAME.xxx [OUTPUT.mp4]
```

`OUTPUT.mp4` — необязательный аргумент. Если не указан, результат сохранится как `output.mp4`.

### Декодирование видео обратно в файл

```
python coder.py decode FILENAME.mp4 [ПАПКА]
```

`ПАПКА` — необязательный аргумент. Если не указана, файл сохранится в текущую директорию.

---

## Шифрование

Файл можно зашифровать при кодировании и расшифровать при декодировании. Ключ указывается одним из двух способов — они взаимоисключающие.

### 1. Ключ напрямую в командной строке

**Кодирование:**
```
python coder.py encode FILENAME.xxx OUTPUT.mp4 --key SECRET
```

**Декодирование:**
```
python coder.py decode FILENAME.mp4 --key SECRET
```

### 2. Путь к файлу с ключом

**Кодирование:**
```
python coder.py encode FILENAME.xxx OUTPUT.mp4 --key-file /path/to/key.txt
```

**Декодирование:**
```
python coder.py decode FILENAME.mp4 --key-file /path/to/key.txt
```

---

## Справка

Общая справка:
```
python coder.py --help
```

Справка по конкретной команде:
```
python coder.py encode --help
python coder.py decode --help
```
