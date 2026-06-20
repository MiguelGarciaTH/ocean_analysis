# Ocean Currents Analysis Pipeline

This project processes Global Ocean Physics Reanalysis data (CMEMS) and GEBCO bathymetry to calculate and visualise bottom currents and specific depth-averaged currents.

## Prerequisites
1. Install Python (3.9 or newer is recommended).
2. Open your terminal or command prompt.
3. Navigate to this project folder.

## Installation
It is highly recommended to use a virtual environment.
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

## Optional colour palettes
This project now supports the `cmcrameri` colour palettes for better scientific colourmaps. The default palette is `cm.batlow` when `cmcrameri` is installed.

## Launching the GUI
Run the GUI to select input files, depth bounds, and month interval interactively:

```bash
python gui.py
```
