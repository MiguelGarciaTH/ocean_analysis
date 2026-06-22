import matplotlib.pyplot as plt
import numpy as np
import os

# Importar o cmcrameri apenas para registar as cores no Matplotlib
# (sem importar o 'cm' para evitar conflitos de nomes)
try:
    import cmcrameri
except ImportError:
    pass

def get_safe_cmap(cmap_name):
    """Obtém o colormap de forma segura, adicionando o prefixo cmc. se necessário."""
    # Accept prefixed names from GUI like "Matplotlib - viridis" or "Crameri - lapaz"
    try:
        if isinstance(cmap_name, str) and cmap_name.startswith('Matplotlib - '):
            base = cmap_name.split('Matplotlib - ', 1)[1].strip()
            return plt.get_cmap(base)
        if isinstance(cmap_name, str) and cmap_name.startswith('Crameri - '):
            base = cmap_name.split('Crameri - ', 1)[1].strip()
            # Try matplotlib cmc.<name> first
            try:
                return plt.get_cmap(f'cmc.{base}')
            except Exception:
                # Fall back to cmcrameri if installed
                try:
                    import cmcrameri
                    cm = getattr(cmcrameri, base)
                    return cm
                except Exception:
                    return plt.get_cmap('viridis')

        # Try direct lookup (callable or matplotlib name)
        if not isinstance(cmap_name, str):
            return cmap_name
        return plt.get_cmap(cmap_name)
    except Exception:
        # Last-resort fallback
        try:
            return plt.get_cmap(f'cmc.{cmap_name}')
        except Exception:
            return plt.get_cmap('viridis')

# Colormap padrão para a Análise de Mapa
DEFAULT_CMAP = get_safe_cmap('lapaz')

def create_bathymetry_plot(lon_bathy, lat_bathy, elevation, bottom_depth, depth_down_matrix, extent, out_dir,
                           month_start=None, month_end=None, depth_shallow_m=None, depth_deep_m=None,
                           analysis_type=None, cmap_name='lapaz'):
    """Replicates Figure 1: Bathymetry and Depth analysis."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    levels = [-5000, -2000, -200, 0]
    
    cmap = get_safe_cmap(cmap_name)
    ax = axes[0]
    pcm = ax.pcolormesh(lon_bathy, lat_bathy, elevation, shading='auto', cmap=cmap)
    ax.contour(lon_bathy, lat_bathy, elevation, levels, colors='k', linewidths=0.5)
    fig.colorbar(pcm, ax=ax)
    ax.set_title('Bathymetry in the area')
    ax.axis(extent)
    
    ax = axes[1]
    pcm = ax.pcolormesh(bottom_depth.longitude, bottom_depth.latitude, -depth_down_matrix, shading='auto', cmap=cmap)
    ax.contour(lon_bathy, lat_bathy, elevation, levels, colors='k', linewidths=0.5)
    fig.colorbar(pcm, ax=ax)
    ax.set_title('Depth: lowest layer current analysis')
    ax.axis(extent)

    ax = axes[2]
    pcm = ax.pcolormesh(bottom_depth.longitude, bottom_depth.latitude, -bottom_depth, shading='auto', cmap=cmap)
    ax.contour(lon_bathy, lat_bathy, elevation, levels, colors='k', linewidths=0.5)
    fig.colorbar(pcm, ax=ax)
    ax.set_title('Depth: lowest layer bottom current')
    ax.axis(extent)

    plt.tight_layout()
    # Add metadata box (months, depth range, analysis type) — show as subdued text
    meta_lines = []
    if month_start is not None and month_end is not None:
        meta_lines.append(f'Months: {month_start}-{month_end}')
    if depth_shallow_m is not None and depth_deep_m is not None:
        ds_shallow = int(min(abs(depth_shallow_m), abs(depth_deep_m)))
        ds_deep = int(max(abs(depth_shallow_m), abs(depth_deep_m)))
        meta_lines.append(f'Depths (m below surface): {ds_shallow} to {ds_deep}')
    if analysis_type:
        meta_lines.append(f'Analysis: {analysis_type}')
    if meta_lines:
        meta_text = '\n'.join(meta_lines)
        # place at bottom-left, small gray text with lower opacity so it doesn't overpower the plot
        fig.text(0.02, 0.02, meta_text, ha='left', va='bottom', fontsize=7, color='gray',
                 bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))
    # Build filename with metadata if available
    if month_start is not None and month_end is not None and depth_shallow_m is not None and depth_deep_m is not None:
        ds_shallow = int(min(abs(depth_shallow_m), abs(depth_deep_m)))
        ds_deep = int(max(abs(depth_shallow_m), abs(depth_deep_m)))
        fname = f"bathymetry_months_{month_start}-{month_end}_depth_{ds_shallow}-{ds_deep}.png"
    else:
        fname = 'fig1_bathymetry_depths.png'
    plt.savefig(os.path.join(out_dir, fname), dpi=300)
    plt.close()

def create_velocity_plot(ds_currents, ds_bottom, lon_bathy, lat_bathy, elevation, extent, step, filename, out_dir,
                         vmax=0.55, month_start=None, month_end=None, depth_shallow_m=None,
                         depth_deep_m=None, analysis_type=None, cmap_name='lapaz'):
    """Replicates Figures 2 & 3: Quiver and magnitude plots for currents."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    lon = ds_currents.longitude.values
    lat = ds_currents.latitude.values
    levels = [-5000, -2000, -200, 0]

    cmap = get_safe_cmap(cmap_name)

    def get_contrasting_colors(magnitudes):
        """Calculates luminance of the colormap to return white or black arrow colors."""
        # Normalize magnitudes to 0-1 range, handling NaNs
        norm_mag = np.clip(np.nan_to_num(magnitudes, nan=0) / vmax, 0, 1)
        # Evaluate the colormap to get RGBA values
        rgba = cmap(norm_mag)
        # Calculate relative perceived luminance 
        luminance = 0.299 * rgba[..., 0] + 0.587 * rgba[..., 1] + 0.114 * rgba[..., 2]
        # Use white for dark backgrounds (< 0.5) and black for light ones
        colors = np.where(luminance < 0.5, 'white', 'black')
        return colors.flatten()

    ax = axes[0]
    pcm = ax.pcolormesh(lon, lat, ds_currents['magn'].values, shading='auto', cmap=cmap, vmin=0, vmax=vmax)
    ax.contour(lon_bathy, lat_bathy, elevation, levels, colors='k', linewidths=0.5)
    
    # Extract subset of data for quiver
    u1 = ds_currents['uo'].values[::step, ::step]
    v1 = ds_currents['vo'].values[::step, ::step]
    m1 = ds_currents['magn'].values[::step, ::step]
    c1 = get_contrasting_colors(m1)
    
    ax.quiver(lon[::step], lat[::step], u1, v1, color=c1, scale=12, width=0.002)
    
    fig.colorbar(pcm, ax=ax, label='Magnitude (m/s)')
    ax.set_title('Current velocity magnitude (m/s)')
    ax.set_xlabel('Longitude (°)')
    ax.set_ylabel('Latitude (°)')
    ax.axis(extent)

    ax = axes[1]
    pcm = ax.pcolormesh(lon, lat, ds_bottom['magn'].values, shading='auto', cmap=cmap, vmin=0, vmax=vmax)
    ax.contour(lon_bathy, lat_bathy, elevation, levels, colors='k', linewidths=0.5)
    
    u2 = ds_bottom['uo'].values[::step, ::step]
    v2 = ds_bottom['vo'].values[::step, ::step]
    m2 = ds_bottom['magn'].values[::step, ::step]
    c2 = get_contrasting_colors(m2)
    
    ax.quiver(lon[::step], lat[::step], u2, v2, color=c2, scale=12, width=0.002)
    
    fig.colorbar(pcm, ax=ax, label='Magnitude (m/s)')
    ax.set_title('Bottom velocity magnitude (m/s)')
    ax.set_xlabel('Longitude (°)')
    ax.set_ylabel('Latitude (°)')
    ax.axis(extent)

    plt.tight_layout()
    # Add metadata box (subdued)
    meta_lines = []
    if month_start is not None and month_end is not None:
        meta_lines.append(f'Months: {month_start}-{month_end}')
    if depth_shallow_m is not None and depth_deep_m is not None:
        ds_shallow = int(min(abs(depth_shallow_m), abs(depth_deep_m)))
        ds_deep = int(max(abs(depth_shallow_m), abs(depth_deep_m)))
        meta_lines.append(f'Depths (m below surface): {ds_shallow} to {ds_deep}')
    if analysis_type:
        meta_lines.append(f'Analysis: {analysis_type}')
    if meta_lines:
        meta_text = '\n'.join(meta_lines)
        fig.text(0.02, 0.02, meta_text, ha='left', va='bottom', fontsize=7, color='gray',
                 bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))

    # Build a clear, human-readable filename for velocity outputs
    if month_start is not None and month_end is not None and depth_shallow_m is not None and depth_deep_m is not None:
        ds_shallow = int(min(abs(depth_shallow_m), abs(depth_deep_m)))
        ds_deep = int(max(abs(depth_shallow_m), abs(depth_deep_m)))
        ds = f"mean_velocity_months_{month_start}-{month_end}_depth_{ds_shallow}-{ds_deep}.png"
    else:
        ds = filename or 'fig2_mean_velocity.png'
    plt.savefig(os.path.join(out_dir, ds), dpi=300)
    plt.close()

def create_section_plots(processor, coord_beg, coord_end, month_start, month_end, out_dir, cmap_name='lapaz',
                         depth_shallow_m=None, depth_deep_m=None, analysis_type=None):
    """Create section plots between coord_beg and coord_end with a mini-map inset."""
    ds = processor._filter_by_month_interval(month_start, month_end)

    u_mean = ds['uo'].mean(dim='time', skipna=True)
    v_mean = ds['vo'].mean(dim='time', skipna=True)

    lon = ds.longitude.values
    lat = ds.latitude.values

    lon0, lat0 = coord_beg
    lon1, lat1 = coord_end

    N = 200
    lons = np.linspace(lon0, lon1, N)
    lats = np.linspace(lat0, lat1, N)

    lon_idx = np.abs(lon[None, :] - lons[:, None]).argmin(axis=1)
    lat_idx = np.abs(lat[None, :] - lats[:, None]).argmin(axis=1)

    depth = u_mean.depth.values

    magn_section = np.full((len(depth), N), np.nan)
    dir_section = np.full((len(depth), N), np.nan)

    for k in range(N):
        i = lon_idx[k]
        j = lat_idx[k]
        ucol = u_mean[:, j, i].values
        vcol = v_mean[:, j, i].values
        magn = np.hypot(ucol, vcol)
        dir_rad = np.arctan2(vcol, ucol)
        dir_deg = np.degrees(dir_rad)
        dir_n = np.mod(90 - dir_deg, 360)
        magn_section[:, k] = magn
        dir_section[:, k] = dir_n

    try:
        lonb = processor.ds_bathy['lon'].values
        latb = processor.ds_bathy['lat'].values
        elev = processor.ds_bathy['elevation'].values
        bathy_vals = np.full(N, np.nan)
        for k in range(N):
            i = np.abs(lonb - lons[k]).argmin()
            j = np.abs(latb - lats[k]).argmin()
            bathy_vals[k] = elev[j, i]
    except Exception:
        bathy_vals = None

    if abs(lon1 - lon0) > abs(lat1 - lat0):
        x_axis_data = lons
        x_label = 'longitude (°)'
    else:
        x_axis_data = lats
        x_label = 'latitude (°)'

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    section_cmap = get_safe_cmap(cmap_name)

    has_data = not np.all(np.isnan(magn_section))
    max_val = np.nanmax(magn_section) if has_data else 0.55
    if max_val == 0 or np.isnan(max_val):
        max_val = 0.55

    if bathy_vals is not None:
        ocean_depths = bathy_vals[bathy_vals < 0]
        if len(ocean_depths) > 0:
            min_y = np.nanmin(ocean_depths) - 30 
        else:
            min_y = -200 
    else:
        min_y = -1000

    # --- 1. Magnitude Plot ---
    ax = axes[0]
    pcm = ax.pcolormesh(x_axis_data, -depth, magn_section, shading='nearest', 
                        cmap=section_cmap, vmin=0, vmax=max_val, zorder=1)
    fig.colorbar(pcm, ax=ax, label='velocity magnitude (m/s)')
    
    if bathy_vals is not None:
        ax.plot(x_axis_data, bathy_vals, color='black', linewidth=2, zorder=3)
        ax.fill_between(x_axis_data, bathy_vals, -10000, color='white', zorder=2)
    
    ax.set_ylim(min_y, 0)
    ax.set_ylabel('depth (m)')
    ax.set_title('velocity magnitude (m/s)', fontweight='bold')

    # --- 2. Direction Plot ---
    ax = axes[1]
    pcm2 = ax.pcolormesh(x_axis_data, -depth, dir_section, shading='nearest', 
                         cmap='twilight_shifted', vmin=0, vmax=360, zorder=1)
    fig.colorbar(pcm2, ax=ax, label='velocity direction (°N)')
    
    if bathy_vals is not None:
        ax.plot(x_axis_data, bathy_vals, color='black', linewidth=2, zorder=3)
        ax.fill_between(x_axis_data, bathy_vals, -10000, color='white', zorder=2)
        
        # ---------------------------------------------------------
        # ADD INSET MINI-MAP 
        # ---------------------------------------------------------
        axins = ax.inset_axes([0.07, 0.08, 0.25, 0.40])
        
        # Plot full bathymetry in the inset
        lonb_full = processor.ds_bathy['lon'].values
        latb_full = processor.ds_bathy['lat'].values
        elev_full = processor.ds_bathy['elevation'].values
        
        # MASK: Set any elevation above 0 (land) to NaN so it doesn't get a colormap color
        elev_ocean = np.where(elev_full > 0, np.nan, elev_full)
        
        ins_pcm = axins.pcolormesh(lonb_full, latb_full, elev_ocean, shading='auto', cmap=DEFAULT_CMAP)
        
        # Add a subtle coastline
        axins.contour(lonb_full, latb_full, elev_full, levels=[0], colors='gray', linewidths=0.5)
        
        # Draw the section line (using cyan so it pops against the black land)
        axins.plot([lon0, lon1], [lat0, lat1], color='cyan', linewidth=2.5)
        
        # Define tighter zoom bounds
        b_lon = max(1.0, abs(lon1 - lon0) * 0.8)
        b_lat = max(1.0, abs(lat1 - lat0) * 0.8)
        
        min_l, max_l = min(lon0, lon1), max(lon0, lon1)
        min_t, max_t = min(lat0, lat1), max(lat0, lat1)
        
        # Clamp to avoid going out of bathymetry bounds
        axins.set_xlim(max(lonb_full.min(), min_l - b_lon), min(lonb_full.max(), max_l + b_lon))
        axins.set_ylim(max(latb_full.min(), min_t - b_lat), min(latb_full.max(), max_t + b_lat))
        
        # Format inset style
        axins.tick_params(labelsize=6)
        
        # CRITICAL: Set the background color to black. The NaNs (land) will let this show through.
        axins.set_facecolor('black')
        
        # Add colorbar to the mini map
        cbar_ins = fig.colorbar(ins_pcm, ax=axins, shrink=0.8, pad=0.05)
        cbar_ins.ax.tick_params(labelsize=5)
        # ---------------------------------------------------------

    ax.set_ylim(min_y, 0)
    ax.set_ylabel('depth (m)')
    ax.set_xlabel(x_label)
    ax.set_title('velocity direction (°N)', fontweight='bold')

    plt.tight_layout()
    # Add metadata box (subdued)
    meta_lines = []
    if month_start is not None and month_end is not None:
        meta_lines.append(f'Months: {month_start}-{month_end}')
    if depth_shallow_m is not None and depth_deep_m is not None:
        ds_shallow = int(min(abs(depth_shallow_m), abs(depth_deep_m)))
        ds_deep = int(max(abs(depth_shallow_m), abs(depth_deep_m)))
        meta_lines.append(f'Depths (m below surface): {ds_shallow} to {ds_deep}')
    if analysis_type:
        meta_lines.append(f'Analysis: {analysis_type}')
    if meta_lines:
        meta_text = '\n'.join(meta_lines)
        fig.text(0.02, 0.02, meta_text, ha='left', va='bottom', fontsize=7, color='gray',
                 bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))

    # Filename with metadata
    if month_start is not None and month_end is not None and depth_shallow_m is not None and depth_deep_m is not None:
        outpath = os.path.join(out_dir, f"section_time_mean_{month_start}-{month_end}_{int(depth_shallow_m)}-{int(depth_deep_m)}.png")
    else:
        outpath = os.path.join(out_dir, 'section_time_mean.png')
    plt.savefig(outpath, dpi=300)
    plt.close()