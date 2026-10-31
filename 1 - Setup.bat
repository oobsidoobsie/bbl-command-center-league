@echo off
REM One-time setup: private Python environment, the browser it uses, and the libraries.
cd /d "%~dp0"
echo BBL Command Center - setup
echo.
set "PY="
py -3.13 -c "import sys" >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3.14 -c "import sys" >nul 2>nul && set "PY=py -3.14"
if not defined PY (
  echo This needs Python 3.12 or newer ^(you can keep your other Python too^).
  echo Install Python 3.13 from https://www.python.org/downloads/windows/
  echo On the first installer screen tick "Add python.exe to PATH", then run this Setup again.
  pause & exit /b 1
)
echo Using %PY%
echo 1/3 Creating the environment...
%PY% -m venv .venv || (echo Couldn't create the environment. & pause & exit /b 1)
echo 2/3 Installing libraries ^(Playwright, numpy, time zones^)...
.venv\Scripts\python -m pip install --quiet --upgrade pip playwright numpy tzdata || (echo Install failed - check your internet. & pause & exit /b 1)
echo 3/3 Downloading the browser it uses ^(about 150 MB, one time^)...
.venv\Scripts\python -m playwright install chromium || (echo Browser download failed - run Setup again. & pause & exit /b 1)
if not exist secret.txt copy /y "cc\secret.example.txt" secret.txt >nul
echo.
echo Setup done. Next: double-click "2 - Sign in to CBS".
pause
