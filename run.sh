#!/bin/bash
# Запуск в один клик (Linux/macOS): скачает клипы и нарежет шортсы.
# Аргументы пробрасываются в make_shorts.py, например: ./run.sh --only 01 --mode blur
set -e
cd "$(dirname "$0")"
python3 -m pip install --upgrade -q -r requirements.txt
python3 make_shorts.py "$@"
echo ""
echo "Готово! Шортсы лежат в папке shorts/"
