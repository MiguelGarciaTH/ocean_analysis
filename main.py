import logging
import os
import xarray as xr
import config as cfg
from data_processor import OceanDataProcessor
import plotter


def configure_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format='%(message)s',
        handlers=[logging.StreamHandler()]
    )


def check_optional_dependencies():
    try:
        import bottleneck  # noqa: F401
    except ModuleNotFoundError:
        logging.warning(
            'Optional package bottleneck is missing. Install it with "pip install bottleneck" '
            'to avoid xarray/dask import issues during reductions.'
        )


def main():
    configure_logging()
    check_optional_dependencies()
    logger = logging.getLogger(__name__)
    # 1. Setup Directories
    os.makedirs(cfg.IMAGE_OUT_DIR, exist_ok=True)
    os.makedirs(cfg.DATA_OUT_DIR, exist_ok=True)

    logger.warning('Starting ocean analysis...')
    processor = OceanDataProcessor(cfg.CMEMS_FILES, cfg.GEBCO_FILE)
    lon_bathy, lat_bathy, elevation = processor.process_bathymetry()
    
    # Define bounding box based on ocean data extent
    lon_ocean = processor.ds_ocean.longitude.values
    lat_ocean = processor.ds_ocean.latitude.values
    extent = [lon_ocean.min(), lon_ocean.max(), lat_ocean.min(), lat_ocean.max()]

    bottom_data, bottom_depth = processor.get_bottom_currents(cfg.MONTH_START, cfg.MONTH_END)

    # Config values are expressed as positive metres below the sea surface (e.g. 700 -> 700 m
    # below surface). Convert to the dataset's depth sign convention (likely negative values)
    # before passing them to the processor and for comparisons below.
    depth_shallow = -abs(cfg.DEPTH_SHALLOW_M)
    depth_deep = -abs(cfg.DEPTH_DEEP_M)

    currents_data = processor.get_depth_averaged_currents(
        depth_shallow, depth_deep, cfg.MONTH_START, cfg.MONTH_END
    )

    # Resolve actual bottom matrix for plotting (using minimum of stated depth or actual bottom)
    # Replicates MATLAB: depthdownM=min(depthdown,bottomdepth)
    depth_down_matrix = xr.where(bottom_depth < depth_deep, bottom_depth, depth_deep)

    plotter.create_bathymetry_plot(
        lon_bathy, lat_bathy, elevation, 
        bottom_depth, depth_down_matrix, 
        extent, cfg.IMAGE_OUT_DIR,
        month_start=cfg.MONTH_START, month_end=cfg.MONTH_END,
        depth_shallow_m=cfg.DEPTH_SHALLOW_M, depth_deep_m=cfg.DEPTH_DEEP_M,
        analysis_type='bathymetry_depths'
    )

    # Take the mean across the time dimension
    bottom_mean = bottom_data.mean(dim='time', skipna=True)
    currents_mean = currents_data.mean(dim='time', skipna=True)
    
    plotter.create_velocity_plot(
        currents_mean, bottom_mean, 
        lon_bathy, lat_bathy, elevation, 
        extent, cfg.SPATIAL_STEP, 'fig2_mean_velocity.png', cfg.IMAGE_OUT_DIR,
        month_start=cfg.MONTH_START, month_end=cfg.MONTH_END,
        depth_shallow_m=cfg.DEPTH_SHALLOW_M, depth_deep_m=cfg.DEPTH_DEEP_M,
        analysis_type='mean_velocity'
    )

    out_path = os.path.join(cfg.DATA_OUT_DIR, 'MeanVel.csv')
    processor.export_to_csv(bottom_data, currents_data, bottom_depth, out_path)

    logger.warning('Analysis complete!')

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception('Unhandled exception during main execution')
        raise
