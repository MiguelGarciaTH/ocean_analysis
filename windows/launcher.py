import os
import subprocess
from pathlib import Path

project_dir = Path(__file__).resolve().parent.parent
venv_dir = project_dir / "venv"

def run(cmd):
    subprocess.check_call(cmd, shell=True)

if not (venv_dir / "Scripts" / "python.exe").exists():
    print("Creating virtual environment...")
    run(f'python -m venv "{venv_dir}"')
    py = venv_dir / "Scripts" / "python.exe"
    run(f'"{py}" -m pip install --upgrade pip')
    run(f'"{py}" -m pip install -r "{project_dir / "requirements.txt"}"')
else:
    print("Virtual environment already exists; skipping creation.")

python_exe = venv_dir / "Scripts" / "pythonw.exe"
if not python_exe.exists():
    python_exe = venv_dir / "Scripts" / "python.exe"

run(f'"{python_exe}" "{project_dir / "gui.py"}"')
