"""Visual effects, animations, and gradients for modern UI components.

This module provides utilities for creating beautiful visual effects including:
- Gradient generation (radial, linear, multi-stop)
- Easing functions for smooth animations
- Color manipulation and interpolation
- Animation helpers
"""

from __future__ import annotations

import math
from typing import Tuple, List, Optional
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import tkinter as tk


# ============================================================================
# COLOR UTILITIES
# ============================================================================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color."""
    return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'


def interpolate_color(color1: str, color2: str, t: float) -> str:
    """Interpolate between two hex colors (t from 0 to 1)."""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    rgb = tuple(int(rgb1[i] + (rgb2[i] - rgb1[i]) * t) for i in range(3))
    return rgb_to_hex(rgb)


def adjust_brightness(color: str, factor: float) -> str:
    """Adjust color brightness by factor (1.0 = no change, >1.0 brighter, <1.0 darker)."""
    rgb = hex_to_rgb(color)
    rgb = tuple(min(255, int(c * factor)) for c in rgb)
    return rgb_to_hex(rgb)


# ============================================================================
# EASING FUNCTIONS
# ============================================================================

def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out easing function."""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out easing function."""
    return 1 - pow(1 - t, 3)


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in easing function."""
    return t * t * t


def ease_out_sine(t: float) -> float:
    """Sine ease-out easing function."""
    return math.sin(t * math.pi / 2)


def ease_in_out_sine(t: float) -> float:
    """Sine ease-in-out easing function."""
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_elastic(t: float) -> float:
    """Elastic ease-out (bouncy effect)."""
    c4 = (2 * math.pi) / 3
    if t == 0 or t == 1:
        return t
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


# ============================================================================
# GRADIENT GENERATION
# ============================================================================

def create_radial_gradient(
    size: int,
    center_color: str,
    edge_color: str,
    center: Optional[Tuple[int, int]] = None,
) -> ImageTk.PhotoImage:
    """Create a radial gradient image.
    
    Args:
        size: Width and height of the gradient (square)
        center_color: Color at the center (hex)
        edge_color: Color at the edges (hex)
        center: Optional center point (default is center of image)
    
    Returns:
        PhotoImage ready for Tkinter canvas
    """
    img = Image.new('RGB', (size, size), edge_color)
    draw = ImageDraw.Draw(img)
    
    cx, cy = center or (size // 2, size // 2)
    max_radius = math.sqrt(cx**2 + cy**2)
    
    center_rgb = hex_to_rgb(center_color)
    edge_rgb = hex_to_rgb(edge_color)
    
    # Draw concentric circles with interpolated colors
    steps = 100
    for i in range(steps, 0, -1):
        t = i / steps
        radius = max_radius * t
        color_t = 1 - t  # Invert for center to edge
        r = int(center_rgb[0] + (edge_rgb[0] - center_rgb[0]) * color_t)
        g = int(center_rgb[1] + (edge_rgb[1] - center_rgb[1]) * color_t)
        b = int(center_rgb[2] + (edge_rgb[2] - center_rgb[2]) * color_t)
        color = (r, g, b)
        
        bbox = [
            cx - radius, cy - radius,
            cx + radius, cy + radius
        ]
        draw.ellipse(bbox, fill=color)
    
    return ImageTk.PhotoImage(img)


def create_linear_gradient(
    width: int,
    height: int,
    color1: str,
    color2: str,
    angle: float = 0,
) -> ImageTk.PhotoImage:
    """Create a linear gradient image.
    
    Args:
        width: Width of the gradient
        height: Height of the gradient
        color1: Start color (hex)
        color2: End color (hex)
        angle: Gradient angle in degrees (0 = left to right)
    
    Returns:
        PhotoImage ready for Tkinter canvas
    """
    img = Image.new('RGB', (width, height), color1)
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    
    # For simplicity, we'll support horizontal (0°) and vertical (90°) gradients
    if angle == 90:
        # Vertical gradient
        for y in range(height):
            t = y / height
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * t)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * t)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * t)
            for x in range(width):
                img.putpixel((x, y), (r, g, b))
    else:
        # Horizontal gradient (default)
        for x in range(width):
            t = x / width
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * t)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * t)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * t)
            for y in range(height):
                img.putpixel((x, y), (r, g, b))
    
    return ImageTk.PhotoImage(img)


def create_multi_stop_radial_gradient(
    size: int,
    color_stops: List[Tuple[float, str]],
    center: Optional[Tuple[int, int]] = None,
) -> ImageTk.PhotoImage:
    """Create a radial gradient with multiple color stops.
    
    Args:
        size: Width and height of the gradient (square)
        color_stops: List of (position, color) tuples where position is 0-1
        center: Optional center point (default is center of image)
    
    Returns:
        PhotoImage ready for Tkinter canvas
    """
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    
    cx, cy = center or (size // 2, size // 2)
    max_radius = math.sqrt(cx**2 + cy**2)
    
    # Sort color stops by position
    color_stops = sorted(color_stops, key=lambda x: x[0])
    
    # Draw concentric circles
    steps = 200
    for i in range(steps, 0, -1):
        t = i / steps
        radius = max_radius * t
        
        # Find the two color stops to interpolate between
        color = color_stops[0][1]
        for j in range(len(color_stops) - 1):
            if color_stops[j][0] <= (1 - t) <= color_stops[j + 1][0]:
                pos1, col1 = color_stops[j]
                pos2, col2 = color_stops[j + 1]
                local_t = ((1 - t) - pos1) / (pos2 - pos1)
                color = interpolate_color(col1, col2, local_t)
                break
        else:
            # If we're past the last stop
            if (1 - t) >= color_stops[-1][0]:
                color = color_stops[-1][1]
        
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        draw.ellipse(bbox, fill=color)
    
    return ImageTk.PhotoImage(img)


def apply_glow(
    img: Image.Image,
    glow_radius: int = 10,
    glow_strength: float = 1.0,
) -> Image.Image:
    """Apply a glow effect to an image.
    
    Args:
        img: Source PIL Image
        glow_radius: Radius of the glow blur
        glow_strength: Strength multiplier (0-1+)
    
    Returns:
        New PIL Image with glow effect
    """
    # Create a copy and apply blur
    glowed = img.copy()
    glowed = glowed.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    
    # Blend with original
    if glow_strength < 1.0:
        glowed = Image.blend(img, glowed, glow_strength)
    
    return glowed


# ============================================================================
# ANIMATION HELPERS
# ============================================================================

class AnimationController:
    """Helper class to manage smooth animations with easing."""
    
    def __init__(
        self,
        duration_ms: int = 300,
        fps: int = 60,
        easing_func=ease_in_out_cubic,
    ):
        """Initialize animation controller.
        
        Args:
            duration_ms: Duration of animation in milliseconds
            fps: Target frames per second
            easing_func: Easing function to use
        """
        self.duration_ms = duration_ms
        self.fps = fps
        self.easing_func = easing_func
        self.frame_delay_ms = int(1000 / fps)
        
        self._active = False
        self._current_frame = 0
        self._total_frames = int(duration_ms / self.frame_delay_ms)
        self._callback = None
        self._completion_callback = None
        self._after_id = None
    
    def animate(
        self,
        start_value: float,
        end_value: float,
        on_update,
        on_complete=None,
        widget: Optional[tk.Widget] = None,
    ):
        """Start an animation from start_value to end_value.
        
        Args:
            start_value: Starting value
            end_value: Ending value
            on_update: Callback(value) called each frame
            on_complete: Optional callback called when animation completes
            widget: Widget to schedule updates on (must have .after method)
        """
        if widget is None:
            raise ValueError("Widget required for animation scheduling")
        
        self.stop()
        self._active = True
        self._current_frame = 0
        self._callback = on_update
        self._completion_callback = on_complete
        
        def step():
            if not self._active:
                return
            
            progress = self._current_frame / self._total_frames
            eased_progress = self.easing_func(min(1.0, progress))
            value = start_value + (end_value - start_value) * eased_progress
            
            if self._callback:
                self._callback(value)
            
            self._current_frame += 1
            
            if self._current_frame <= self._total_frames:
                self._after_id = widget.after(self.frame_delay_ms, step)
            else:
                self._active = False
                if self._completion_callback:
                    self._completion_callback()
        
        step()
    
    def stop(self):
        """Stop the current animation."""
        self._active = False
        if self._after_id:
            # Note: We can't cancel after callbacks without widget reference
            pass


# ============================================================================
# THEME COLORS
# ============================================================================

class ColorTheme:
    """Modern color theme for the application."""
    
    # Overlay themes for different states
    IDLE_GRADIENT = [
        (0.0, '#3b82f6'),   # Blue
        (0.5, '#8b5cf6'),   # Purple
        (1.0, '#1e293b'),   # Dark blue
    ]
    
    RECORDING_GRADIENT = [
        (0.0, '#ef4444'),   # Red
        (0.5, '#f59e0b'),   # Orange
        (1.0, '#7c2d12'),   # Dark orange
    ]
    
    PROCESSING_GRADIENT = [
        (0.0, '#eab308'),   # Yellow
        (0.5, '#f59e0b'),   # Orange
        (1.0, '#78350f'),   # Dark yellow
    ]
    
    # UI colors for settings window
    BG_DARK = '#1a1a2e'
    BG_DARKER = '#16213e'
    BG_CARD = '#0f172a'
    
    ACCENT_PRIMARY = '#8b5cf6'    # Purple
    ACCENT_SECONDARY = '#3b82f6'  # Blue
    ACCENT_SUCCESS = '#10b981'    # Green
    ACCENT_ERROR = '#ef4444'      # Red
    
    TEXT_PRIMARY = '#f1f5f9'
    TEXT_SECONDARY = '#94a3b8'
    TEXT_DISABLED = '#475569'
    
    BORDER = '#334155'
    BORDER_LIGHT = '#475569'
    
    # Gradients for buttons
    BUTTON_GRADIENT_START = '#8b5cf6'
    BUTTON_GRADIENT_END = '#6366f1'
    BUTTON_HOVER_START = '#a78bfa'
    BUTTON_HOVER_END = '#818cf8'


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_rounded_rectangle(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: int = 10,
    **kwargs,
) -> int:
    """Create a rounded rectangle on a canvas.
    
    Args:
        canvas: Tkinter canvas
        x1, y1: Top-left corner
        x2, y2: Bottom-right corner
        radius: Corner radius
        **kwargs: Additional arguments for canvas.create_polygon
    
    Returns:
        Canvas item ID
    """
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    
    return canvas.create_polygon(points, smooth=True, **kwargs)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))
