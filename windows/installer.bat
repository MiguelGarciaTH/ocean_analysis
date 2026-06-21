@echo off
REM Installer and launcher for Windows: creates venv, installs deps, runs gui.py

pushd "%~dp0.."
set PROJECT_DIR=%CD%
set VENV_DIR=%PROJECT_DIR%\venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating virtual environment in %VENV_DIR%...
  python -m venv "%VENV_DIR%"
  echo Upgrading pip and installing requirements...
  "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
  "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%PROJECT_DIR%\requirements.txt"
) else (
  echo Virtual environment already exists at %VENV_DIR%.
)

echo Launching GUI...
if exist "%VENV_DIR%\Scripts\pythonw.exe" (
  "%VENV_DIR%\Scripts\pythonw.exe" "%PROJECT_DIR%\gui.py"
) else (
  "%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%\gui.py"
)

popd
