import xarray as xr
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class OceanDataProcessor:
    def __init__(self, cmems_files, gebco_file):
        """Initialise by lazily loading the NetCDF datasets."""
        # open_mfdataset handles concatenation across time dimensions automatically
        self.ds_ocean = xr.open_mfdataset(cmems_files, combine='by_coords')
        self.ds_bathy = xr.open_dataset(gebco_file)
        
    def process_bathymetry(self):
        """Extract and clean bathymetry data."""
        lon = self.ds_bathy['lon'].values
        lat = self.ds_bathy['lat'].values
        elevation = self.ds_bathy['elevation'].values
        
        # Mask out land (elevation > 0)
        elevation = np.where(elevation > 0, np.nan, elevation)
        return lon, lat, elevation

    def calculate_magnitude_direction(self, u, v):
        """Calculate magnitude and direction (degrees North) from u and v vectors."""
        magnitude = np.hypot(u, v)
        # Convert to degrees and wrap to 360 relative to North
        direction_rad = np.arctan2(v, u)
        direction_deg = np.degrees(direction_rad)
        direction_n = np.mod(90 - direction_deg, 360)
        return magnitude, direction_n

    def _filter_by_month_interval(self, start_month, end_month):
        """Return a dataset filtered to the selected month interval across all years."""
        if start_month is None or end_month is None:
            return self.ds_ocean

        month_index = self.ds_ocean['time'].dt.month
        if start_month <= end_month:
            selected_months = list(range(start_month, end_month + 1))
        else:
            selected_months = list(range(start_month, 13)) + list(range(1, end_month + 1))

        return self.ds_ocean.sel(time=month_index.isin(selected_months))

    def get_bottom_currents(self, start_month=None, end_month=None):
        """Extract currents at the lowest valid depth layer for each coordinate."""
        ds = self._filter_by_month_interval(start_month, end_month)

        # Calculate overall magnitude and direction
        ds['magn'], ds['dir'] = self.calculate_magnitude_direction(
            ds['uo'], ds['vo']
        )

        # Forward fill along the depth dimension. The last valid value is carried to the bottom.
        bottom_data = ds.ffill(dim='depth').isel(depth=-1)
        
        # Find the actual depth of the bottom layer
        depth_3d = ds.depth.broadcast_like(ds.uo.isel(time=0))
        bottom_depth = depth_3d.where(ds.uo.isel(time=0).notnull()).max(dim='depth')
        
        return bottom_data, bottom_depth

    def get_depth_averaged_currents(self, depth_up, depth_down, start_month=None, end_month=None):
        """Average the currents across a specific depth slice and compute derived fields.

        Parameters
        - depth_up: shallow/top bound for the slice. Can be positive (interpreted as metres
          below surface) or negative (dataset sign). The function normalizes the sign.
        - depth_down: deep/bottom bound for the slice. Same sign handling as `depth_up`.
        """
        ds = self._filter_by_month_interval(start_month, end_month)
        # Handle datasets that use negative depths (e.g., bathymetry/elevation conventions)
        depth_vals = ds.depth.values
        # If depth coordinate is all non-positive, assume depths are negative (e.g., -10, -20...)
        if np.all(depth_vals <= 0):
            d_up = -abs(depth_up)
            d_down = -abs(depth_down)
        else:
            d_up = depth_up
            d_down = depth_down

        # Select depth levels by magnitude (absolute depth from surface) so user inputs
        # like 700..800 (meaning -700..-800) match dataset coordinates regardless of sign/order.
        abs_depth_vals = np.abs(depth_vals)
        low_mag = min(abs(d_up), abs(d_down))
        high_mag = max(abs(d_up), abs(d_down))

        # Find indices where absolute depth falls within requested bounds (inclusive)
        idx = np.where((abs_depth_vals >= low_mag) & (abs_depth_vals <= high_mag))[0]
        if idx.size > 0:
            # Use .isel to select the discovered depth indices
            ds_sliced = ds.isel(depth=idx)
            selected_depths = depth_vals[idx]
            logger.info(f'✓ Depth selection: requested {depth_up:.0f}–{depth_down:.0f}m below surface, selected {idx.size} depth levels from {float(selected_depths.min()):.1f} to {float(selected_depths.max()):.1f}m')
        else:
            # No exact magnitude match: expand to nearest available levels around the bounds
            try:
                # Try to use the actual sign convention of the dataset (positive or negative)
                if np.all(depth_vals >= 0):
                    # Positive depths: search for positive bounds
                    nearest_low = float(ds.depth.sel(depth=low_mag, method='nearest'))
                    nearest_high = float(ds.depth.sel(depth=high_mag, method='nearest'))
                else:
                    # Negative depths: search for negative bounds
                    nearest_low = float(ds.depth.sel(depth=-low_mag, method='nearest'))
                    nearest_high = float(ds.depth.sel(depth=-high_mag, method='nearest'))
                # Ensure correct ordering for slice
                start_bound = min(nearest_low, nearest_high)
                stop_bound = max(nearest_low, nearest_high)
                ds_sliced = ds.sel(depth=slice(start_bound, stop_bound))
                logger.info(f'ℹ Depth selection: requested {depth_up:.0f}–{depth_down:.0f}m below surface, selected slice from {start_bound:.1f} to {stop_bound:.1f}m')
            except Exception:
                # As a last resort, pick the single nearest level to the midpoint
                try:
                    mid_mag = (low_mag + high_mag) / 2.0
                    if np.all(depth_vals >= 0):
                        nearest_mid = float(ds.depth.sel(depth=mid_mag, method='nearest'))
                    else:
                        nearest_mid = float(ds.depth.sel(depth=-mid_mag, method='nearest'))
                    ds_sliced = ds.sel(depth=nearest_mid)
                    logger.info(f'⚠ Depth selection: requested {depth_up:.0f}–{depth_down:.0f}m below surface, fell back to single nearest level: {nearest_mid:.1f}m')
                except Exception:
                    ds_sliced = ds
                    logger.info(f'⚠ Depth selection: requested {depth_up:.0f}–{depth_down:.0f}m below surface, no valid depths found, using all depths')

        mean_currents = ds_sliced.mean(dim='depth', skipna=True)
        mean_currents['magn'], mean_currents['dir'] = self.calculate_magnitude_direction(
            mean_currents['uo'], mean_currents['vo']
        )
        return mean_currents

    def export_to_csv(self, bottom_data, mean_currents, bottom_depth, output_path):
        """Flatten multidimensional arrays into a tabular format and export."""
        # Take the time mean for the export
        bot_mean = bottom_data.mean(dim='time', skipna=True)
        cur_mean = mean_currents.mean(dim='time', skipna=True)
        
        # Group everything into a single temporary Dataset
        ds_export = xr.Dataset({
            'bottomdepth': bottom_depth,
            'bottommeanmag': bot_mean['magn'],
            'bottommeandir': bot_mean['dir'],
            'currentmeanmag': cur_mean['magn'],
            'currentmeandir': cur_mean['dir']
        })
        
        # to_dataframe() automatically creates the perfect combinations of lon/lat for every point!
        df = ds_export.to_dataframe().reset_index()
        
        # Keep only the columns we actually want
        cols = ['longitude', 'latitude', 'bottomdepth', 'bottommeanmag', 
                'bottommeandir', 'currentmeanmag', 'currentmeandir']
        df = df[cols]
        
        # Drop rows where there is no ocean data (e.g., landmasses)
        df.dropna(subset=['bottommeanmag'], inplace=True)
        
        # Export to CSV
        df.to_csv(output_path, index=False)