"""Modern glassmorphism-styled settings window with smooth animations."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, Any
from PIL import Image, ImageDraw, ImageTk

from ..config.manager import ConfigManager
from ..audio.capture import AudioCapture
from .effects import ColorTheme, ease_out_sine, interpolate_color


class ModernButton(tk.Canvas):
    """Custom modern button with gradient and hover effects."""
    
    def __init__(
        self,
        parent,
        text: str,
        command: Optional[Callable] = None,
        width: int = 120,
        height: int = 36,
        primary: bool = False,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
        )
        
        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.primary = primary
        
        self._is_hovering = False
        self._is_pressed = False
        self._animation_progress = 0.0
        
        # Bind events
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        
        self._draw()
    
    def _draw(self):
        """Draw the button."""
        self.delete('all')
        
        w, h = self.width, self.height
        
        # Choose colors based on state
        if self.primary:
            if self._is_pressed:
                bg_color = '#6366f1'
            elif self._is_hovering:
                bg_color = '#8b5cf6'
            else:
                bg_color = '#7c3aed'
        else:
            if self._is_pressed:
                bg_color = ColorTheme.BG_CARD
            elif self._is_hovering:
                bg_color = ColorTheme.BORDER_LIGHT
            else:
                bg_color = ColorTheme.BORDER
        
        # Draw rounded rectangle background
        self._create_rounded_rect(2, 2, w-2, h-2, radius=8, fill=bg_color, outline='')
        
        # Draw text
        text_color = ColorTheme.TEXT_PRIMARY
        self.create_text(
            w // 2, h // 2,
            text=self.text,
            fill=text_color,
            font=('Segoe UI', 10, 'normal')
        )
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        """Create a rounded rectangle."""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _on_enter(self, event):
        """Handle mouse enter."""
        self._is_hovering = True
        self._draw()
    
    def _on_leave(self, event):
        """Handle mouse leave."""
        self._is_hovering = False
        self._draw()
    
    def _on_press(self, event):
        """Handle button press."""
        self._is_pressed = True
        self._draw()
    
    def _on_release(self, event):
        """Handle button release."""
        self._is_pressed = False
        self._draw()
        if self._is_hovering and self.command:
            self.command()


class ModernEntry(tk.Frame):
    """Custom modern entry field with rounded corners and styling."""
    
    def __init__(self, parent, textvariable=None, width=30, **kwargs):
        super().__init__(parent, bg=ColorTheme.BG_DARK)
        
        # Create canvas for rounded background
        self.canvas = tk.Canvas(
            self,
            height=32,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.X, expand=True)
        
        # Draw rounded background
        self._draw_background()
        
        # Create entry widget on top
        self.entry = tk.Entry(
            self.canvas,
            textvariable=textvariable,
            bg=ColorTheme.BG_CARD,
            fg=ColorTheme.TEXT_PRIMARY,
            insertbackground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT,
            font=('Segoe UI', 10),
            width=width,
            **kwargs
        )
        
        # Place entry in canvas
        self.canvas.create_window(4, 16, anchor=tk.W, window=self.entry)
        
        # Bind focus events for highlighting
        self.entry.bind('<FocusIn>', lambda e: self._on_focus(True))
        self.entry.bind('<FocusOut>', lambda e: self._on_focus(False))
    
    def _draw_background(self, focused=False):
        """Draw the rounded background."""
        self.canvas.delete('background')
        
        border_color = ColorTheme.ACCENT_PRIMARY if focused else ColorTheme.BORDER
        
        # Draw rounded rectangle
        w = self.canvas.winfo_reqwidth() or 200
        self._create_rounded_rect(
            self.canvas, 0, 0, w, 32,
            radius=6,
            fill=ColorTheme.BG_CARD,
            outline=border_color,
            width=1,
            tags='background'
        )
        self.canvas.tag_lower('background')
    
    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius=10, **kwargs):
        """Create a rounded rectangle."""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)
    
    def _on_focus(self, has_focus):
        """Handle focus change."""
        self._draw_background(has_focus)
    
    def get(self):
        """Get entry value."""
        return self.entry.get()


class ModernTitleBar(tk.Canvas):
    """Custom modern title bar with close/minimize buttons."""
    
    def __init__(self, parent, title: str, on_close=None, on_minimize=None):
        super().__init__(
            parent,
            height=40,
            bg=ColorTheme.BG_DARKER,
            highlightthickness=0,
        )
        
        self.title = title
        self.on_close = on_close
        self.on_minimize = on_minimize
        self.parent_window = parent
        
        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Button states
        self._close_hover = False
        self._minimize_hover = False
        
        # Bind events for dragging
        self.bind('<ButtonPress-1>', self._start_drag)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<Motion>', self._on_motion)
        self.bind('<Leave>', self._on_leave)
        
        self.pack(fill=tk.X)
        self._draw()
    
    def _draw(self):
        """Draw the title bar."""
        self.delete('all')
        
        width = self.winfo_width() or 640
        height = 40
        
        # Background
        self.create_rectangle(0, 0, width, height, fill=ColorTheme.BG_DARKER, outline='')
        
        # Title text
        self.create_text(
            16, height // 2,
            text=self.title,
            fill=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 11, 'bold'),
            anchor=tk.W
        )
        
        # Close button (X)
        close_x = width - 20
        close_y = height // 2
        close_color = '#ef4444' if self._close_hover else ColorTheme.TEXT_SECONDARY
        
        self.create_text(
            close_x, close_y,
            text='×',
            fill=close_color,
            font=('Segoe UI', 20, 'bold'),
            tags='close_btn'
        )
        
        # Minimize button (–)
        minimize_x = width - 50
        minimize_y = height // 2
        minimize_color = ColorTheme.TEXT_PRIMARY if self._minimize_hover else ColorTheme.TEXT_SECONDARY
        
        self.create_text(
            minimize_x, minimize_y,
            text='─',
            fill=minimize_color,
            font=('Segoe UI', 12, 'bold'),
            tags='minimize_btn'
        )
    
    def _start_drag(self, event):
        """Start dragging the window."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        """Drag the window."""
        try:
            # Get the parent window
            window = self.parent_window
            x = window.winfo_x() + (event.x - self._drag_start_x)
            y = window.winfo_y() + (event.y - self._drag_start_y)
            window.geometry(f"+{x}+{y}")
        except:
            pass
    
    def _on_motion(self, event):
        """Handle mouse motion for button hover effects."""
        width = self.winfo_width() or 640
        
        # Check if over close button
        close_x = width - 20
        if abs(event.x - close_x) < 15 and abs(event.y - 20) < 15:
            if not self._close_hover:
                self._close_hover = True
                self._draw()
        elif self._close_hover:
            self._close_hover = False
            self._draw()
        
        # Check if over minimize button
        minimize_x = width - 50
        if abs(event.x - minimize_x) < 15 and abs(event.y - 20) < 15:
            if not self._minimize_hover:
                self._minimize_hover = True
                self._draw()
        elif self._minimize_hover:
            self._minimize_hover = False
            self._draw()
    
    def _on_leave(self, event):
        """Reset hover states when mouse leaves."""
        if self._close_hover or self._minimize_hover:
            self._close_hover = False
            self._minimize_hover = False
            self._draw()
    
    def _on_click(self, event):
        """Handle button clicks."""
        width = self.winfo_width() or 640
        
        # Close button
        close_x = width - 20
        if abs(event.x - close_x) < 15 and abs(event.y - 20) < 15:
            if self.on_close:
                self.on_close()
            return
        
        # Minimize button
        minimize_x = width - 50
        if abs(event.x - minimize_x) < 15 and abs(event.y - 20) < 15:
            if self.on_minimize:
                self.on_minimize()
            return


class SettingsWindow:
    """Modern glassmorphism-styled settings window.
    
    Features:
    - Dark mode with semi-transparent background
    - Custom modern title bar with draggable interface
    - Custom-styled widgets with hover effects
    - Smooth tab transitions
    - Gradient accents matching the overlay
    - Success animations on save
    """
    
    def __init__(self, cfgm: ConfigManager, root: Optional[tk.Tk] = None) -> None:
        self.cfgm = cfgm
        self.root: Optional[tk.Tk] = root
        self.win: Optional[tk.Toplevel] = None
        
        # Animation state
        self._fade_alpha = 0.0
        self._current_tab_index = 0
        self._title_bar: Optional[ModernTitleBar] = None
        
    def _setup_modern_style(self) -> None:
        """Setup modern ttk style theme."""
        style = ttk.Style()
        
        # Configure Notebook (tabs)
        style.theme_use('clam')
        
        style.configure(
            'Modern.TNotebook',
            background=ColorTheme.BG_DARK,
            borderwidth=0,
            tabmargins=[10, 10, 0, 0]
        )
        
        style.configure(
            'Modern.TNotebook.Tab',
            background=ColorTheme.BG_CARD,
            foreground=ColorTheme.TEXT_SECONDARY,
            padding=[20, 10],
            borderwidth=0,
            font=('Segoe UI', 10)
        )
        
        style.map(
            'Modern.TNotebook.Tab',
            background=[('selected', ColorTheme.ACCENT_PRIMARY)],
            foreground=[('selected', ColorTheme.TEXT_PRIMARY)],
            expand=[('selected', [1, 1, 1, 0])]
        )
        
        # Configure Frame
        style.configure(
            'Modern.TFrame',
            background=ColorTheme.BG_DARK
        )
        
        # Configure Label
        style.configure(
            'Modern.TLabel',
            background=ColorTheme.BG_DARK,
            foreground=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 10)
        )
        
        style.configure(
            'Title.TLabel',
            background=ColorTheme.BG_DARK,
            foreground=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 12, 'bold')
        )
        
        # Configure Combobox
        style.configure(
            'Modern.TCombobox',
            fieldbackground=ColorTheme.BG_CARD,
            background=ColorTheme.BG_CARD,
            foreground=ColorTheme.TEXT_PRIMARY,
            arrowcolor=ColorTheme.TEXT_PRIMARY,
            borderwidth=1,
            relief=tk.FLAT
        )
        
        # Configure Checkbutton
        style.configure(
            'Modern.TCheckbutton',
            background=ColorTheme.BG_DARK,
            foreground=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 10)
        )
        style.map(
            'Modern.TCheckbutton',
            background=[('active', ColorTheme.BG_DARK)],
            foreground=[('active', ColorTheme.ACCENT_PRIMARY)]
        )

    def _create_section_header(self, parent, text: str) -> ttk.Label:
        """Create a section header label."""
        return ttk.Label(
            parent,
            text=text,
            style='Title.TLabel'
        )

    def _create_labeled_field(
        self,
        parent,
        label_text: str,
        widget_class,
        row: int,
        **widget_kwargs
    ) -> Any:
        """Create a labeled field (label + widget) in a grid.
        
        Args:
            parent: Parent widget
            label_text: Text for the label
            widget_class: Widget class to instantiate
            row: Grid row
            **widget_kwargs: Additional arguments for widget
        
        Returns:
            The created widget
        """
        # Label
        label = ttk.Label(
            parent,
            text=label_text,
            style='Modern.TLabel'
        )
        label.grid(row=row, column=0, sticky='w', padx=16, pady=8)
        
        # Widget
        widget = widget_class(parent, **widget_kwargs)
        widget.grid(row=row, column=1, sticky='w', padx=16, pady=8)
        
        return widget

    def _build(self) -> None:
        """Build the modern settings UI."""
        assert self.win is not None
        print("[SettingsWindow] Building modern settings UI")
        
        # Remove default window decorations
        self.win.overrideredirect(True)
        self.win.geometry("640x560+200+200")
        
        # Set window background
        self.win.configure(bg=ColorTheme.BG_DARK)
        
        # Try to set transparency (may not work on all systems)
        try:
            self.win.attributes('-alpha', 0.97)
        except:
            pass
        
        # Setup modern styles
        self._setup_modern_style()
        
        # Custom title bar
        self._title_bar = ModernTitleBar(
            self.win,
            title="⚙ Voice Typing Settings",
            on_close=self.win.destroy,
            on_minimize=self._minimize_window
        )
        
        # Bind click event to title bar
        self._title_bar.bind('<Button-1>', self._title_bar._on_click)
        
        # Main container
        main_container = ttk.Frame(self.win, style='Modern.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_container, style='Modern.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create tabs
        self._create_general_tab()
        self._create_audio_tab()
        self._create_streaming_tab()
        self._create_decoding_tab()
        
        # Button container
        button_frame = ttk.Frame(main_container, style='Modern.TFrame')
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Add buttons (right-aligned)
        close_btn = ModernButton(
            button_frame,
            text="Close",
            command=self.win.destroy,
            width=100,
            height=36
        )
        close_btn.pack(side=tk.RIGHT, padx=5)
        
        save_btn = ModernButton(
            button_frame,
            text="Save",
            command=self._save,
            width=100,
            height=36,
            primary=True
        )
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        # Fade-in animation
        self._animate_fade_in()

    def _create_general_tab(self) -> None:
        """Create the General settings tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="  General  ")
        
        # Configure grid
        frame.columnconfigure(1, weight=1)
        
        # Hotkey
        self.var_hotkey = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.ui.hotkey
        )
        self._hotkey_entry = self._create_labeled_field(
            frame,
            "Hotkey",
            lambda p, **kw: ModernEntry(p, **kw),
            row=0,
            textvariable=self.var_hotkey,
            width=30
        )
        
        # Model
        self.var_model = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.stt.model
        )
        model_combo = self._create_labeled_field(
            frame,
            "Model",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=1,
            textvariable=self.var_model,
            values=["tiny", "base", "small", "medium", "large-v2"],
            width=28
        )
        
        # Device
        self.var_device = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.stt.device
        )
        device_combo = self._create_labeled_field(
            frame,
            "Device",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=2,
            textvariable=self.var_device,
            values=["auto", "cpu", "cuda"],
            width=28
        )
        
        # Compute Type
        self.var_compute = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.stt.compute_type
        )
        compute_combo = self._create_labeled_field(
            frame,
            "Compute Type",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=3,
            textvariable=self.var_compute,
            values=["float16", "float32", "int8"],
            width=28
        )
        
        # Filler Word Removal
        self.var_remove_fillers = tk.BooleanVar(
            master=self.win,
            value=getattr(self.cfgm.config.stt, 'remove_filler_words', False)
        )
        filler_check = ttk.Checkbutton(
            frame,
            text="Remove filler words (um, uh, etc.)",
            variable=self.var_remove_fillers,
            style='Modern.TCheckbutton'
        )
        filler_check.grid(row=4, column=0, columnspan=2, sticky='w', padx=16, pady=8)
        
        # Grammar Improvement
        self.var_improve_grammar = tk.BooleanVar(
            master=self.win,
            value=getattr(self.cfgm.config.stt, 'improve_grammar', False)
        )
        grammar_check = ttk.Checkbutton(
            frame,
            text="Improve grammar (context-aware corrections)",
            variable=self.var_improve_grammar,
            style='Modern.TCheckbutton'
        )
        grammar_check.grid(row=5, column=0, columnspan=2, sticky='w', padx=16, pady=8)

    def _create_audio_tab(self) -> None:
        """Create the Audio settings tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="  Audio  ")
        
        frame.columnconfigure(1, weight=1)
        
        # Get audio devices
        devices = AudioCapture().list_devices()
        device_names = [f"{d['id']}: {d['name']}" for d in devices]
        
        # Input Device
        device_id_val = "default" if self.cfgm.config.audio.device_id is None else str(self.cfgm.config.audio.device_id)
        self.var_device_id = tk.StringVar(master=self.win, value=device_id_val)
        
        device_combo = self._create_labeled_field(
            frame,
            "Input Device",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=0,
            textvariable=self.var_device_id,
            values=["default"] + device_names,
            width=40
        )
        
        # Sample Rate
        self.var_sr = tk.IntVar(
            master=self.win,
            value=self.cfgm.config.audio.sample_rate
        )
        sr_entry = self._create_labeled_field(
            frame,
            "Sample Rate",
            lambda p, **kw: ModernEntry(p, **kw),
            row=1,
            textvariable=self.var_sr,
            width=15
        )

    def _create_streaming_tab(self) -> None:
        """Create the Streaming settings tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="  Streaming  ")
        
        frame.columnconfigure(1, weight=1)
        
        # Mode
        self.var_stream_mode = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.streaming.mode
        )
        mode_combo = self._create_labeled_field(
            frame,
            "Mode",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=0,
            textvariable=self.var_stream_mode,
            values=["final_only"],
            width=20
        )
        
        # Segmentation
        self.var_seg = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.streaming.segmentation
        )
        seg_combo = self._create_labeled_field(
            frame,
            "Segmentation",
            lambda p, **kw: self._create_modern_combobox(p, **kw),
            row=1,
            textvariable=self.var_seg,
            values=["energy", "vad"],
            width=20
        )
        
        # Min Segment
        self.var_min_seg = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.streaming.min_segment_sec
        )
        min_seg_entry = self._create_labeled_field(
            frame,
            "Min Segment (s)",
            lambda p, **kw: ModernEntry(p, **kw),
            row=2,
            textvariable=self.var_min_seg,
            width=12
        )
        
        # Min Silence
        self.var_min_sil = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.streaming.min_silence_sec
        )
        min_sil_entry = self._create_labeled_field(
            frame,
            "Min Silence (s)",
            lambda p, **kw: ModernEntry(p, **kw),
            row=3,
            textvariable=self.var_min_sil,
            width=12
        )
        
        # Energy Threshold
        self.var_energy = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.streaming.energy_threshold
        )
        energy_entry = self._create_labeled_field(
            frame,
            "Energy Threshold",
            lambda p, **kw: ModernEntry(p, **kw),
            row=4,
            textvariable=self.var_energy,
            width=12
        )

    def _create_decoding_tab(self) -> None:
        """Create the Decoding settings tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="  Decoding  ")
        
        frame.columnconfigure(1, weight=1)
        
        # Beam Size
        self.var_beam = tk.IntVar(
            master=self.win,
            value=self.cfgm.config.decoding.beam_size
        )
        beam_entry = self._create_labeled_field(
            frame,
            "Beam Size",
            lambda p, **kw: ModernEntry(p, **kw),
            row=0,
            textvariable=self.var_beam,
            width=12
        )
        
        # Temperature
        self.var_temp = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.decoding.temperature
        )
        temp_entry = self._create_labeled_field(
            frame,
            "Temperature",
            lambda p, **kw: ModernEntry(p, **kw),
            row=1,
            textvariable=self.var_temp,
            width=12
        )

    def _create_modern_combobox(self, parent, textvariable=None, values=None, width=30):
        """Create a modern styled combobox."""
        combo = ttk.Combobox(
            parent,
            textvariable=textvariable,
            values=values or [],
            width=width,
            style='Modern.TCombobox',
            font=('Segoe UI', 10)
        )
        return combo

    def _minimize_window(self) -> None:
        """Minimize the settings window."""
        if self.win:
            self.win.withdraw()
    
    def _animate_fade_in(self) -> None:
        """Animate window fade-in effect."""
        if not self.win:
            return
        
        steps = 15
        target_alpha = 0.97
        
        def fade_step(current_step):
            if not self.win or current_step > steps:
                return
            
            alpha = (current_step / steps) * target_alpha
            try:
                self.win.attributes('-alpha', alpha)
            except:
                pass
            
            if current_step < steps:
                self.win.after(20, lambda: fade_step(current_step + 1))
        
        try:
            self.win.attributes('-alpha', 0.0)
            fade_step(0)
        except:
            # Fade animation not supported
            pass

    def _save(self) -> None:
        """Save settings with success animation."""
        try:
            hk = self.var_hotkey.get().strip()
            model = self.var_model.get().strip()
            device = self.var_device.get().strip()
            compute = self.var_compute.get().strip()
            sr = int(self.var_sr.get())
            device_id = self.var_device_id.get()
            
            if device_id == "default" or device_id == "":
                did = None
            else:
                did = int(device_id.split(":", 1)[0]) if ":" in device_id else int(device_id)

            self.cfgm.update(
                ui__hotkey=hk,
                stt__model=model,
                stt__device=device,
                stt__compute_type=compute,
                stt__remove_filler_words=self.var_remove_fillers.get(),
                stt__improve_grammar=self.var_improve_grammar.get(),
                audio__sample_rate=sr,
                audio__device_id=did,
                streaming__mode=self.var_stream_mode.get().strip(),
                streaming__segmentation=self.var_seg.get().strip(),
                streaming__min_segment_sec=float(self.var_min_seg.get()),
                streaming__min_silence_sec=float(self.var_min_sil.get()),
                streaming__energy_threshold=float(self.var_energy.get()),
                decoding__beam_size=int(self.var_beam.get()),
                decoding__temperature=float(self.var_temp.get()),
            )
            
            # Show success message with modern styling
            self._show_success_message()
            
        except Exception as e:
            messagebox.showerror("Settings Error", f"Failed to save: {e}")

    def _show_success_message(self) -> None:
        """Show a modern success message."""
        # Create a custom success dialog
        success_win = tk.Toplevel(self.win)
        success_win.title("Success")
        success_win.geometry("320x120")
        success_win.configure(bg=ColorTheme.BG_DARK)
        success_win.transient(self.win)
        success_win.grab_set()
        
        # Center on parent
        if self.win:
            x = self.win.winfo_x() + (self.win.winfo_width() - 320) // 2
            y = self.win.winfo_y() + (self.win.winfo_height() - 120) // 2
            success_win.geometry(f"+{x}+{y}")
        
        # Remove window decorations
        success_win.overrideredirect(True)
        
        # Success icon and message
        frame = ttk.Frame(success_win, style='Modern.TFrame')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        icon_label = ttk.Label(
            frame,
            text="✓",
            style='Title.TLabel',
            font=('Segoe UI', 32),
            foreground=ColorTheme.ACCENT_SUCCESS
        )
        icon_label.pack(pady=(10, 5))
        
        msg_label = ttk.Label(
            frame,
            text="Settings saved successfully!",
            style='Modern.TLabel'
        )
        msg_label.pack()
        
        hint_label = ttk.Label(
            frame,
            text="Some changes may require restart",
            style='Modern.TLabel',
            font=('Segoe UI', 8),
            foreground=ColorTheme.TEXT_SECONDARY
        )
        hint_label.pack(pady=(5, 0))
        
        # Auto-close after 2 seconds
        success_win.after(2000, success_win.destroy)

    def _show_impl(self) -> None:
        """Show the settings window implementation."""
        print("[SettingsWindow] Show requested")
        if self.root is None:
            print("[SettingsWindow] Creating root")
            self.root = tk.Tk()
            self.root.withdraw()
        
        if self.win is not None and tk.Toplevel.winfo_exists(self.win):
            print("[SettingsWindow] Deiconify existing window")
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            self.win.update_idletasks()
            return
        
        print("[SettingsWindow] Creating Toplevel")
        self.win = tk.Toplevel(self.root)
        self._build()
        
        try:
            self.win.attributes('-topmost', True)
        except Exception:
            pass
        
        self.win.update_idletasks()
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        print("[SettingsWindow] Shown")

    def show(self) -> None:
        """Show the settings window."""
        # Always marshal to Tk main thread
        if self.root is not None:
            try:
                self.root.after(0, self._show_impl)
                return
            except Exception:
                pass
        # Fallback (should not happen if root exists)
        self._show_impl()
