@echo off
REM Запуск в один клик (Windows): скачает клипы и нарежет шортсы.
cd /d %~dp0
pip install yt-dlp imageio-ffmpeg
python make_shorts.py %*
echo.
echo Готово! Шортсы лежат в папке shorts\
pause
