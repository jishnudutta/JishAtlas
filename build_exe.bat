@echo off
setlocal
cd /d "%~dp0"

set UV_CACHE_DIR=.uv-cache
set TEMP=%CD%\.build-tmp
set TMP=%CD%\.build-tmp
if not exist "%TEMP%" mkdir "%TEMP%"

where uv >nul 2>nul
if errorlevel 1 goto :python_build

set UV_PROJECT_ENVIRONMENT=.build-venv
echo Preparing the build environment...
uv sync --group dev
if errorlevel 1 goto :failed

echo.
echo Preparing the Windows icon from the JishAtlas SVG logo...
uv run python assets\make_icon.py
if errorlevel 1 goto :failed

echo.
echo Building JishAtlas.exe, including the llama.cpp native libraries...
uv run pyinstaller --clean JishAtlas.spec
if errorlevel 1 goto :failed
echo.
echo Checking the executable can start and load its packaged AI dependencies...
uv run pytest -q tests/test_exe_smoke.py
if errorlevel 1 goto :failed
goto :success

:python_build
where py >nul 2>nul
if errorlevel 1 (
    echo Install Python 3.13 or uv, then run this file again.
    echo uv installation: https://docs.astral.sh/uv/getting-started/installation/
    goto :failed
)

if exist ".build-venv\Scripts\python.exe" (
    .build-venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>nul
    if errorlevel 1 goto :create_venv
) else (
    goto :create_venv
)

goto :install_python_deps

:create_venv
echo Creating a Python 3.13 build environment...
    py -3.13 -m venv .build-venv
    if errorlevel 1 goto :failed

:install_python_deps
echo Installing JishAtlas and PyInstaller...
.build-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :failed
.build-venv\Scripts\python.exe -m pip install . pillow pyinstaller pytest
if errorlevel 1 goto :failed

echo.
echo Preparing the Windows icon from the JishAtlas SVG logo...
.build-venv\Scripts\python.exe assets\make_icon.py
if errorlevel 1 goto :failed

echo.
echo Building JishAtlas.exe, including the llama.cpp native libraries...
.build-venv\Scripts\python.exe -m PyInstaller --clean JishAtlas.spec
if errorlevel 1 goto :failed
echo.
echo Checking the executable can start and load its packaged AI dependencies...
.build-venv\Scripts\python.exe -m pytest -q tests/test_exe_smoke.py
if errorlevel 1 goto :failed

:success

echo.
echo Build complete: %CD%\dist\JishAtlas.exe
pause
exit /b 0

:failed
echo.
echo The build failed. Review the error above, then run this file again.
pause
exit /b 1
