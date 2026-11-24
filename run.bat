@echo off
REM Запуск в один клик (Windows): скачает клипы и нарежет шортсы.
REM Аргументы пробрасываются в make_shorts.py, например: run.bat --only 01 --mode blur
cd /d %~dp0
python -m pip install --upgrade -q -r requirements.txt
python make_shorts.py %*
echo.
echo Готово! Шортсы лежат в папке shorts\
pause
