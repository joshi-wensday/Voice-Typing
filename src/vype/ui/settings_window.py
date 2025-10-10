"""Modern glassmorphism-styled settings window with smooth animations."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, Any
from PIL import Image, ImageDraw, ImageTk

from ..config.manager import ConfigManager
from ..audio.capture import AudioCapture
from ..stt.model_manager import ModelManager
from ..stt.model_tester import ModelTester
from .effects import ColorTheme, ease_out_sine, interpolate_color
from .hotkey_capture import HotkeyCapture


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


class ColorPicker(tk.Frame):
    """Simple color picker with preview and hex input."""
    
    def __init__(self, parent, textvariable=None, width=20):
        super().__init__(parent, bg=ColorTheme.BG_DARK)
        
        self.textvariable = textvariable or tk.StringVar()
        self.width = width
        
        # Color preview box
        self.preview_canvas = tk.Canvas(
            self,
            width=32,
            height=32,
            bg=ColorTheme.BG_CARD,
            highlightthickness=1,
            highlightbackground=ColorTheme.BORDER,
            cursor='hand2'
        )
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.preview_canvas.bind('<Button-1>', self._open_color_picker)
        
        # Hex input
        self.entry = ModernEntry(
            self,
            textvariable=self.textvariable,
            width=width
        )
        self.entry.pack(side=tk.LEFT)
        
        # Update preview when color changes
        self.textvariable.trace_add('write', lambda *args: self._update_preview())
        self._update_preview()
    
    def _update_preview(self):
        """Update the color preview."""
        color = self.textvariable.get()
        try:
            # Validate hex color
            if color.startswith('#') and len(color) == 7:
                self.preview_canvas.configure(bg=color)
            else:
                self.preview_canvas.configure(bg=ColorTheme.BG_CARD)
        except:
            self.preview_canvas.configure(bg=ColorTheme.BG_CARD)
    
    def _open_color_picker(self, event=None):
        """Open system color chooser dialog."""
        from tkinter import colorchooser
        
        current_color = self.textvariable.get()
        
        # Find the parent window (settings window) to set transient relationship
        parent_window = self.winfo_toplevel()
        
        # Temporarily disable topmost on settings window so color picker can appear above it
        was_topmost = False
        try:
            was_topmost = parent_window.attributes('-topmost')
            if was_topmost:
                parent_window.attributes('-topmost', False)
        except:
            pass
        
        # Open color chooser with current color
        color = colorchooser.askcolor(
            color=current_color, 
            title="Choose Color",
            parent=parent_window
        )
        
        # Restore topmost state
        try:
            if was_topmost:
                parent_window.attributes('-topmost', True)
        except:
            pass
        
        if color and color[1]:  # color[1] is the hex value
            self.textvariable.set(color[1])
    
    def get(self):
        """Get color value."""
        return self.textvariable.get()


class ModernSlider(tk.Frame):
    """Custom modern slider with value display."""
    
    def __init__(self, parent, variable=None, from_=0.0, to=1.0, resolution=0.01, width=200):
        super().__init__(parent, bg=ColorTheme.BG_DARK)
        
        self.variable = variable or tk.DoubleVar()
        self.from_ = from_
        self.to = to
        self.resolution = resolution
        
        # Slider
        self.scale = tk.Scale(
            self,
            from_=from_,
            to=to,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            variable=self.variable,
            bg=ColorTheme.BG_CARD,
            fg=ColorTheme.TEXT_PRIMARY,
            troughcolor=ColorTheme.BORDER,
            highlightthickness=0,
            length=width,
            width=20,
            sliderrelief=tk.FLAT,
            activebackground=ColorTheme.ACCENT_PRIMARY
        )
        self.scale.pack(side=tk.LEFT, padx=(0, 10))
        
        # Value label
        self.value_label = tk.Label(
            self,
            textvariable=self.variable,
            bg=ColorTheme.BG_DARK,
            fg=ColorTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9),
            width=6
        )
        self.value_label.pack(side=tk.LEFT)
    
    def get(self):
        """Get slider value."""
        return self.variable.get()


class ModernDropdown(tk.Frame):
    """Custom modern dropdown with styled list."""
    
    def __init__(self, parent, textvariable=None, values=None, width=30):
        super().__init__(parent, bg=ColorTheme.BG_DARK)
        
        self.textvariable = textvariable or tk.StringVar()
        self.values = values or []
        self.width = width
        self._is_open = False
        self._dropdown_window = None
        
        # Main button/display with explicit width
        canvas_width = self.width * 8  # Calculate pixel width from character width
        self.button_canvas = tk.Canvas(
            self,
            height=32,
            width=canvas_width,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
        )
        self.button_canvas.pack(fill=tk.X, expand=True)
        
        # Draw the dropdown button
        self._draw_button()
        
        # Bind click to toggle dropdown
        self.button_canvas.bind('<Button-1>', self._toggle_dropdown)
        
        # Update display when variable changes
        self.textvariable.trace_add('write', lambda *args: self._draw_button())
    
    def _draw_button(self, hovering=False):
        """Draw the dropdown button."""
        self.button_canvas.delete('all')
        
        # Use explicit width calculation
        w = self.width * 8
        h = 32
        
        # Background color
        bg_color = ColorTheme.BORDER_LIGHT if hovering else ColorTheme.BG_CARD
        border_color = ColorTheme.ACCENT_PRIMARY if hovering else ColorTheme.BORDER
        
        # Draw rounded rectangle background
        self._create_rounded_rect(
            self.button_canvas, 0, 0, w, h,
            radius=6,
            fill=bg_color,
            outline=border_color,
            width=1,
            tags='background'
        )
        
        # Draw text
        text = self.textvariable.get() or ''
        self.button_canvas.create_text(
            10, h // 2,
            text=text,
            fill=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 10),
            anchor=tk.W,
            tags='text'
        )
        
        # Draw arrow
        arrow_x = w - 20
        arrow_y = h // 2
        arrow_points = [
            arrow_x - 4, arrow_y - 2,
            arrow_x, arrow_y + 2,
            arrow_x + 4, arrow_y - 2
        ]
        self.button_canvas.create_polygon(
            arrow_points,
            fill=ColorTheme.TEXT_SECONDARY,
            outline='',
            tags='arrow'
        )
    
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
    
    def _toggle_dropdown(self, event=None):
        """Toggle the dropdown list."""
        print(f"[DROPDOWN] Toggle called - currently open: {self._is_open}")
        if self._is_open:
            self._close_dropdown()
        else:
            self._open_dropdown()
    
    def _open_dropdown(self):
        """Open the dropdown list."""
        print(f"[DROPDOWN] _open_dropdown called - is_open={self._is_open}, values={len(self.values)}")
        if self._is_open or not self.values:
            print(f"[DROPDOWN] Aborting open - is_open={self._is_open}, has_values={len(self.values) > 0}")
            return
        
        self._is_open = True
        
        # Ensure widget is updated before getting position
        self.button_canvas.update_idletasks()
        
        # Create toplevel window for dropdown
        self._dropdown_window = tk.Toplevel(self)
        self._dropdown_window.overrideredirect(True)
        self._dropdown_window.attributes('-topmost', True)
        self._dropdown_window.configure(bg=ColorTheme.BG_CARD)
        
        # Position below the button - use explicit width
        x = self.button_canvas.winfo_rootx()
        y = self.button_canvas.winfo_rooty() + self.button_canvas.winfo_height()
        w = self.width * 8  # Use explicit width calculation
        
        print(f"[DROPDOWN] Positioning at x={x}, y={y}, width={w}")
        
        # Create scrollable frame for dropdown
        container_frame = tk.Frame(
            self._dropdown_window,
            bg=ColorTheme.BG_CARD
        )
        container_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a simple container for items (no canvas, direct packing)
        # Calculate height based on number of items (max 6 visible at once)
        max_visible_items = 6
        item_height = 32
        num_items = len(self.values)
        dropdown_height = min(num_items * item_height, max_visible_items * item_height)
        
        # Add items directly to container
        for i, value in enumerate(self.values):
            if i >= max_visible_items:
                break  # Limit visible items for now (TODO: add scrollbar if needed)
            
            item_frame = tk.Frame(container_frame, bg=ColorTheme.BG_CARD, height=item_height)
            item_frame.pack(fill=tk.X)
            item_frame.pack_propagate(False)
            
            label = tk.Label(
                item_frame,
                text=str(value),
                bg=ColorTheme.BG_CARD,
                fg=ColorTheme.TEXT_PRIMARY,
                font=('Segoe UI', 10),
                anchor=tk.W,
                padx=10
            )
            label.pack(fill=tk.BOTH, expand=True)
            
            # Bind hover and click
            item_frame.bind('<Enter>', lambda e, f=item_frame, l=label: self._on_item_hover(f, l, True))
            item_frame.bind('<Leave>', lambda e, f=item_frame, l=label: self._on_item_hover(f, l, False))
            label.bind('<Enter>', lambda e, f=item_frame, l=label: self._on_item_hover(f, l, True))
            label.bind('<Leave>', lambda e, f=item_frame, l=label: self._on_item_hover(f, l, False))
            
            item_frame.bind('<Button-1>', lambda e, v=value: self._on_select(v))
            label.bind('<Button-1>', lambda e, v=value: self._on_select(v))
        
        # Update to ensure proper sizing
        container_frame.update_idletasks()
        
        geometry_str = f"{w}x{dropdown_height}+{x}+{y}"
        print(f"[DROPDOWN] Setting geometry: {geometry_str}")
        self._dropdown_window.geometry(geometry_str)
        
        # Make sure dropdown is visible
        self._dropdown_window.deiconify()
        self._dropdown_window.lift()
        
        # Bind click outside to close
        self._dropdown_window.bind('<FocusOut>', lambda e: self._close_dropdown())
        self._dropdown_window.focus_set()
        print("[DROPDOWN] Dropdown window created and shown")
    
    def _on_item_hover(self, frame, label, entering):
        """Handle item hover."""
        if entering:
            frame.configure(bg=ColorTheme.BORDER_LIGHT)
            label.configure(bg=ColorTheme.BORDER_LIGHT)
        else:
            frame.configure(bg=ColorTheme.BG_CARD)
            label.configure(bg=ColorTheme.BG_CARD)
    
    def _on_select(self, value):
        """Handle item selection."""
        self.textvariable.set(str(value))
        self._close_dropdown()
    
    def _close_dropdown(self):
        """Close the dropdown list."""
        if not self._is_open:
            return
        
        self._is_open = False
        if self._dropdown_window:
            self._dropdown_window.destroy()
            self._dropdown_window = None
    
    def get(self):
        """Get selected value."""
        return self.textvariable.get()
    
    def set(self, value):
        """Set selected value."""
        self.textvariable.set(str(value))


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
        self._window_start_x = 0
        self._window_start_y = 0
        self._is_dragging = False
        
        # Button states
        self._close_hover = False
        self._minimize_hover = False
        
        # Bind events for dragging and clicking
        self.bind('<ButtonPress-1>', self._on_button_press)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_button_release)
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
    
    def _on_button_press(self, event):
        """Handle button press - start drag or prepare for button click."""
        print(f"[DRAG] _on_button_press called - event.x={event.x}, event.y={event.y}")
        
        # Check if clicking on buttons
        width = self.winfo_width() or 640
        close_x = width - 20
        minimize_x = width - 50
        
        print(f"[DRAG] Width={width}, close_x={close_x}, minimize_x={minimize_x}")
        
        # If clicking on close or minimize buttons, don't start drag (handle in release)
        if (abs(event.x - close_x) < 15 and abs(event.y - 20) < 15) or \
           (abs(event.x - minimize_x) < 15 and abs(event.y - 20) < 15):
            print("[DRAG] Click on button detected - not starting drag")
            self._is_dragging = False
            return
        
        # Start dragging - store absolute screen coordinates and initial window position
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        try:
            self._window_start_x = self.parent_window.winfo_x()
            self._window_start_y = self.parent_window.winfo_y()
            self._is_dragging = True
            print(f"[DRAG] Drag started - root=({event.x_root},{event.y_root}), window=({self._window_start_x},{self._window_start_y})")
        except Exception as e:
            print(f"[DRAG] Error getting window position: {e}")
            self._window_start_x = 0
            self._window_start_y = 0
            self._is_dragging = False
    
    def _on_drag(self, event):
        """Drag the window."""
        # Only drag if we're in dragging mode
        if not self._is_dragging:
            return
            
        try:
            # Calculate movement using absolute screen coordinates
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            
            # Apply to initial window position
            x = self._window_start_x + dx
            y = self._window_start_y + dy
            print(f"[DRAG] Moving window to ({x},{y}) - delta=({dx},{dy})")
            self.parent_window.geometry(f"+{x}+{y}")
        except Exception as e:
            print(f"[DRAG] Error during drag: {e}")
    
    def _on_button_release(self, event):
        """Handle button release - end drag or execute button click."""
        print(f"[DRAG] _on_button_release called - is_dragging was {self._is_dragging}")
        
        # If we were dragging, just end the drag
        if self._is_dragging:
            self._is_dragging = False
            print("[DRAG] Drag ended")
            return
        
        # Not dragging - check if clicking on buttons
        width = self.winfo_width() or 640
        close_x = width - 20
        minimize_x = width - 50
        
        # Close button
        if abs(event.x - close_x) < 15 and abs(event.y - 20) < 15:
            print("[DRAG] Close button clicked")
            if self.on_close:
                self.on_close()
            return
        
        # Minimize button
        if abs(event.x - minimize_x) < 15 and abs(event.y - 20) < 15:
            print("[DRAG] Minimize button clicked")
            if self.on_minimize:
                self.on_minimize()
            return
    
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
        
        # Model management
        self.model_manager = ModelManager()
        self.model_tester = ModelTester()
        
        # Config snapshot for cancel functionality
        self._original_config = None
        
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
            padding=[16, 12],  # Reasonable padding - width controlled by spaces in text
            borderwidth=0,
            font=('Segoe UI', 10)
        )
        
        style.map(
            'Modern.TNotebook.Tab',
            background=[('selected', ColorTheme.ACCENT_PRIMARY)],
            foreground=[('selected', ColorTheme.TEXT_PRIMARY)],
            padding=[('selected', [16, 12])]  # Same padding for selected state
            # Removed expand parameter that was causing size changes
        )
        
        # Configure Frame
        style.configure(
            'Modern.TFrame',
            background=ColorTheme.BG_DARK
        )
        
        # Configure custom scrollbar
        style.configure(
            'Modern.Vertical.TScrollbar',
            background=ColorTheme.BG_CARD,
            troughcolor=ColorTheme.BG_DARKER,
            borderwidth=0,
            arrowsize=12,
            width=12
        )
        
        style.map(
            'Modern.Vertical.TScrollbar',
            background=[('active', ColorTheme.ACCENT_PRIMARY), ('!active', ColorTheme.BG_CARD)]
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
        self.win.geometry("640x600+200+200")  # Increased height to ensure buttons aren't cut off
        
        # Set window background
        self.win.configure(bg=ColorTheme.BG_DARK)
        
        # Try to set transparency (may not work on all systems)
        try:
            opacity = self.cfgm.config.ui.settings_window_opacity
            self.win.attributes('-alpha', opacity)
        except:
            pass
        
        # Setup modern styles
        self._setup_modern_style()
        
        # Custom title bar
        self._title_bar = ModernTitleBar(
            self.win,
            title="⚙ Vype Settings",
            on_close=self._cancel,
            on_minimize=self._minimize_window
        )
        
        # Note: Click events already bound in ModernTitleBar.__init__()
        # The title bar handles both dragging and button clicks internally
        
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
        self._create_appearance_tab()
        self._create_models_tab()
        
        # Button container with extra bottom padding to prevent cutoff
        button_frame = ttk.Frame(main_container, style='Modern.TFrame')
        button_frame.pack(fill=tk.X, padx=20, pady=(10, 25))  # Extra bottom padding
        
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
        self.notebook.add(frame, text="General          ")
        
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
            lambda p, **kw: HotkeyCapture(p, **kw),
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
        self.notebook.add(frame, text="Audio          ")
        
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
        self.notebook.add(frame, text="Streaming          ")
        
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
        self.notebook.add(frame, text="Decoding          ")
        
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

    def _create_appearance_tab(self) -> None:
        """Create the Appearance settings tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="Appearance          ")
        
        frame.columnconfigure(1, weight=1)
        
        # Color pickers for different states
        self.var_color_idle = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.ui.accent_color_idle
        )
        idle_color = self._create_labeled_field(
            frame,
            "Idle Color",
            lambda p, **kw: ColorPicker(p, **kw),
            row=0,
            textvariable=self.var_color_idle,
            width=15
        )
        
        self.var_color_recording = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.ui.accent_color_recording
        )
        recording_color = self._create_labeled_field(
            frame,
            "Recording Color",
            lambda p, **kw: ColorPicker(p, **kw),
            row=1,
            textvariable=self.var_color_recording,
            width=15
        )
        
        self.var_color_processing = tk.StringVar(
            master=self.win,
            value=self.cfgm.config.ui.accent_color_processing
        )
        processing_color = self._create_labeled_field(
            frame,
            "Processing Color",
            lambda p, **kw: ColorPicker(p, **kw),
            row=2,
            textvariable=self.var_color_processing,
            width=15
        )
        
        # Transparency sliders
        self.var_settings_opacity = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.ui.settings_window_opacity
        )
        settings_opacity = self._create_labeled_field(
            frame,
            "Settings Opacity",
            lambda p, **kw: ModernSlider(p, **kw),
            row=3,
            variable=self.var_settings_opacity,
            from_=0.7,
            to=1.0,
            resolution=0.05,
            width=180
        )
        
        self.var_overlay_opacity = tk.DoubleVar(
            master=self.win,
            value=self.cfgm.config.ui.overlay_opacity
        )
        overlay_opacity = self._create_labeled_field(
            frame,
            "Overlay Opacity",
            lambda p, **kw: ModernSlider(p, **kw),
            row=4,
            variable=self.var_overlay_opacity,
            from_=0.5,
            to=1.0,
            resolution=0.05,
            width=180
        )
        
        # Visualizer size slider
        self.var_visualizer_size = tk.IntVar(
            master=self.win,
            value=self.cfgm.config.ui.visualizer_size
        )
        visualizer_size = self._create_labeled_field(
            frame,
            "Visualizer Size",
            lambda p, **kw: ModernSlider(p, **kw),
            row=5,
            variable=self.var_visualizer_size,
            from_=50,
            to=120,
            resolution=10,
            width=180
        )
        
        # Info label
        info_label = ttk.Label(
            frame,
            text="Note: Some changes may require restarting the app",
            style='Modern.TLabel',
            font=('Segoe UI', 8),
            foreground=ColorTheme.TEXT_SECONDARY
        )
        info_label.grid(row=6, column=0, columnspan=2, sticky='w', padx=16, pady=(20, 8))

    def _create_models_tab(self) -> None:
        """Create the Models management tab."""
        frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(frame, text="Models          ")
        
        # Create scrollable content
        canvas = tk.Canvas(frame, bg=ColorTheme.BG_DARK, highlightthickness=0)
        
        # Custom styled scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview, style='Modern.Vertical.TScrollbar')
        scrollable_frame = ttk.Frame(canvas, style='Modern.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Section 1: Installed Models
        ttk.Label(
            scrollable_frame,
            text="Installed Models",
            style='Title.TLabel'
        ).pack(anchor='w', padx=16, pady=(10, 5))
        
        self.installed_models_frame = ttk.Frame(scrollable_frame, style='Modern.TFrame')
        self.installed_models_frame.pack(fill=tk.X, padx=16, pady=5)
        
        # Refresh button for installed models
        refresh_btn = ModernButton(
            self.installed_models_frame,
            text="Refresh",
            command=self._refresh_installed_models,
            width=100,
            height=30
        )
        refresh_btn.pack(anchor='w', pady=5)
        
        self.installed_models_list = ttk.Frame(self.installed_models_frame, style='Modern.TFrame')
        self.installed_models_list.pack(fill=tk.X, pady=5)
        
        # Section 2: Download Models
        ttk.Label(
            scrollable_frame,
            text="Download Models",
            style='Title.TLabel'
        ).pack(anchor='w', padx=16, pady=(20, 5))
        
        download_frame = ttk.Frame(scrollable_frame, style='Modern.TFrame')
        download_frame.pack(fill=tk.X, padx=16, pady=5)
        
        # Model selection dropdown
        ttk.Label(
            download_frame,
            text="Select Model:",
            style='Modern.TLabel'
        ).grid(row=0, column=0, sticky='w', padx=(0, 10), pady=5)
        
        self.var_download_model = tk.StringVar(value="base")
        available_models = list(self.model_manager.AVAILABLE_MODELS.keys())
        
        download_combo = ModernDropdown(
            download_frame,
            textvariable=self.var_download_model,
            values=available_models,
            width=20
        )
        download_combo.grid(row=0, column=1, sticky='w', pady=5)
        
        download_btn = ModernButton(
            download_frame,
            text="Download Model",
            command=self._download_selected_model,
            width=140,
            height=36,
            primary=True
        )
        download_btn.grid(row=0, column=2, sticky='w', padx=10, pady=5)
        
        # Model info display
        self.model_info_label = ttk.Label(
            download_frame,
            text="",
            style='Modern.TLabel',
            font=('Segoe UI', 9),
            foreground=ColorTheme.TEXT_SECONDARY,
            wraplength=500
        )
        self.model_info_label.grid(row=1, column=0, columnspan=3, sticky='w', pady=5)
        
        # Update info when selection changes
        self.var_download_model.trace_add('write', lambda *args: self._update_model_info())
        self._update_model_info()
        
        # HuggingFace URL input
        ttk.Label(
            download_frame,
            text="Or paste HuggingFace URL:",
            style='Modern.TLabel'
        ).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(10, 5))
        
        self.var_hf_url = tk.StringVar()
        hf_entry = ModernEntry(
            download_frame,
            textvariable=self.var_hf_url,
            width=40
        )
        hf_entry.grid(row=2, column=1, columnspan=2, sticky='w', pady=(10, 5))
        
        # Section 3: Manual Installation
        ttk.Label(
            scrollable_frame,
            text="Manual Installation",
            style='Title.TLabel'
        ).pack(anchor='w', padx=16, pady=(20, 5))
        
        manual_frame = ttk.Frame(scrollable_frame, style='Modern.TFrame')
        manual_frame.pack(fill=tk.X, padx=16, pady=5)
        
        instructions = (
            "To manually install a model:\n"
            "1. Download the model files from HuggingFace\n"
            "2. Place them in the model directory\n"
            "3. Click 'Refresh' to detect new models"
        )
        
        ttk.Label(
            manual_frame,
            text=instructions,
            style='Modern.TLabel',
            font=('Segoe UI', 9),
            foreground=ColorTheme.TEXT_SECONDARY
        ).pack(anchor='w', pady=5)
        
        open_folder_btn = ModernButton(
            manual_frame,
            text="Open Model Folder",
            command=self._open_model_folder,
            width=150,
            height=36
        )
        open_folder_btn.pack(anchor='w', pady=10)
        
        # Section 4: Model Testing
        ttk.Label(
            scrollable_frame,
            text="Model Testing",
            style='Title.TLabel'
        ).pack(anchor='w', padx=16, pady=(20, 5))
        
        test_frame = ttk.Frame(scrollable_frame, style='Modern.TFrame')
        test_frame.pack(fill=tk.X, padx=16, pady=5)
        
        ttk.Label(
            test_frame,
            text="Test installed models to compare performance on your system",
            style='Modern.TLabel',
            font=('Segoe UI', 9),
            foreground=ColorTheme.TEXT_SECONDARY
        ).pack(anchor='w', pady=5)
        
        test_btn = ModernButton(
            test_frame,
            text="Test All Models",
            command=self._test_models,
            width=140,
            height=36,
            primary=True
        )
        test_btn.pack(anchor='w', pady=10)
        
        # Test results display
        self.test_results_text = tk.Text(
            test_frame,
            height=10,
            bg=ColorTheme.BG_CARD,
            fg=ColorTheme.TEXT_PRIMARY,
            font=('Consolas', 9),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.test_results_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Initial refresh
        self._refresh_installed_models()

    def _refresh_installed_models(self):
        """Refresh the list of installed models."""
        # Clear existing list
        for widget in self.installed_models_list.winfo_children():
            widget.destroy()
        
        # Get installed models
        installed = self.model_manager.list_installed_models()
        
        if not installed:
            ttk.Label(
                self.installed_models_list,
                text="No models installed yet",
                style='Modern.TLabel',
                foreground=ColorTheme.TEXT_SECONDARY
            ).pack(anchor='w', pady=5)
        else:
            for model in installed:
                model_frame = ttk.Frame(self.installed_models_list, style='Modern.TFrame')
                model_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(
                    model_frame,
                    text=f"✓ {model.name} ({model.parameters}, {model.size_mb}MB)",
                    style='Modern.TLabel'
                ).pack(side=tk.LEFT, padx=5)
    
    def _update_model_info(self):
        """Update the model information display."""
        model_name = self.var_download_model.get()
        info = self.model_manager.get_model_info(model_name)
        
        if info:
            text = (
                f"{info.description}\n"
                f"Size: {info.size_mb}MB | Parameters: {info.parameters} | "
                f"Speed: {info.relative_speed} | Accuracy: {info.accuracy}"
            )
            self.model_info_label.configure(text=text)
    
    def _download_selected_model(self):
        """Download the selected model."""
        model_name = self.var_download_model.get()
        
        def progress_callback(message):
            # Update UI with progress (could show in a dialog)
            print(f"[Model Download] {message}")
        
        # Download in background (should use threading in production)
        success = self.model_manager.download_model(model_name, progress_callback)
        
        if success:
            messagebox.showinfo("Success", f"Model {model_name} downloaded successfully!")
            self._refresh_installed_models()
        else:
            messagebox.showerror("Error", f"Failed to download model {model_name}")
    
    def _open_model_folder(self):
        """Open the model directory in file explorer."""
        success = self.model_manager.open_model_directory()
        if not success:
            messagebox.showwarning("Warning", "Could not open model directory")
    
    def _test_models(self):
        """Test all installed models."""
        installed = self.model_manager.list_installed_models()
        
        if not installed:
            messagebox.showinfo("No Models", "No models installed to test")
            return
        
        model_names = [m.name for m in installed]
        
        # Update text widget
        self.test_results_text.configure(state=tk.NORMAL)
        self.test_results_text.delete(1.0, tk.END)
        self.test_results_text.insert(tk.END, "Testing models, please wait...\n")
        self.test_results_text.configure(state=tk.DISABLED)
        self.test_results_text.update()
        
        def progress_callback(message):
            self.test_results_text.configure(state=tk.NORMAL)
            self.test_results_text.insert(tk.END, f"{message}\n")
            self.test_results_text.configure(state=tk.DISABLED)
            self.test_results_text.update()
        
        # Run tests
        results = self.model_tester.test_all_models(
            model_names,
            device=self.cfgm.config.stt.device,
            compute_type=self.cfgm.config.stt.compute_type,
            progress_callback=progress_callback
        )
        
        # Display results
        results_table = self.model_tester.format_results_table(results)
        
        self.test_results_text.configure(state=tk.NORMAL)
        self.test_results_text.delete(1.0, tk.END)
        self.test_results_text.insert(tk.END, results_table)
        self.test_results_text.configure(state=tk.DISABLED)

    def _create_modern_combobox(self, parent, textvariable=None, values=None, width=30):
        """Create a modern styled dropdown."""
        dropdown = ModernDropdown(
            parent,
            textvariable=textvariable,
            values=values or [],
            width=width
        )
        return dropdown

    def _minimize_window(self) -> None:
        """Minimize the settings window."""
        if self.win:
            self.win.withdraw()
    
    def _cancel(self) -> None:
        """Cancel any changes and restore original config."""
        if self._original_config is not None:
            # Restore the original config
            self.cfgm.config = self._original_config
            self.cfgm.save()
            print("[SettingsWindow] Changes cancelled, original config restored")
        
        # Close the window
        if self.win:
            self.win.destroy()
    
    def _animate_fade_in(self) -> None:
        """Animate window fade-in effect."""
        if not self.win:
            return
        
        steps = 15
        target_alpha = self.cfgm.config.ui.settings_window_opacity
        
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

            # Check if critical settings changed that require restart
            model_changed = model != self.cfgm.config.stt.model
            device_changed = device != self.cfgm.config.stt.device
            compute_changed = compute != self.cfgm.config.stt.compute_type
            
            needs_restart = model_changed or device_changed or compute_changed

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
                ui__accent_color_idle=self.var_color_idle.get().strip(),
                ui__accent_color_recording=self.var_color_recording.get().strip(),
                ui__accent_color_processing=self.var_color_processing.get().strip(),
                ui__settings_window_opacity=float(self.var_settings_opacity.get()),
                ui__overlay_opacity=float(self.var_overlay_opacity.get()),
                ui__visualizer_size=int(self.var_visualizer_size.get()),
            )
            
            # Show success message with restart warning if needed
            self._show_success_message(needs_restart=needs_restart)
            
        except Exception as e:
            messagebox.showerror("Settings Error", f"Failed to save: {e}")

    def _show_success_message(self, needs_restart: bool = False) -> None:
        """Show a modern success message.
        
        Args:
            needs_restart: If True, shows prominent restart warning
        """
        # Create a custom success dialog
        success_win = tk.Toplevel(self.win)
        success_win.title("Success")
        height = 140 if needs_restart else 120
        success_win.geometry(f"360x{height}")
        success_win.configure(bg=ColorTheme.BG_DARK)
        success_win.transient(self.win)
        success_win.grab_set()
        
        # Center on parent
        if self.win:
            x = self.win.winfo_x() + (self.win.winfo_width() - 360) // 2
            y = self.win.winfo_y() + (self.win.winfo_height() - height) // 2
            success_win.geometry(f"+{x}+{y}")
        
        # Remove window decorations
        success_win.overrideredirect(True)
        
        # Make it appear above settings window
        try:
            success_win.attributes('-topmost', True)
        except:
            pass
        
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
        
        if needs_restart:
            # Prominent restart warning
            restart_label = ttk.Label(
                frame,
                text="⚠ RESTART REQUIRED",
                style='Modern.TLabel',
                font=('Segoe UI', 10, 'bold'),
                foreground='#f59e0b'  # Orange warning color
            )
            restart_label.pack(pady=(8, 2))
            
            hint_label = ttk.Label(
                frame,
                text="Model/device changes require app restart",
                style='Modern.TLabel',
                font=('Segoe UI', 8),
                foreground=ColorTheme.TEXT_SECONDARY
            )
            hint_label.pack(pady=(0, 0))
        else:
            hint_label = ttk.Label(
                frame,
                text="Some changes may require restart",
                style='Modern.TLabel',
                font=('Segoe UI', 8),
                foreground=ColorTheme.TEXT_SECONDARY
            )
            hint_label.pack(pady=(5, 0))
        
        # Auto-close after 3 seconds (longer if restart needed)
        close_delay = 3500 if needs_restart else 2000
        success_win.after(close_delay, success_win.destroy)

    def _show_impl(self) -> None:
        """Show the settings window implementation."""
        print("[SettingsWindow] Show requested")
        
        # Take a snapshot of the config for cancel functionality
        import copy
        self._original_config = copy.deepcopy(self.cfgm.config)
        
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
