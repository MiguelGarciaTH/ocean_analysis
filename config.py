# --- FILE PATHS ---
# Add or remove files from this list; the processor handles concatenation automatically.
CMEMS_FILES = [
    'data/cmems_mod_glo_phy_my_0.083deg_P1M-m_1714487911627.nc',
    'data/cmems_mod_glo_phy_my_0.083deg_P1M-m_1714488096171.nc'
]

GEBCO_FILE = 'data/gebco_2023_n30.0_s17.0_w115.0_e130.0.nc'

# --- OUTPUT DIRECTORIES ---
IMAGE_OUT_DIR = 'output_images'
DATA_OUT_DIR = 'output_data'
OUTPUT_CSV = 'output_data/MeanVel.csv'

# --- ANALYSIS PARAMETERS ---
# Depth selection (meters below sea surface). Use positive numbers to indicate
# depth below the surface (e.g., 700 means 700 m below sea surface => -700 in depth coords).
# `DEPTH_SHALLOW_M` is the shallower bound (top of the slice),
# `DEPTH_DEEP_M` is the deeper bound (bottom of the slice).
DEPTH_SHALLOW_M = 0        # Shallow/top limit in metres below surface (positive)
DEPTH_DEEP_M = 5500       # Deep/bottom limit in metres below surface (positive)

# Backwards-compatible names (deprecated): keep for scripts using the old names.
DEPTH_UP = DEPTH_SHALLOW_M
DEPTH_DOWN = DEPTH_DEEP_M
MONTH_START = 1     # Start month for averaging (1 = January)
MONTH_END = 12      # End month for averaging (12 = December)

# Plotting parameters
SPATIAL_STEP = 3    # Step size for quiver arrows to prevent overcrowding