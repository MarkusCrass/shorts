@echo off
REM Запуск в один клик (Windows).
REM   run.bat              - cookies из браузера + все клипы
REM   run.bat --only 04    - только один клип
chcp 65001 >nul
cd /d %~dp0

python -m pip install --upgrade -q -r requirements.txt >nul 2>&1

if not defined SHORTS_COOKIES_FROM_BROWSER if not exist cookies.txt (
  if exist "%LOCALAPPDATA%\Google\Chrome\User Data" (
    set SHORTS_COOKIES_FROM_BROWSER=chrome
    echo Cookies беру из Chrome
  ) else if exist "%APPDATA%\Mozilla\Firefox\Profiles" (
    set SHORTS_COOKIES_FROM_BROWSER=firefox
    echo Cookies беру из Firefox
  ) else if exist "%LOCALAPPDATA%\Microsoft\Edge\User Data" (
    set SHORTS_COOKIES_FROM_BROWSER=edge
    echo Cookies беру из Edge
  )
)

python make_shorts.py %*
set STATUS=%ERRORLEVEL%

echo.
if "%STATUS%"=="0" (
  echo Готово! Шортсы лежат в папке shorts\
  echo Там же: .jpg ^(превью^) и .txt ^(заголовок, описание, теги^).
) else (
  echo Часть клипов не получилась - смотрите подсказку выше.
)
pause
exit /b %STATUS%
