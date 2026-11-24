#!/bin/bash
# Запуск в один клик (Linux/macOS): скачает клипы и нарежет шортсы.
set -e
cd "$(dirname "$0")"
pip3 install yt-dlp imageio-ffmpeg
python3 make_shorts.py "$@"
echo ""
echo "Готово! Шортсы лежат в папке shorts/"
