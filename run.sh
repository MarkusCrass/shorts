#!/bin/bash
# Запуск в один клик (Linux/macOS).
#   ./run.sh              — взять cookies из первого найденного браузера и нарезать все клипы
#   ./run.sh --only 04    — только один клип
#   ./run.sh --mode blur  — размытый фон
set -u
cd "$(dirname "$0")"

python3 -m pip install --upgrade -q -r requirements.txt 2>/dev/null || true

# cookies из браузера НЕ подставляем автоматически: на Windows они часто
# не читаются (DPAPI), а на домашнем интернете YouTube обычно пускает и так.
# Если понадобятся — скрипт сам сообщит и попробует.

python3 make_shorts.py "$@"
STATUS=$?

echo ""
if [ $STATUS -eq 0 ]; then
  echo "Готово! Шортсы лежат в папке shorts/"
  echo "Там же: .jpg (превью) и .txt (заголовок, описание, теги для загрузки)."
else
  echo "Часть клипов не получилась — смотрите подсказку выше."
fi
read -r -p "Нажмите Enter, чтобы закрыть..." _ 2>/dev/null || true
exit $STATUS
