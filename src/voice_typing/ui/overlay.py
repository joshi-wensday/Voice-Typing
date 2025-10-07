"""Modern draggable circular overlay visualizer with stunning animations and gradients."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import Canvas
from typing import Callable, Optional, TYPE_CHECKING, List, Tuple
from PIL import Image, ImageDraw, ImageTk

if TYPE_CHECKING:
    from ..config.manager import ConfigManager

from .effects import (
    ColorTheme,
    ease_out_sine,
    ease_in_out_cubic,
    interpolate_color,
    lerp,
    clamp,
)


class Overlay:
    """Modern circular overlay visualizer with stunning animations.
    
    Features:
    - Gradient backgrounds that change based on state (idle/recording/processing)
    - Smooth circular waveform visualization
    - Pulsing animations based on audio level
    - Particle effects for visual feedback
    - Smooth state transitions with easing
    - Interactive hover and click effects
    """
    
    def __init__(
        self,
        get_level: Callable[[], float],
        size: int = 100,
        opacity: float = 0.8,
        position: tuple[int, int] = (100, 100),
        root: Optional[tk.Tk] = None,
        config_manager: Optional["ConfigManager"] = None,
    ) -> None:
        self.get_level = get_level
        self.size = size
        self.opacity = opacity
        self.position = position
        self.root: Optional[tk.Tk] = root
        self.config_manager = config_manager
        self.win: Optional[tk.Toplevel] = None
        self.canvas: Optional[Canvas] = None
        
        # Drag handling
        self._drag_start_pos = (0, 0)
        self._drag_start_window_pos = (0, 0)
        self._dragged = False
        self._running = False
        
        # Callbacks
        self.on_toggle: Optional[Callable[[], None]] = None
        self.on_settings: Optional[Callable[[], None]] = None
        
        # Animation state
        self._state = "idle"  # idle, recording, processing
        self._target_state = "idle"
        self._state_transition_progress = 1.0  # 0 to 1
        self._animation_frame = 0
        self._pulse_scale = 1.0
        self._target_pulse_scale = 1.0
        self._breathing_phase = 0.0
        
        # Waveform data (circular frequency bars)
        self._waveform_bars = 48  # Number of bars around the circle
        self._waveform_values = [0.0] * self._waveform_bars
        self._waveform_target_values = [0.0] * self._waveform_bars
        
        # Hover state
        self._is_hovering = False
        self._hover_alpha = 0.0
        
        # Ripple effect (for clicks)
        self._ripple_active = False
        self._ripple_radius = 0.0
        self._ripple_alpha = 0.0
        
        # Cached gradient images
        self._gradient_cache = {}
        
        # Performance: update at ~30 FPS (33ms)
        self._update_interval_ms = 33

    def _build(self) -> None:
        """Build the overlay window and canvas."""
        assert self.win is not None
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        
        # Make window transparent (the key to circular appearance!)
        try:
            self.win.attributes("-transparentcolor", "black")
        except:
            pass  # Transparency not supported on this platform
        
        self.win.geometry(f"{self.size}x{self.size}+{self.position[0]}+{self.position[1]}")
        self.win.configure(bg="black")
        
        self.canvas = Canvas(
            self.win,
            width=self.size,
            height=self.size,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Event bindings
        self.canvas.bind('<ButtonPress-1>', self._on_left_press)
        self.canvas.bind('<B1-Motion>', self._on_left_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_left_release)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.canvas.bind('<Enter>', self._on_mouse_enter)
        self.canvas.bind('<Leave>', self._on_mouse_leave)
        
        # Initial draw
        self._draw(0.0)

    def set_state(self, state: str) -> None:
        """Set the visualizer state (idle, recording, processing).
        
        Args:
            state: One of 'idle', 'recording', or 'processing'
        """
        if state != self._target_state:
            self._target_state = state
            self._state_transition_progress = 0.0

    def _update_state_transition(self) -> None:
        """Update state transition animation."""
        if self._state_transition_progress < 1.0:
            # Smooth transition over 300ms
            transition_speed = self._update_interval_ms / 300.0
            self._state_transition_progress = min(1.0, self._state_transition_progress + transition_speed)
            
            # Apply easing
            eased_progress = ease_in_out_cubic(self._state_transition_progress)
            
            if eased_progress >= 1.0:
                self._state = self._target_state

    def _get_state_colors(self, state: str) -> Tuple[str, str, str]:
        """Get gradient colors for a given state.
        
        Returns:
            Tuple of (inner_color, mid_color, outer_color)
        """
        if state == "recording":
            return ('#ef4444', '#f59e0b', '#7c2d12')
        elif state == "processing":
            return ('#eab308', '#f59e0b', '#78350f')
        else:  # idle
            return ('#3b82f6', '#8b5cf6', '#1e293b')

    def _interpolate_state_colors(self) -> Tuple[str, str, str]:
        """Interpolate colors between current and target state."""
        if self._state_transition_progress >= 1.0:
            return self._get_state_colors(self._target_state)
        
        # Interpolate between current and target
        current_colors = self._get_state_colors(self._state)
        target_colors = self._get_state_colors(self._target_state)
        
        t = ease_in_out_cubic(self._state_transition_progress)
        
        return (
            interpolate_color(current_colors[0], target_colors[0], t),
            interpolate_color(current_colors[1], target_colors[1], t),
            interpolate_color(current_colors[2], target_colors[2], t),
        )

    def _create_gradient_background(self, colors: Tuple[str, str, str]) -> ImageTk.PhotoImage:
        """Create a radial gradient background (truly circular with transparency).
        
        Args:
            colors: Tuple of (inner, mid, outer) colors
        
        Returns:
            PhotoImage for canvas
        """
        # Check cache
        cache_key = f"{colors}_{self.size}"
        if cache_key in self._gradient_cache:
            return self._gradient_cache[cache_key]
        
        size = self.size
        # Create RGBA image with transparency
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))  # Fully transparent
        draw = ImageDraw.Draw(img)
        
        cx, cy = size // 2, size // 2
        # Use actual circle radius, not diagonal
        max_radius = size // 2
        
        # Draw multi-stop radial gradient (circular)
        steps = 100
        for i in range(steps, 0, -1):
            t = i / steps
            radius = max_radius * t
            
            # Determine which color pair to interpolate
            if t > 0.5:
                # Outer to mid
                local_t = (t - 0.5) * 2
                color = interpolate_color(colors[1], colors[2], local_t)
            else:
                # Mid to inner
                local_t = t * 2
                color = interpolate_color(colors[0], colors[1], local_t)
            
            # Convert hex to RGB
            from .effects import hex_to_rgb
            rgb = hex_to_rgb(color)
            
            # Draw with full opacity inside the circle
            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
            draw.ellipse(bbox, fill=rgb + (255,))  # Add alpha channel
        
        photo = ImageTk.PhotoImage(img)
        
        # Cache it (limit cache size)
        if len(self._gradient_cache) < 10:
            self._gradient_cache[cache_key] = photo
        
        return photo

    def _update_waveform(self, level: float) -> None:
        """Update waveform bar values with smooth interpolation."""
        # Generate semi-random waveform based on level and animation frame
        # This simulates frequency bars
        for i in range(self._waveform_bars):
            # Create variation across bars using sine waves
            phase_offset = (i / self._waveform_bars) * 2 * math.pi
            variation = (math.sin(self._animation_frame * 0.1 + phase_offset) + 1) / 2
            target = level * (0.3 + variation * 0.7)
            
            # Smooth interpolation to target
            self._waveform_target_values[i] = target
            self._waveform_values[i] = lerp(
                self._waveform_values[i],
                self._waveform_target_values[i],
                0.3  # Smoothing factor
            )

    def _draw_vibrating_edge(self, cx: float, cy: float, base_radius: float, level: float) -> None:
        """Draw vibrating edge effect for the circle.
        
        The edge vibrates/pulses outward based on audio level, making it very clear
        when voice input is being received.
        """
        if not self.canvas:
            return
        
        colors = self._interpolate_state_colors()
        edge_color = colors[0]
        glow_color = colors[1]
        
        # Create points for the vibrating edge
        points = []
        num_points = self._waveform_bars
        
        for i in range(num_points + 1):  # +1 to close the circle
            angle = (2 * math.pi * i / num_points)
            
            # Calculate vibration amount based on waveform value
            vibration = self._waveform_values[i % num_points] * (self.size / 8)
            
            # Add vibration to radius
            current_radius = base_radius + vibration
            
            # Calculate point position
            x = cx + current_radius * math.cos(angle)
            y = cy + current_radius * math.sin(angle)
            
            points.extend([x, y])
        
        # Draw the vibrating circle as a thick polygon outline
        if len(points) >= 6:  # Need at least 3 points
            # Draw glow effect (outer vibrating edge)
            glow_points = []
            for i in range(num_points + 1):
                angle = (2 * math.pi * i / num_points)
                vibration = self._waveform_values[i % num_points] * (self.size / 8)
                glow_radius = base_radius + vibration + 3
                
                x = cx + glow_radius * math.cos(angle)
                y = cy + glow_radius * math.sin(angle)
                glow_points.extend([x, y])
            
            # Draw glow
            if len(glow_points) >= 6:
                self.canvas.create_polygon(
                    glow_points,
                    fill='',
                    outline=glow_color,
                    width=3,
                    smooth=True
                )
            
            # Draw main vibrating edge
            self.canvas.create_polygon(
                points,
                fill='',
                outline=edge_color,
                width=4,
                smooth=True
            )

    def _draw_center_circle(self, cx: float, cy: float, radius: float) -> None:
        """Draw the center filled circle."""
        if not self.canvas:
            return
        
        colors = self._interpolate_state_colors()
        fill_color = colors[0]
        
        # Apply pulse scale
        scaled_radius = radius * self._pulse_scale
        
        self.canvas.create_oval(
            cx - scaled_radius, cy - scaled_radius,
            cx + scaled_radius, cy + scaled_radius,
            fill=fill_color,
            outline='',
        )
        
        # Add subtle glow ring
        glow_radius = scaled_radius * 1.15
        glow_color = colors[1]
        self.canvas.create_oval(
            cx - glow_radius, cy - glow_radius,
            cx + glow_radius, cy + glow_radius,
            outline=glow_color,
            width=2,
        )

    def _draw_hover_effect(self, cx: float, cy: float, radius: float) -> None:
        """Draw hover highlight effect."""
        if not self.canvas or self._hover_alpha <= 0:
            return
        
        # Create a subtle highlight ring
        highlight_radius = radius * 1.3
        alpha_int = int(self._hover_alpha * 100)
        
        # Use a light color with transparency effect (simulated with lighter shade)
        highlight_color = '#ffffff'
        
        self.canvas.create_oval(
            cx - highlight_radius, cy - highlight_radius,
            cx + highlight_radius, cy + highlight_radius,
            outline=highlight_color,
            width=1,
        )

    def _draw_ripple_effect(self, cx: float, cy: float) -> None:
        """Draw click ripple animation."""
        if not self.canvas or not self._ripple_active:
            return
        
        if self._ripple_alpha > 0:
            # Calculate color with fading alpha simulation
            colors = self._interpolate_state_colors()
            ripple_color = colors[0]
            
            self.canvas.create_oval(
                cx - self._ripple_radius, cy - self._ripple_radius,
                cx + self._ripple_radius, cy + self._ripple_radius,
                outline=ripple_color,
                width=2,
            )

    def _update_animations(self, level: float) -> None:
        """Update all animation states."""
        self._animation_frame += 1
        
        # Update state transition
        self._update_state_transition()
        
        # Update pulse scale based on audio level
        if self._target_state == "recording":
            self._target_pulse_scale = 1.0 + level * 0.15
        elif self._target_state == "processing":
            # Gentle pulsing for processing
            self._target_pulse_scale = 1.0 + 0.05 * (math.sin(self._animation_frame * 0.15) + 1) / 2
        else:
            # Idle: subtle breathing animation
            self._breathing_phase += 0.02
            self._target_pulse_scale = 1.0 + 0.03 * math.sin(self._breathing_phase)
        
        # Smooth pulse interpolation
        self._pulse_scale = lerp(self._pulse_scale, self._target_pulse_scale, 0.2)
        
        # Update waveform
        self._update_waveform(level)
        
        # Update hover effect
        if self._is_hovering:
            self._hover_alpha = min(1.0, self._hover_alpha + 0.1)
        else:
            self._hover_alpha = max(0.0, self._hover_alpha - 0.1)
        
        # Update ripple effect
        if self._ripple_active:
            self._ripple_radius += self.size / 40
            self._ripple_alpha -= 0.05
            if self._ripple_alpha <= 0:
                self._ripple_active = False

    def _draw(self, level: float) -> None:
        """Draw the complete visualizer.
        
        Args:
            level: Audio level (0.0 to 1.0)
        """
        if not self.canvas:
            return
        
        # Update animations first
        self._update_animations(level)
        
        # Clear canvas
        self.canvas.delete('all')
        
        # Draw gradient background
        colors = self._interpolate_state_colors()
        gradient = self._create_gradient_background(colors)
        self.canvas.create_image(0, 0, image=gradient, anchor=tk.NW)
        # Keep reference to prevent garbage collection
        self.canvas.image = gradient
        
        # Calculate positions
        cx = cy = self.size / 2
        base_radius = self.size / 3
        
        # Draw ripple effect (behind everything)
        self._draw_ripple_effect(cx, cy)
        
        # Draw vibrating edge effect (replaces waveform bars)
        self._draw_vibrating_edge(cx, cy, base_radius, level)
        
        # Draw center circle (filled)
        center_radius = base_radius * 0.8  # Make it larger for better visibility
        self._draw_center_circle(cx, cy, center_radius)
        
        # Draw hover effect (on top)
        self._draw_hover_effect(cx, cy, base_radius)

    def _tick(self) -> None:
        """Main animation loop tick."""
        if not self._running or self.win is None:
            return
        
        # Get current audio level
        lvl = max(0.0, min(1.0, float(self.get_level())))
        
        # Redraw
        self._draw(lvl)
        
        # Schedule next frame
        self.win.after(self._update_interval_ms, self._tick)

    def _trigger_ripple(self) -> None:
        """Trigger a ripple animation effect."""
        self._ripple_active = True
        self._ripple_radius = self.size / 6
        self._ripple_alpha = 1.0

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    def _on_mouse_enter(self, _e: tk.Event) -> None:
        """Handle mouse enter (hover start)."""
        self._is_hovering = True

    def _on_mouse_leave(self, _e: tk.Event) -> None:
        """Handle mouse leave (hover end)."""
        self._is_hovering = False

    def _on_right_click(self, _e: tk.Event) -> None:
        """Handle right-click to open settings."""
        if self.on_settings:
            self.on_settings()

    def _on_left_press(self, e: tk.Event) -> None:
        """Handle left button press (start of drag or click)."""
        self._drag_start_pos = (e.x, e.y)
        if self.win:
            self._drag_start_window_pos = (self.win.winfo_x(), self.win.winfo_y())
        self._dragged = False

    def _on_left_drag(self, e: tk.Event) -> None:
        """Handle left button drag (move overlay)."""
        if not self.win:
            return
        
        # Calculate movement
        dx = e.x - self._drag_start_pos[0]
        dy = e.y - self._drag_start_pos[1]
        
        # If moved more than 3 pixels, consider it a drag
        if abs(dx) > 3 or abs(dy) > 3:
            self._dragged = True
            x = self._drag_start_window_pos[0] + dx
            y = self._drag_start_window_pos[1] + dy
            self.win.geometry(f"+{x}+{y}")
            self.position = (x, y)

    def _on_left_release(self, e: tk.Event) -> None:
        """Handle left button release (end drag or perform click)."""
        if self._dragged:
            # Drag ended - save position to config
            if self.config_manager:
                try:
                    self.config_manager.update(ui__visualizer_position=list(self.position))
                except Exception:
                    # Fail silently if config update fails
                    pass
        else:
            # Click (no drag) - toggle and trigger ripple
            self._trigger_ripple()
            if self.on_toggle:
                self.on_toggle()

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def show(self) -> None:
        """Show the overlay window."""
        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()
        if self.win is not None and tk.Toplevel.winfo_exists(self.win):
            self.win.deiconify()
        else:
            self.win = tk.Toplevel(self.root)
            self._build()
        self._running = True
        self._tick()

    def hide(self) -> None:
        """Hide the overlay window."""
        self._running = False
        if self.win:
            self.win.withdraw()
