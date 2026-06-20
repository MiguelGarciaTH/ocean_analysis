import xarray as xr
import numpy as np
import pandas as pd

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
        """Average the currents across a specific depth slice and compute derived fields."""
        ds = self._filter_by_month_interval(start_month, end_month)
        ds_sliced = ds.sel(depth=slice(depth_up, depth_down))
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