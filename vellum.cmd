@echo off
rem Vellum launcher (Windows). Thin shim — all logic lives in vellum.py.
rem Run it from PowerShell or cmd as:  vellum   or   .\vellum   (e.g. .\vellum init)
setlocal
set "ROOT=%~dp0"

rem Prefer the Python launcher (py -3), fall back to python on PATH.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%ROOT%vellum.py" %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
  python "%ROOT%vellum.py" %*
  exit /b %errorlevel%
)

echo Vellum needs Python 3.10 or newer, but none was found.>&2
echo Install it from https://www.python.org/downloads/ ^(check "Add to PATH"^) and try again.>&2
exit /b 1
