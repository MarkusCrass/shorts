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
%PYEXE% -m pip install --upgrade -q -r requirements.txt >nul 2>&1

if defined SHORTS_COOKIES_FROM_BROWSER goto run
if exist cookies.txt goto run
if exist "%LOCALAPPDATA%\Google\Chrome\User Data" set "SHORTS_COOKIES_FROM_BROWSER=chrome"
if exist "%APPDATA%\Mozilla\Firefox\Profiles" set "SHORTS_COOKIES_FROM_BROWSER=firefox"
if exist "%LOCALAPPDATA%\Microsoft\Edge\User Data" set "SHORTS_COOKIES_FROM_BROWSER=edge"

:run
if defined SHORTS_COOKIES_FROM_BROWSER echo Using browser cookies: %SHORTS_COOKIES_FROM_BROWSER%
%PYEXE% make_shorts.py %*
set "STATUS=%ERRORLEVEL%"
echo.
pause
exit /b %STATUS%
