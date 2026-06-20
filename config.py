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
DEPTH_UP = 0        # Upper limit in metres
DEPTH_DOWN = 5500   # Lower limit in metres
MONTH_START = 1     # Start month for averaging (1 = January)
MONTH_END = 12      # End month for averaging (12 = December)

# Plotting parameters
SPATIAL_STEP = 3    # Step size for quiver arrows to prevent overcrowding