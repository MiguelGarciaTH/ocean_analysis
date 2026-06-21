Building a Windows executable for the project

1) Purpose
- `windows/launcher.py` is a small launcher that creates a venv, installs `requirements.txt`, and runs `gui.py`.

2) Quick build steps (on Windows)

- Install Python 3.8+ and open a Developer PowerShell or cmd.
- Install PyInstaller: `python -m pip install pyinstaller`
- From the project root run:

```powershell
pyinstaller --onefile --noconsole --name OceanAnalysisLauncher windows/launcher.py
```

- After the build, the single-file executable will be in `dist\OceanAnalysisLauncher.exe`.

3) Notes
- The generated exe will run on the machine it is executed on; it cannot create a full system Python for other machines. The launcher will create a local `venv` inside the project folder and install dependencies from `requirements.txt` into that venv on first run.
- If you want a truly standalone bundle (no external installs), you must package the whole application and its dependencies including binary wheels; that may require testing and adding binary data via PyInstaller `--add-data` and ensuring platform-specific wheels are available.
