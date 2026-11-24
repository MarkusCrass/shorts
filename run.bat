@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if not errorlevel 1 goto havepy
where py >nul 2>&1
if not errorlevel 1 goto havepylauncher

echo.
echo Python not found.
echo Install it from https://www.python.org/downloads/
echo IMPORTANT: tick "Add Python to PATH" in the installer.
echo Then run run.bat again.
echo.
pause
exit /b 1

:havepylauncher
set "PYEXE=py -3"
goto deps

:havepy
set "PYEXE=python"

:deps
%PYEXE% -m pip install --upgrade -q -r requirements.txt
if errorlevel 1 %PYEXE% -m pip install --upgrade -q yt-dlp imageio-ffmpeg

REM No browser cookies by default: on Windows Chrome/Edge cookies fail with
REM "Failed to decrypt with DPAPI". Home internet usually works without cookies.
REM If YouTube asks to sign in, the script will retry with cookies by itself.

:run
%PYEXE% make_shorts.py %*
set "STATUS=%ERRORLEVEL%"
echo.
pause
exit /b %STATUS%
