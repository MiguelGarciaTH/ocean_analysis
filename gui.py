import io
import logging
import math
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
from PIL import Image, ImageDraw

import config as cfg
from data_processor import OceanDataProcessor
import plotter

# Configure logging to both console and GUI
class GUILogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.config(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')
        self.text_widget.update()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    import bottleneck  # noqa: F401
except ModuleNotFoundError:
    pass

try:
    from cmcrameri import cm
    CMAPS = {name: getattr(cm, name) for name in dir(cm) if not name.startswith('_') and name not in ['show_cmaps']}
except ImportError:
    CMAPS = {'viridis': 'viridis', 'plasma': 'plasma', 'inferno': 'inferno'}


class OceanAnalysisGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Ocean Analysis')
        self.geometry('1100x950')
        self.resizable(True, True)

        # Apply dark theme
        self.setup_theme()

        self.cmems_files = list(cfg.CMEMS_FILES)
        self.gebco_file = cfg.GEBCO_FILE
        self.output_csv = cfg.OUTPUT_CSV
        self.output_image_dir = cfg.IMAGE_OUT_DIR
        self.selected_cmap = 'lapaz'
        self.selected_analysis = tk.StringVar(value='map')
        self.generate_csv = tk.BooleanVar(value=False)
        self.cancel_requested = False

        self.depth_up_var = tk.StringVar(value=str(cfg.DEPTH_UP))
        self.depth_down_var = tk.StringVar(value=str(cfg.DEPTH_DOWN))
        self.month_start_var = tk.StringVar(value=str(cfg.MONTH_START))
        self.month_end_var = tk.StringVar(value=str(cfg.MONTH_END))

        self.create_widgets()
        self.setup_logging()

    def setup_theme(self):
        self.BG_PRIMARY = '#0d1117'
        self.BG_SECONDARY = '#161b22'
        self.BG_TERTIARY = '#21262d'
        self.TEXT_PRIMARY = '#c9d1d9'
        self.TEXT_SECONDARY = '#8b949e'
        self.ACCENT = '#58a6ff'
        self.ACCENT_HOVER = '#79c0ff'
        self.BORDER = '#30363d'
        self.DANGER = '#f85149'
        self.DANGER_HOVER = '#ff6a69'
        
        self.configure(bg=self.BG_PRIMARY)
        
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TNotebook', background=self.BG_PRIMARY, borderwidth=0)
        
        style.configure('TNotebook.Tab', background=self.BG_SECONDARY, foreground=self.TEXT_SECONDARY, 
                       padding=[20, 10], borderwidth=0, focuscolor=self.BG_PRIMARY)
                       
        style.map('TNotebook.Tab', 
                  background=[('selected', self.BG_PRIMARY), ('active', self.BG_TERTIARY)], 
                  foreground=[('selected', self.ACCENT), ('active', self.TEXT_PRIMARY)])
                  
        style.configure('TNotebook.Client', background=self.BG_PRIMARY)
        
        style.configure('TCombobox', fieldbackground=self.BG_TERTIARY, background=self.BG_TERTIARY, 
                       foreground=self.TEXT_PRIMARY, borderwidth=1, relief='flat')
        style.map('TCombobox', fieldbackground=[('readonly', self.BG_TERTIARY)],
                 background=[('readonly', self.BG_TERTIARY)],
                 foreground=[('readonly', self.TEXT_PRIMARY)])
        
        style.configure('TScrollbar', background=self.BG_SECONDARY, troughcolor=self.BG_TERTIARY)

    def setup_logging(self):
        handler = GUILogHandler(self.log_text)
        handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def _create_button(self, parent, text, command, bg=None, hover=None):
        btn_bg = bg if bg else self.ACCENT
        btn_hover = hover if hover else self.ACCENT_HOVER
        return tk.Button(
            parent, text=text, command=command,
            bg=btn_bg, fg='white', font=('Segoe UI', 9, 'bold'),
            border=0, padx=12, pady=8, cursor='hand2',
            activebackground=btn_hover, activeforeground='white',
            relief='flat'
        )

    def _create_checkbox(self, parent, text, variable):
        frame = tk.Frame(parent, bg=parent.cget('bg'))
        
        def toggle():
            variable.set(not variable.get())
            update_appearance()
        
        def update_appearance():
            if variable.get():
                check_btn.config(bg=self.ACCENT, fg='white', text='✓')
            else:
                check_btn.config(bg=self.BG_TERTIARY, fg=self.BG_TERTIARY, text=' ')
        
        check_btn = tk.Button(
            frame, text=' ', width=2, command=toggle,
            bg=self.BG_TERTIARY, fg=self.BG_TERTIARY, 
            font=('Segoe UI', 10, 'bold'), border=0, padx=4, pady=2,
            activebackground=self.ACCENT, activeforeground='white'
        )
        check_btn.pack(side='left', padx=(0, 8))
        
        label = tk.Label(
            frame, text=text, bg=parent.cget('bg'), fg=self.TEXT_PRIMARY,
            font=('Segoe UI', 10), cursor='hand2'
        )
        label.pack(side='left')
        label.bind('<Button-1>', lambda e: toggle())
        update_appearance()
        return frame

    def _create_entry(self, parent, width=80):
        return tk.Entry(
            parent, width=width, bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY,
            relief='flat', borderwidth=0, insertbackground=self.ACCENT,
            font=('Consolas', 9)
        )

    def create_widgets(self):
        main_frame = tk.Frame(self, bg=self.BG_PRIMARY)
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 12))
        
        self.create_io_tab(notebook)
        self.create_parameters_tab(notebook)
        self.create_visualization_tab(notebook)
        self.create_data_analysis_tab(notebook)

        log_title = tk.Label(main_frame, text='Messages', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10, 'bold'))
        log_title.pack(anchor='w', pady=(12, 6))
        
        log_frame = tk.Frame(main_frame, bg=self.BG_TERTIARY, highlightthickness=1, highlightbackground=self.BORDER)
        log_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side='right', fill='y')

        self.log_text = tk.Text(
            log_frame, height=5, wrap='word', state='disabled',
            bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY, font=('Consolas', 9),
            yscrollcommand=scrollbar.set, insertbackground=self.ACCENT,
            relief='flat', borderwidth=0
        )
        self.log_text.pack(fill='both', expand=True, padx=8, pady=8)
        scrollbar.config(command=self.log_text.yview)

    def create_io_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.BG_PRIMARY)
        notebook.add(frame, text='Files')
        
        inner_frame = tk.Frame(frame, bg=self.BG_PRIMARY)
        inner_frame.pack(fill='both', expand=True, padx=12, pady=12)

        input_title = tk.Label(inner_frame, text='Input Files', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold'))
        input_title.pack(anchor='w', pady=(0, 10))
        
        input_frame = tk.Frame(inner_frame, bg=self.BG_SECONDARY)
        input_frame.pack(fill='x', pady=(0, 20))
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=0)

        tk.Label(input_frame, text='Data files:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', pady=(12, 4), padx=12)
        
        self.cmems_listbox = tk.Listbox(
            input_frame, height=5, activestyle='dotbox',
            bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY, selectbackground=self.ACCENT,
            relief='flat', borderwidth=0, highlightthickness=0
        )
        self.cmems_listbox.grid(row=1, column=0, sticky='we', padx=(12, 8), pady=(0, 8))
        self.update_cmems_listbox()

        btn_frame = tk.Frame(input_frame, bg=self.BG_SECONDARY)
        btn_frame.grid(row=1, column=1, sticky='ne', padx=(0, 12))
        self._create_button(btn_frame, '➕ Add', self.add_cmems_file).pack(fill='x', pady=(0, 6))
        self._create_button(btn_frame, '➖ Remove', self.remove_cmems_file).pack(fill='x')

        tk.Label(input_frame, text='Bathymetry files:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=2, column=0, sticky='w', pady=(8, 4), padx=12)
        
        self.gebco_entry = self._create_entry(input_frame)
        self.gebco_entry.insert(0, self.gebco_file)
        self.gebco_entry.grid(row=3, column=0, sticky='we', padx=(12, 8), pady=(0, 12))
        
        self._create_button(input_frame, '📁 Browse', self.browse_gebco_file).grid(row=3, column=1, sticky='e', padx=(0, 12), pady=(0, 12))

        output_title = tk.Label(inner_frame, text='Output Files', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold'))
        output_title.pack(anchor='w', pady=(0, 10))
        
        output_frame = tk.Frame(inner_frame, bg=self.BG_SECONDARY)
        output_frame.pack(fill='x')
        output_frame.columnconfigure(0, weight=1)
        output_frame.columnconfigure(1, weight=0)

        tk.Label(output_frame, text='CSV output:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', pady=(12, 4), padx=12)
        
        self.csv_entry = self._create_entry(output_frame)
        self.csv_entry.insert(0, self.output_csv)
        self.csv_entry.grid(row=1, column=0, sticky='we', padx=(12, 8), pady=(0, 8))
        
        self._create_button(output_frame, '📁 Browse', self.browse_output_csv).grid(row=1, column=1, sticky='e', padx=(0, 12), pady=(0, 8))

        self._create_checkbox(output_frame, 'Generate CSV file', self.generate_csv).grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 8), padx=12)

        tk.Label(output_frame, text='Image output directory:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=3, column=0, sticky='w', pady=(8, 4), padx=12)
        
        self.outdir_entry = self._create_entry(output_frame)
        self.outdir_entry.insert(0, self.output_image_dir)
        self.outdir_entry.grid(row=4, column=0, sticky='we', padx=(12, 8), pady=(0, 12))
        
        self._create_button(output_frame, '📁 Browse', self.browse_output_dir).grid(row=4, column=1, sticky='e', padx=(0, 12), pady=(0, 12))

    def create_parameters_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.BG_PRIMARY)
        notebook.add(frame, text='Analysis Parameters')
        inner_frame = tk.Frame(frame, bg=self.BG_PRIMARY)
        inner_frame.pack(fill='both', expand=True, padx=12, pady=12)

        tk.Label(inner_frame, text='Depth Range (metres)', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        depth_frame = tk.Frame(inner_frame, bg=self.BG_SECONDARY)
        depth_frame.pack(fill='x', pady=(0, 20))

        tk.Label(depth_frame, text='Upper limit:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=12, pady=12)
        entry = self._create_entry(depth_frame, width=12)
        entry.insert(0, self.depth_up_var.get())
        entry.grid(row=0, column=1, sticky='w', padx=(0, 12))
        entry.bind('<KeyRelease>', lambda e: self.depth_up_var.set(entry.get()))

        tk.Label(depth_frame, text='Lower limit:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', padx=12, pady=(0, 12))
        entry = self._create_entry(depth_frame, width=12)
        entry.insert(0, self.depth_down_var.get())
        entry.grid(row=1, column=1, sticky='w', padx=(0, 12))
        entry.bind('<KeyRelease>', lambda e: self.depth_down_var.set(entry.get()))

        tk.Label(inner_frame, text='Month Interval (average across all years)', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        month_frame = tk.Frame(inner_frame, bg=self.BG_SECONDARY)
        month_frame.pack(fill='x')

        tk.Label(month_frame, text='From month:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=12, pady=12)
        self.start_month_combo = ttk.Combobox(month_frame, values=[str(i) for i in range(1, 13)], width=5, state='readonly', textvariable=self.month_start_var)
        self.start_month_combo.grid(row=0, column=1, sticky='w', padx=(0, 12))

        tk.Label(month_frame, text='To month:', bg=self.BG_SECONDARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', padx=12, pady=(0, 12))
        self.end_month_combo = ttk.Combobox(month_frame, values=[str(i) for i in range(1, 13)], width=5, state='readonly', textvariable=self.month_end_var)
        self.end_month_combo.grid(row=1, column=1, sticky='w', padx=(0, 12))

    def create_visualization_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.BG_PRIMARY)
        notebook.add(frame, text='Visualization')
        inner_frame = tk.Frame(frame, bg=self.BG_PRIMARY)
        inner_frame.pack(fill='both', expand=True, padx=12, pady=12)

        tk.Label(inner_frame, text='Color Scheme', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        tk.Label(inner_frame, text='Select colormap:', bg=self.BG_PRIMARY, fg=self.TEXT_SECONDARY, font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 8))

        cmap_list_frame = tk.Frame(inner_frame, bg=self.BG_TERTIARY, highlightthickness=1, highlightbackground=self.BORDER)
        cmap_list_frame.pack(fill='both', expand=True, pady=(0, 15))

        scrollbar = ttk.Scrollbar(cmap_list_frame)
        scrollbar.pack(side='right', fill='y')

        self.cmap_listbox = tk.Listbox(
            cmap_list_frame, height=8, bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY,
            selectbackground=self.ACCENT, yscrollcommand=scrollbar.set, relief='flat', borderwidth=0, highlightthickness=0
        )
        self.cmap_listbox.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        scrollbar.config(command=self.cmap_listbox.yview)

        cmap_names = sorted(CMAPS.keys())
        for name in cmap_names:
            self.cmap_listbox.insert(tk.END, name)

        if 'lapaz' in cmap_names:
            idx = cmap_names.index('lapaz')
            self.cmap_listbox.selection_set(idx)
            self.cmap_listbox.see(idx)

        self.cmap_listbox.bind('<<ListboxSelect>>', self.on_cmap_select)

        tk.Label(inner_frame, text='Preview', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 8))
        self.preview_canvas = tk.Canvas(inner_frame, width=500, height=60, bg=self.BG_TERTIARY, highlightthickness=1, highlightbackground=self.BORDER)
        self.preview_canvas.pack(fill='x')
        self.update_cmap_preview()

    def create_data_analysis_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.BG_PRIMARY)
        notebook.add(frame, text='Data analysis')

        inner = tk.Frame(frame, bg=self.BG_PRIMARY)
        inner.pack(fill='both', expand=True, padx=12, pady=12)

        self.button_frame = tk.Frame(inner, bg=self.BG_PRIMARY)
        self.button_frame.pack(side='bottom', fill='x', pady=(12, 0))

        self.run_button = tk.Button(
            self.button_frame, text='▶ Run Analysis', command=self.start_analysis,
            bg=self.ACCENT, fg='white', font=('Segoe UI', 11, 'bold'),
            border=0, padx=20, pady=12, cursor='hand2',
            activebackground=self.ACCENT_HOVER, activeforeground='white'
        )
        self.run_button.pack(side='left', fill='x', expand=True, padx=(0, 6))

        self.cancel_button = tk.Button(
            self.button_frame, text='⏹ Cancel', command=self.cancel_analysis,
            bg=self.DANGER, fg='white', font=('Segoe UI', 11, 'bold'),
            border=0, padx=20, pady=12, cursor='hand2',
            activebackground=self.DANGER_HOVER, activeforeground='white',
            state='disabled'
        )
        self.cancel_button.pack(side='right', fill='x', expand=True, padx=(6, 0))

        tk.Label(inner, text='Data Analysis Type', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY, font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(0, 12))

        type_frame = tk.Frame(inner, bg=self.BG_PRIMARY)
        type_frame.pack(fill='x', pady=(0, 15))
        
        self.map_btn = tk.Button(
            type_frame, text='Map Analysis', command=lambda: self.set_analysis_type('map'),
            font=('Segoe UI', 10, 'bold'), border=0, padx=16, pady=8, cursor='hand2'
        )
        self.map_btn.pack(side='left', padx=(0, 8))
        
        self.section_btn = tk.Button(
            type_frame, text='Section Analysis', command=lambda: self.set_analysis_type('section'),
            font=('Segoe UI', 10, 'bold'), border=0, padx=16, pady=8, cursor='hand2'
        )
        self.section_btn.pack(side='left')

        self.section_container = tk.Frame(inner, bg=self.BG_PRIMARY)
        
        self.section_info_label = tk.Label(
            self.section_container, 
            text='Load preview, then: Scroll to Zoom | Middle-Click or CTRL+Left-Click to Pan | Left-Click to set points', 
            bg=self.BG_PRIMARY, fg=self.TEXT_SECONDARY, font=('Segoe UI', 9)
        )
        self.section_info_label.pack(anchor='w', pady=(6,8))

        preview_controls = tk.Frame(self.section_container, bg=self.BG_PRIMARY)
        preview_controls.pack(fill='x')
        self._create_button(preview_controls, 'Load preview', self.load_section_preview).pack(side='left')
        self._create_button(preview_controls, 'Clear selection', self.clear_section_selection, bg=self.BG_TERTIARY, hover=self.BORDER).pack(side='left', padx=(8,0))

        self.section_canvas = tk.Canvas(self.section_container, bg=self.BG_TERTIARY, height=300, highlightthickness=1, highlightbackground=self.BORDER)
        self.section_canvas.pack(fill='both', expand=True, pady=(10,0))

        coords_frame = tk.Frame(self.section_container, bg=self.BG_PRIMARY)
        coords_frame.pack(fill='x', pady=(8,0))
        self.coord_beg_label = tk.Label(coords_frame, text='Start: -', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY)
        self.coord_beg_label.pack(side='left', padx=(0,12))
        self.coord_end_label = tk.Label(coords_frame, text='End: -', bg=self.BG_PRIMARY, fg=self.TEXT_PRIMARY)
        self.coord_end_label.pack(side='left')
        self.live_coord_label = tk.Label(coords_frame, text='Cursor: -', bg=self.BG_PRIMARY, fg=self.TEXT_SECONDARY)
        self.live_coord_label.pack(side='right', padx=(0,12))

        self._section_preview_image = None
        self.section_lonlat_extent = None
        self.section_points = []
        self._pan_start_x = None
        self._pan_start_y = None
        
        # Point Selection & Hover
        self.section_canvas.bind('<Button-1>', self.on_section_click)
        self.section_canvas.bind('<Motion>', self.on_section_hover)

        # Scroll Wheel Zoom Binds (Windows/Mac and Linux)
        self.section_canvas.bind('<MouseWheel>', self.on_mouse_wheel)
        self.section_canvas.bind('<Button-4>', self.on_mouse_wheel)
        self.section_canvas.bind('<Button-5>', self.on_mouse_wheel)

        # Pan Binds (Middle Mouse Button)
        self.section_canvas.bind('<ButtonPress-2>', self.on_pan_start)
        self.section_canvas.bind('<B2-Motion>', self.on_pan_motion)

        # Pan Binds (CTRL + Left Click)
        self.section_canvas.bind('<Control-ButtonPress-1>', self.on_pan_start)
        self.section_canvas.bind('<Control-B1-Motion>', self.on_pan_motion)

        self.set_analysis_type('map')

    def set_analysis_type(self, type_str):
        self.selected_analysis.set(type_str)
        if type_str == 'map':
            self.map_btn.config(bg=self.ACCENT, fg='white')
            self.section_btn.config(bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY)
            self.section_container.pack_forget()
        else:
            self.section_btn.config(bg=self.ACCENT, fg='white')
            self.map_btn.config(bg=self.BG_TERTIARY, fg=self.TEXT_PRIMARY)
            self.section_container.pack(fill='both', expand=True, pady=(10,0))

    def on_cmap_select(self, event):
        selection = self.cmap_listbox.curselection()
        if selection:
            cmap_names = sorted(CMAPS.keys())
            self.selected_cmap = cmap_names[selection[0]]
            self.update_cmap_preview()

    def update_cmap_preview(self):
        try:
            import matplotlib.pyplot as plt
            import numpy as np

            self.preview_canvas.update_idletasks()
            canvas_width = max(self.preview_canvas.winfo_width(), 500)
            height = 60

            cmap_obj = CMAPS.get(self.selected_cmap)
            if cmap_obj is None:
                cmap_obj = plt.get_cmap('viridis')
            elif isinstance(cmap_obj, str):
                cmap_obj = plt.get_cmap(cmap_obj)

            colors = cmap_obj(np.linspace(0, 1, canvas_width))
            img = Image.new('RGB', (canvas_width, height))
            pixels = img.load()

            for x in range(canvas_width):
                r, g, b = colors[x][:3]
                rgb_color = (int(r * 255), int(g * 255), int(b * 255))
                for y in range(height):
                    pixels[x, y] = rgb_color

            with io.BytesIO() as output:
                img.save(output, format='PPM')
                photo = tk.PhotoImage(data=output.getvalue())
            
            self.preview_canvas.delete('all')
            self.preview_canvas.create_image(0, 0, image=photo, anchor='nw')
            self.preview_canvas.image = photo
        except Exception:
            pass

    def check_cancel(self):
        if self.cancel_requested:
            raise InterruptedError('Analysis cancelled by user.')

    def load_section_preview(self):
        try:
            config = self.validate_inputs()
        except Exception as exc:
            messagebox.showerror('Invalid input', str(exc))
            return

        try:
            processor = OceanDataProcessor(config['cmems_files'], config['gebco_file'])
            lon_bathy, lat_bathy, elevation = processor.process_bathymetry()

            import numpy as np
            import matplotlib.pyplot as plt
            
            # --- Store bathymetry data for dynamic depth lookup ---
            self._lon_bathy = lon_bathy
            self._lat_bathy = lat_bathy
            self._elevation = np.array(elevation)

            minlon, maxlon = float(lon_bathy.min()), float(lon_bathy.max())
            minlat, maxlat = float(lat_bathy.min()), float(lat_bathy.max())
            self.base_extent = (minlon, maxlon, minlat, maxlat)
            self.section_lonlat_extent = self.base_extent

            elev = np.array(elevation)
            vmin = np.nanpercentile(elev, 2)
            vmax = np.nanpercentile(elev, 98)
            norm = plt.Normalize(vmin=vmin, vmax=vmax)
            cmap_obj = CMAPS.get(self.selected_cmap)
            if cmap_obj is None:
                cmap_obj = plt.get_cmap('viridis')
            arr = cmap_obj(norm(elev))

            img = Image.fromarray((255 * arr).astype('uint8'))
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            self._base_preview_image = img

            self.section_points = []
            self.coord_beg_label.config(text='Start: -')
            self.coord_end_label.config(text='End: -')
            
            self._render_preview()
            
        except Exception as exc:
            logger.error(f'Failed to load preview: {exc}')
            messagebox.showerror('Preview error', f'Could not generate preview:\n{exc}')

    def _render_preview(self):
        if not hasattr(self, '_base_preview_image') or self._base_preview_image is None:
            return

        base_minlon, base_maxlon, base_minlat, base_maxlat = self.base_extent
        cur_minlon, cur_maxlon, cur_minlat, cur_maxlat = self.section_lonlat_extent

        base_w, base_h = self._base_preview_image.size
        lon_range = base_maxlon - base_minlon
        lat_range = base_maxlat - base_minlat

        left = int((cur_minlon - base_minlon) / lon_range * base_w)
        right = int((cur_maxlon - base_minlon) / lon_range * base_w)
        top = int((base_maxlat - cur_maxlat) / lat_range * base_h)
        bottom = int((base_maxlat - cur_minlat) / lat_range * base_h)

        cropped_img = self._base_preview_image.crop((left, top, right, bottom))
        
        self.section_canvas.update_idletasks()
        canvas_w = max(self.section_canvas.winfo_width(), 300)
        canvas_h = max(self.section_canvas.winfo_height(), 300)

        # Calculate true physical aspect ratio to prevent stretching
        mean_lat = math.radians((cur_minlat + cur_maxlat) / 2.0)
        physical_aspect_ratio = ((cur_maxlon - cur_minlon) * math.cos(mean_lat)) / max(1e-6, (cur_maxlat - cur_minlat))
        
        canvas_ratio = canvas_w / canvas_h
        
        if physical_aspect_ratio > canvas_ratio:
            # Fit to width
            cw = canvas_w
            ch = int(cw / physical_aspect_ratio)
        else:
            # Fit to height
            ch = canvas_h
            cw = int(ch * physical_aspect_ratio)

        # Save actual image dimensions for coordinate math
        self._preview_cw = cw
        self._preview_ch = ch

        resized_img = cropped_img.resize((cw, ch), resample=Image.BILINEAR)

        with io.BytesIO() as output:
            resized_img.save(output, format='PPM')
            photo = tk.PhotoImage(data=output.getvalue())

        self.section_canvas.delete('all')
        self.section_canvas.create_image(0, 0, image=photo, anchor='nw')
        self.section_canvas.image = photo
        self._section_preview_image = resized_img
        
        self._redraw_selection()
        self._draw_scale_bar()

    def _draw_scale_bar(self):
        if self.section_lonlat_extent is None:
            return
            
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        cw = getattr(self, '_preview_cw', self.section_canvas.winfo_width())
        ch = getattr(self, '_preview_ch', self.section_canvas.winfo_height())
        
        if cw < 50 or ch < 50:
            return

        center_lat = (minlat + maxlat) / 2.0
        R = 6371.0 # Radius of the Earth in km
        
        # Haversine distance for the current map width
        lat_rad = math.radians(center_lat)
        dlon_rad = math.radians(maxlon - minlon)
        a = math.cos(lat_rad) * math.cos(lat_rad) * (math.sin(dlon_rad / 2.0) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        width_km = R * c
        
        # Target scale width is roughly 150px
        target_px = min(150, cw * 0.4) 
        if target_px <= 0: return
        target_km = (target_px / cw) * width_km
        
        if target_km <= 0: return
        
        # Round to a clean number
        magnitude = 10 ** math.floor(math.log10(target_km))
        val = target_km / magnitude
        if val < 2: nice_val = 1
        elif val < 5: nice_val = 2
        elif val < 10: nice_val = 5
        else: nice_val = 10
        nice_km = nice_val * magnitude
        
        scale_px = (nice_km / width_km) * cw
        
        pad_x, pad_y = 15, 15
        x1 = pad_x
        y1 = ch - pad_y
        x2 = x1 + scale_px
        y2 = y1
        
        # Semi-transparent/dark background box for the scale bar
        self.section_canvas.create_rectangle(x1 - 5, y1 - 22, x2 + 5, y1 + 5, fill=self.BG_TERTIARY, outline=self.BORDER, tags='scale')
        
        self.section_canvas.create_line(x1, y1, x2, y2, fill=self.TEXT_PRIMARY, width=2, tags='scale')
        self.section_canvas.create_line(x1, y1 - 4, x1, y1 + 4, fill=self.TEXT_PRIMARY, width=2, tags='scale')
        self.section_canvas.create_line(x2, y1 - 4, x2, y1 + 4, fill=self.TEXT_PRIMARY, width=2, tags='scale')
        
        text_val = int(nice_km) if nice_km.is_integer() else nice_km
        self.section_canvas.create_text(x1 + scale_px/2, y1 - 12, text=f'{text_val} km', fill=self.TEXT_PRIMARY, font=('Segoe UI', 9, 'bold'), tags='scale')

    def on_mouse_wheel(self, event):
        if self.section_lonlat_extent is None:
            return
        
        zoom_in = False
        if event.num == 4 or getattr(event, 'delta', 0) > 0:
            zoom_in = True
        elif event.num == 5 or getattr(event, 'delta', 0) < 0:
            zoom_in = False
        else:
            return

        factor = 0.8 if zoom_in else 1.25
        self._zoom(factor, event.x, event.y)

    def _zoom(self, factor, cx=None, cy=None):
        if not hasattr(self, 'section_lonlat_extent') or self.section_lonlat_extent is None:
            return
        
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        cw = getattr(self, '_preview_cw', max(1, self.section_canvas.winfo_width()))
        ch = getattr(self, '_preview_ch', max(1, self.section_canvas.winfo_height()))
        
        if cx is not None and cy is not None and cx <= cw and cy <= ch:
            focus_lon = minlon + (cx / cw) * (maxlon - minlon)
            focus_lat = maxlat - (cy / ch) * (maxlat - minlat)
        else:
            focus_lon = (minlon + maxlon) / 2
            focus_lat = (minlat + maxlat) / 2
            cx = cw / 2
            cy = ch / 2
            
        new_lon_span = (maxlon - minlon) * factor
        new_lat_span = (maxlat - minlat) * factor
        
        rel_x = cx / cw
        rel_y = cy / ch
        new_minlon = focus_lon - new_lon_span * rel_x
        new_maxlon = focus_lon + new_lon_span * (1 - rel_x)
        new_minlat = focus_lat - new_lat_span * (1 - rel_y)
        new_maxlat = focus_lat + new_lat_span * rel_y
        
        b_minlon, b_maxlon, b_minlat, b_maxlat = self.base_extent
        
        if new_maxlon - new_minlon > b_maxlon - b_minlon:
            new_minlon, new_maxlon = b_minlon, b_maxlon
        if new_maxlat - new_minlat > b_maxlat - b_minlat:
            new_minlat, new_maxlat = b_minlat, b_maxlat
            
        if new_minlon < b_minlon: 
            new_maxlon += (b_minlon - new_minlon)
            new_minlon = b_minlon
        if new_maxlon > b_maxlon: 
            new_minlon -= (new_maxlon - b_maxlon)
            new_maxlon = b_maxlon
        if new_minlat < b_minlat: 
            new_maxlat += (b_minlat - new_minlat)
            new_minlat = b_minlat
        if new_maxlat > b_maxlat: 
            new_minlat -= (new_maxlat - b_maxlat)
            new_maxlat = b_maxlat

        self.section_lonlat_extent = (new_minlon, new_maxlon, new_minlat, new_maxlat)
        self._render_preview()

    def on_pan_start(self, event):
        if self.section_lonlat_extent is None:
            return
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def on_pan_motion(self, event):
        if self.section_lonlat_extent is None or self._pan_start_x is None:
            return
        
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        
        cw = getattr(self, '_preview_cw', max(1, self.section_canvas.winfo_width()))
        ch = getattr(self, '_preview_ch', max(1, self.section_canvas.winfo_height()))
        
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        lon_span = maxlon - minlon
        lat_span = maxlat - minlat
        
        dlon = -(dx / cw) * lon_span
        dlat = (dy / ch) * lat_span
        
        new_minlon, new_maxlon = minlon + dlon, maxlon + dlon
        new_minlat, new_maxlat = minlat + dlat, maxlat + dlat
        
        b_minlon, b_maxlon, b_minlat, b_maxlat = self.base_extent
        
        if new_minlon < b_minlon:
            new_minlon, new_maxlon = b_minlon, b_minlon + lon_span
        if new_maxlon > b_maxlon:
            new_maxlon, new_minlon = b_maxlon, b_maxlon - lon_span
        if new_minlat < b_minlat:
            new_minlat, new_maxlat = b_minlat, b_minlat + lat_span
        if new_maxlat > b_maxlat:
            new_maxlat, new_minlat = b_maxlat, b_maxlat - lat_span

        self.section_lonlat_extent = (new_minlon, new_maxlon, new_minlat, new_maxlat)
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._render_preview()

    def _redraw_selection(self):
        self.section_canvas.delete('sel')
        if not hasattr(self, 'section_points') or not self.section_points:
            return
        
        cw = getattr(self, '_preview_cw', max(1, self.section_canvas.winfo_width()))
        ch = getattr(self, '_preview_ch', max(1, self.section_canvas.winfo_height()))
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        
        r = 6
        for lon, lat in self.section_points:
            x = int((lon - minlon) / (maxlon - minlon) * cw)
            y = int((maxlat - lat) / (maxlat - minlat) * ch)
            if 0 <= x <= cw and 0 <= y <= ch:
                self.section_canvas.create_oval(x - r, y - r, x + r, y + r, outline=self.ACCENT, width=2, tags='sel')
            
        if len(self.section_points) == 2:
            lon0, lat0 = self.section_points[0]
            lon1, lat1 = self.section_points[1]
            x0 = int((lon0 - minlon) / (maxlon - minlon) * cw)
            y0 = int((maxlat - lat0) / (maxlat - minlat) * ch)
            x1 = int((lon1 - minlon) / (maxlon - minlon) * cw)
            y1 = int((maxlat - lat1) / (maxlat - minlat) * ch)
            self.section_canvas.create_line(x0, y0, x1, y1, fill=self.ACCENT, width=2, tags='sel')

    def on_section_click(self, event):
        if event.state & 0x0004: # Ignore click if Control key is pressed
            return

        if self._section_preview_image is None or self.section_lonlat_extent is None:
            return
        
        cw = getattr(self, '_preview_cw', max(1, self.section_canvas.winfo_width()))
        ch = getattr(self, '_preview_ch', max(1, self.section_canvas.winfo_height()))
        
        # Ensure click is within image boundaries
        if event.x > cw or event.y > ch:
            return 
            
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        lon = minlon + (event.x / cw) * (maxlon - minlon)
        lat = maxlat - (event.y / ch) * (maxlat - minlat)

        if len(self.section_points) >= 2:
            self.section_points = []
            
        self.section_points.append((lon, lat))
        self._redraw_selection()

        if len(self.section_points) == 2:
            lon0, lat0 = self.section_points[0]
            lon1, lat1 = self.section_points[1]
            self.coord_beg_label.config(text=f'Start: {lon0:.4f}, {lat0:.4f}')
            self.coord_end_label.config(text=f'End: {lon1:.4f}, {lat1:.4f}')

    def on_section_hover(self, event):
        if self.section_lonlat_extent is None:
            return
            
        cw = getattr(self, '_preview_cw', max(1, self.section_canvas.winfo_width()))
        ch = getattr(self, '_preview_ch', max(1, self.section_canvas.winfo_height()))
        
        if event.x > cw or event.y > ch:
            self.live_coord_label.config(text='Cursor: Out of bounds')
            return
            
        minlon, maxlon, minlat, maxlat = self.section_lonlat_extent
        lon = minlon + (event.x / cw) * (maxlon - minlon)
        lat = maxlat - (event.y / ch) * (maxlat - minlat)
        
        # --- Add dynamic depth lookup ---
        depth_info = ""
        if hasattr(self, '_lon_bathy'):
            import numpy as np
            # Find the nearest lat/lon indices in the stored arrays
            idx_lon = (np.abs(self._lon_bathy - lon)).argmin()
            idx_lat = (np.abs(self._lat_bathy - lat)).argmin()
            
            # Extract depth value
            z = self._elevation[idx_lat, idx_lon]
            
            # Land points are filtered as np.nan
            if np.isnan(z):
                depth_info = " | Depth: Land"
            else:
                depth_info = f" | Depth: {abs(z):.0f} m"

        self.live_coord_label.config(text=f'Cursor: {lon:.4f}°, {lat:.4f}°{depth_info}')

    def clear_section_selection(self):
        self.section_points = []
        if hasattr(self, 'section_canvas'):
            self.section_canvas.delete('sel')
        self.coord_beg_label.config(text='Start: -')
        self.coord_end_label.config(text='End: -')

    def add_cmems_file(self):
        files = filedialog.askopenfilenames(title='Select Data files', filetypes=[('NetCDF files', '*.nc'), ('All files', '*.*')])
        if files:
            for path in files:
                if path not in self.cmems_files:
                    self.cmems_files.append(path)
            self.update_cmems_listbox()

    def remove_cmems_file(self):
        selection = self.cmems_listbox.curselection()
        if selection:
            self.cmems_files.pop(selection[0])
            self.update_cmems_listbox()

    def update_cmems_listbox(self):
        self.cmems_listbox.delete(0, tk.END)
        for path in self.cmems_files:
            self.cmems_listbox.insert(tk.END, path)

    def browse_gebco_file(self):
        path = filedialog.askopenfilename(title='Select Bathymetry file', filetypes=[('NetCDF files', '*.nc'), ('All files', '*.*')])
        if path:
            self.gebco_file = path
            self.gebco_entry.delete(0, tk.END)
            self.gebco_entry.insert(0, path)

    def browse_output_csv(self):
        path = filedialog.asksaveasfilename(
            title='Save CSV output as', defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            initialfile=os.path.basename(self.output_csv),
            initialdir=os.path.dirname(self.output_csv) or '.'
        )
        if path:
            self.output_csv = path
            self.csv_entry.delete(0, tk.END)
            self.csv_entry.insert(0, path)

    def browse_output_dir(self):
        path = filedialog.askdirectory(title='Select image output directory', initialdir=self.output_image_dir)
        if path:
            self.output_image_dir = path
            self.outdir_entry.delete(0, tk.END)
            self.outdir_entry.insert(0, path)

    def validate_inputs(self):
        if not self.cmems_files: raise ValueError('At least one Data input file must be selected.')
        for path in self.cmems_files:
            if not os.path.isfile(path): raise FileNotFoundError(f'Data file not found: {path}')
        
        gebco_file = self.gebco_entry.get().strip()
        if not gebco_file: raise ValueError('A Bathymetry file must be selected.')
        if not os.path.isfile(gebco_file): raise FileNotFoundError(f'Bathymetry file not found: {gebco_file}')
        
        output_image_dir = self.outdir_entry.get().strip()
        if not output_image_dir: raise ValueError('An image output directory must be selected.')
        
        output_csv = self.csv_entry.get().strip() if self.generate_csv.get() else None
        if self.generate_csv.get() and not output_csv: raise ValueError('An output CSV file must be specified.')

        try:
            depth_up, depth_down = float(self.depth_up_var.get()), float(self.depth_down_var.get())
        except ValueError:
            raise ValueError('Depth bounds must be numeric.')
        if depth_up < 0 or depth_down < 0: raise ValueError('Depth values cannot be negative.')
        if depth_up > depth_down: raise ValueError('Depth upper limit must be <= lower limit.')

        try:
            month_start, month_end = int(self.month_start_var.get()), int(self.month_end_var.get())
        except ValueError:
            raise ValueError('Month values must be integers between 1 and 12.')
        if not 1 <= month_start <= 12 or not 1 <= month_end <= 12: raise ValueError('Month values must be between 1 and 12.')

        return {
            'cmems_files': self.cmems_files, 'gebco_file': gebco_file,
            'output_csv': output_csv, 'output_image_dir': output_image_dir,
            'depth_up': depth_up, 'depth_down': depth_down,
            'month_start': month_start, 'month_end': month_end,
            'generate_csv': self.generate_csv.get()
        }

    def start_analysis(self):
        try:
            config = self.validate_inputs()
        except Exception as exc:
            logger.error(f'Validation error: {exc}')
            messagebox.showerror('Invalid input', str(exc))
            return
            
        self.cancel_requested = False
        self.run_button.config(state='disabled', bg=self.BG_TERTIARY, cursor='arrow', text='Running...')
        self.cancel_button.config(state='normal', cursor='hand2')
        
        threading.Thread(target=self._analysis_worker, args=(config,), daemon=True).start()

    def cancel_analysis(self):
        self.cancel_requested = True
        self.cancel_button.config(state='disabled', text='Cancelling...', cursor='arrow')
        logger.warning('Cancellation requested. Stopping after the current operation finishes...')

    def reset_buttons(self):
        self.run_button.config(state='normal', bg=self.ACCENT, cursor='hand2', text='▶ Run Analysis')
        self.cancel_button.config(state='disabled', text='⏹ Cancel', cursor='arrow')

    def _analysis_worker(self, config):
        try:
            if self.selected_analysis.get() == 'section':
                self.run_section_analysis(config)
            else:
                self.run_map_analysis(config)
        except InterruptedError:
            logger.warning('✓ Analysis cancelled successfully.')
        except Exception as exc:
            logger.error(f'Analysis failed: {exc}')
            self.after(0, lambda: messagebox.showerror('Error', f'An error occurred:\n{exc}'))
        finally:
            self.after(0, self.reset_buttons)

    def run_section_analysis(self, config):
        if not self.section_points or len(self.section_points) < 2:
            raise ValueError('Section start and end points must be selected on the preview.')

        self.section_info_label.config(text='Running section analysis...')
        logger.warning('Section analysis starting...')

        coord_beg, coord_end = self.section_points[0], self.section_points[1]
        logger.warning(f'Section endpoints set: start={coord_beg[0]:.4f},{coord_beg[1]:.4f} end={coord_end[0]:.4f},{coord_end[1]:.4f}')

        self.check_cancel()
        os.makedirs(config['output_image_dir'], exist_ok=True)
        
        logger.warning('Loading datasets and bathymetry...')
        processor = OceanDataProcessor(config['cmems_files'], config['gebco_file'])
        lon_bathy, lat_bathy, elevation = processor.process_bathymetry()

        self.check_cancel()
        logger.warning('Computing section results... this may take a moment.')
        plotter.create_section_plots(
            processor, coord_beg, coord_end,
            config['month_start'], config['month_end'],
            config['output_image_dir'], cmap_name=self.selected_cmap
        )

        self.check_cancel()
        if config['generate_csv']:
            logger.warning('CSV export for section not implemented; skipping CSV.')

        logger.warning('✓ Section analysis complete!')
        self.section_info_label.config(text='Section analysis complete.')

    def run_map_analysis(self, config):
        logger.warning('Map Analysis starting...')
        
        self.check_cancel()
        os.makedirs(config['output_image_dir'], exist_ok=True)
        processor = OceanDataProcessor(config['cmems_files'], config['gebco_file'])
        lon_bathy, lat_bathy, elevation = processor.process_bathymetry()

        lon_ocean = processor.ds_ocean.longitude.values
        lat_ocean = processor.ds_ocean.latitude.values
        extent = [lon_ocean.min(), lon_ocean.max(), lat_ocean.min(), lat_ocean.max()]

        self.check_cancel()
        logger.warning('Calculating bottom currents...')
        bottom_data, bottom_depth = processor.get_bottom_currents(config['month_start'], config['month_end'])

        self.check_cancel()
        logger.warning('Calculating depth-averaged currents...')
        currents_data = processor.get_depth_averaged_currents(
            config['depth_up'], config['depth_down'],
            config['month_start'], config['month_end']
        )

        depth_down_matrix = bottom_depth.where(bottom_depth < config['depth_down'], config['depth_down'])

        self.check_cancel()
        logger.warning('Generating bathymetry plots...')
        plotter.create_bathymetry_plot(
            lon_bathy, lat_bathy, elevation,
            bottom_depth, depth_down_matrix,
            extent, config['output_image_dir']
        )

        self.check_cancel()
        logger.warning('Generating velocity plots...')
        bottom_mean = bottom_data.mean(dim='time', skipna=True)
        currents_mean = currents_data.mean(dim='time', skipna=True)
        plotter.create_velocity_plot(
            currents_mean, bottom_mean,
            lon_bathy, lat_bathy, elevation,
            extent, cfg.SPATIAL_STEP, 'fig2_mean_velocity.png', config['output_image_dir']
        )

        self.check_cancel()
        if config['generate_csv']:
            logger.warning('Exporting data to CSV...')
            os.makedirs(os.path.dirname(config['output_csv']) or '.', exist_ok=True)
            processor.export_to_csv(bottom_data, currents_data, bottom_depth, config['output_csv'])

        logger.warning('✓ Map Analysis complete!')
        self.after(0, lambda: messagebox.showinfo('Success', 'Analysis finished successfully!'))

if __name__ == '__main__':
    app = OceanAnalysisGUI()
    app.mainloop()