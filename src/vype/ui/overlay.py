"""Overlay visualizer — deeply redesigned with state-specific visual language.

Visual language:
  idle       — deep glowing orb + slow sonar-ping rings + 3-dot mic indicator
  recording  — reactive waveform edge + radial audio bars in the core
  processing — orbiting comet dots (3 × 120°) + spinning arc in the core
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import Canvas, ttk
from typing import Callable, Optional, TYPE_CHECKING, List, Tuple
from PIL import Image, ImageDraw, ImageTk

if TYPE_CHECKING:
    from ..config.manager import ConfigManager

from .effects import (
    ColorTheme,
    ease_out_sine,
    ease_in_out_cubic,
    interpolate_color,
    hex_to_rgb,
    lerp,
    clamp,
)
from .spectrum_analyzer import SpectrumAnalyzer

# Human-readable names for command tools (used in toast + correction dialog)
_TOOL_DISPLAY_NAMES: dict[str, str] = {
    "NEW_LINE": "New Line",
    "NEW_PARAGRAPH": "New Paragraph",
    "SAVE": "Save File",
    "UNDO": "Undo",
    "SCRATCH_THAT": "Scratch That  (delete last segment)",
    "DELETE_WORD": "Delete Word",
    "DELETE_LINE": "Delete Line",
    "BULLET_POINT": "Bullet Point",
    "STOP": "Stop Dictation",
    "CAPITALIZE": "Capitalize",
    "LOWERCASE": "Lowercase",
}


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
        # Called when user confirms a correction in the dialog: (phrase, tool) -> None
        self.on_correction_save: Optional[Callable[[str, str], None]] = None

        # Toast / feedback state
        self._toast_win: Optional[tk.Toplevel] = None
        self._toast_after_id: Optional[str] = None
        self._toast_phrase: str = ""
        self._toast_tool: str = ""
        
        # Animation state
        self._state = "idle"  # idle, recording, processing
        self._target_state = "idle"
        self._state_transition_progress = 1.0  # 0 to 1
        self._animation_frame = 0
        self._pulse_scale = 1.0
        self._target_pulse_scale = 1.0
        self._breathing_phase = 0.0
        
        # Waveform data (circular frequency bars) - increased for smoother curves
        self._waveform_bars = 64  # Increased from 48 for smoother visualization
        self._waveform_values = [0.0] * self._waveform_bars
        self._waveform_target_values = [0.0] * self._waveform_bars
        
        # Hover state
        self._is_hovering = False
        self._hover_alpha = 0.0
        
        # Ripple effect (for clicks)
        self._ripple_active = False
        self._ripple_radius = 0.0
        self._ripple_alpha = 0.0
        
        # Cached gradient images (key → ImageTk.PhotoImage)
        self._gradient_cache: dict = {}
        # Strong reference so Tkinter doesn't GC the PhotoImage between frames
        self._current_orb_photo: Optional[ImageTk.PhotoImage] = None

        # Spectrum analyzer
        self._spectrum_analyzer = SpectrumAnalyzer(
            sample_rate=16000,
            num_bands=64,
            smoothing=0.15,
        )
        self._audio_capture = None

        # ── Sonar-ping rings (idle) ───────────────────────────────────────
        # Each ring: {'r': float, 'alpha': float}
        self._sonar_rings: list[dict] = []
        self._sonar_timer: int = 0
        self._sonar_interval: int = 150   # frames between spawns (~1.7 s at 90 fps)

        # ── Processing orbit ──────────────────────────────────────────────
        self._spinner_angle: float = 0.0   # degrees, advances each frame

        # ── Spinning arc (processing core icon) ──────────────────────────
        self._arc_angle: float = 0.0       # leading-edge angle in degrees

        # Performance: ~90 FPS
        self._update_interval_ms = 11

    # Extra pixels below the circle reserved for the status pill label.
    _PILL_HEIGHT = 28

    def _build(self) -> None:
        """Build the overlay window and canvas."""
        assert self.win is not None
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        # Make window transparent (the key to circular appearance!)
        try:
            self.win.attributes("-transparentcolor", "black")
            self.win.wm_attributes("-alpha", self.opacity)
        except Exception:
            pass  # Transparency not supported on this platform

        total_height = self.size + self._PILL_HEIGHT
        self.win.geometry(f"{self.size}x{total_height}+{self.position[0]}+{self.position[1]}")
        self.win.configure(bg="black")

        self.canvas = Canvas(
            self.win,
            width=self.size,
            height=total_height,
            bg="black",
            highlightthickness=0,
            borderwidth=0,
            relief='flat',
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
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
    
    def set_audio_capture(self, audio_capture) -> None:
        """Set the audio capture instance for real-time spectrum visualization.
        
        Args:
            audio_capture: AudioCapture instance
        """
        self._audio_capture = audio_capture

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
        """Return (inner, mid, outer) gradient colours for ``state``.

        The three stops are derived from a single *base* accent colour so the
        orb always looks like a glowing sphere:
          inner  = accent blended 35 % toward white  (bright highlight)
          mid    = accent colour itself
          outer  = accent blended 90 % toward near-black  (deep shadow rim)
        """
        if self.config_manager:
            cfg = self.config_manager.config.ui
            if state == "recording":
                base = cfg.accent_color_recording
            elif state == "processing":
                base = cfg.accent_color_processing
            else:
                base = cfg.accent_color_idle
        else:
            if state == "recording":
                base = '#ef4444'
            elif state == "processing":
                base = '#eab308'
            else:
                base = '#3b82f6'

        inner = interpolate_color(base, '#ffffff', 0.35)
        outer = interpolate_color(base, '#010203', 0.90)
        return (inner, base, outer)

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
        """Build a circular radial-gradient PIL image for the orb background.

        The image is ``size × size`` RGBA.  Pixels outside the circle have
        alpha=0 so they are invisible (Tkinter maps them to black which the
        ``-transparentcolor black`` window attribute makes truly transparent).

        Gradient stops (outer → inner):
          colours[2]  outer edge  (near-black — gives a dark atmospheric rim)
          colours[1]  mid-point   (accent colour)
          colours[0]  inner core  (bright / white-tinted highlight)
        """
        size = self.size
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = size / 2, size / 2
        max_r = size / 2 - 1   # leave 1 px margin so anti-alias doesn't clip

        steps = 80
        for i in range(steps, 0, -1):
            t = i / steps          # 1.0 = outer, 0.0 = inner
            r = max_r * t

            # Three-stop gradient: outer(t=1) → mid(t=0.5) → inner(t=0)
            if t > 0.55:
                local = (t - 0.55) / 0.45
                hex_c = interpolate_color(colors[1], colors[2], local)
            else:
                local = t / 0.55
                hex_c = interpolate_color(colors[0], colors[1], local)

            rgb = hex_to_rgb(hex_c)
            bbox = [cx - r, cy - r, cx + r, cy + r]
            draw.ellipse(bbox, fill=rgb + (255,))

        photo = ImageTk.PhotoImage(img)
        return photo

    def _update_waveform(self, level: float) -> None:
        """Update waveform bar values with smooth interpolation."""
        # Always try to get real spectrum data when recording OR processing
        if self._audio_capture is not None and (self._target_state == "recording" or self._target_state == "processing"):
            try:
                audio_chunk = self._audio_capture.get_latest_chunk()
                if audio_chunk.size > 100:  # Need enough samples for FFT
                    # Get real frequency spectrum
                    spectrum = self._spectrum_analyzer.analyze(audio_chunk)
                    # Apply moderate boosting for visibility (reduced since we now have noise floor)
                    for i in range(min(len(spectrum), self._waveform_bars)):
                        # Apply power scaling to make differences more visible
                        boosted = spectrum[i] ** 0.75  # Power < 1 boosts small values
                        # Faster interpolation for more responsive updates
                        self._waveform_values[i] = lerp(
                            self._waveform_values[i],
                            boosted * 1.2,  # Moderate scale up
                            0.4  # Increased from implicit direct assignment for smooth but responsive updates
                        )
                    return
            except Exception:
                pass  # Fall back to pseudo-spectrum
        
        # Idle state or fallback: fade to zero
        if self._target_state == "idle":
            for i in range(self._waveform_bars):
                self._waveform_values[i] = lerp(self._waveform_values[i], 0.0, 0.15)  # Slightly faster fade
        else:
            # Fallback for other states
            for i in range(self._waveform_bars):
                phase_offset = (i / self._waveform_bars) * 2 * math.pi
                variation = (math.sin(self._animation_frame * 0.1 + phase_offset) + 1) / 2
                target = level * (0.3 + variation * 0.7)
                
                self._waveform_target_values[i] = target
                self._waveform_values[i] = lerp(
                    self._waveform_values[i],
                    self._waveform_target_values[i],
                    0.4  # Increased from 0.3 for faster response
                )

    # =====================================================================
    # NEW: Layered drawing system
    # =====================================================================

    def _draw_orb_background(self, cx: float, cy: float) -> None:
        """Render the radial-gradient orb sphere using a cached PIL image.

        The PIL image has transparent corners so only the circle is opaque.
        ``transparentcolor="black"`` on the window makes those corners invisible.
        """
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        # Quantise each channel to the nearest multiple of 6 for cache efficiency
        def _snap(hx: str) -> str:
            r, g, b = hex_to_rgb(hx)
            return f'#{(r // 6) * 6:02x}{(g // 6) * 6:02x}{(b // 6) * 6:02x}'
        key = f"{_snap(colors[0])},{_snap(colors[1])},{_snap(colors[2])},{self.size}"
        if key not in self._gradient_cache:
            if len(self._gradient_cache) > 24:
                self._gradient_cache.clear()
            self._gradient_cache[key] = self._create_gradient_background(colors)
        photo = self._gradient_cache[key]
        self._current_orb_photo = photo  # strong reference
        self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)

    def _draw_sonar_pings(self, cx: float, cy: float) -> None:
        """Idle-state animation: expanding sonar rings that fade outward."""
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        accent = colors[1]
        for ring in self._sonar_rings:
            r = ring['r']
            a = ring['alpha']
            # Fade toward near-black (not pure #000000 which is transparent)
            ring_color = interpolate_color('#010203', accent, a * 0.9)
            lw = max(1, int(a * 2.5))
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline=ring_color, width=lw,
            )

    def _draw_waveform_edge(self, cx: float, cy: float, base_radius: float) -> None:
        """Recording-state animation: vibrating frequency-reactive edge ring.

        Two concentric waveform polygons — outer glow + inner crisp edge —
        give a sense of depth and energy.
        """
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        noise_floor = 0.30
        num = self._waveform_bars
        max_vib = self.size / 8.0

        def _build_points(extra_offset: float) -> list:
            pts: list = []
            for i in range(num + 1):
                angle = 2 * math.pi * i / num
                wv = self._waveform_values[i % num]
                if wv < noise_floor:
                    wv = 0.0
                else:
                    wv = ((wv - noise_floor) / (1.0 - noise_floor)) ** 1.4
                r = base_radius + wv * max_vib + extra_offset
                pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
            return pts

        glow_pts = _build_points(2.5)
        edge_pts = _build_points(0.0)

        if len(glow_pts) >= 6:
            self.canvas.create_polygon(glow_pts, fill='', outline=colors[1], width=3, smooth=True)
        if len(edge_pts) >= 6:
            self.canvas.create_polygon(edge_pts, fill='', outline=colors[0], width=2, smooth=True)

    def _draw_processing_orbit(self, cx: float, cy: float, orbit_r: float) -> None:
        """Processing-state animation: 3 comet-trailed dots orbiting the core.

        Each dot has 4 trail segments that fade toward the background.
        """
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        accent = colors[0]
        dark = interpolate_color(colors[2], '#010203', 0.5)
        dot_r = max(2.5, self.size / 18.0)

        for i in range(3):
            head_deg = self._spinner_angle + i * 120.0
            # Trail (drawn first so it's behind the head dot)
            for step in range(5, 0, -1):
                trail_deg = head_deg - step * 16.0
                fade = (5 - step) / 5.0            # 0.2 … 1.0
                color = interpolate_color(dark, accent, fade * 0.6)
                tr = dot_r * (0.35 + fade * 0.45)
                rad = math.radians(trail_deg)
                tx = cx + orbit_r * math.cos(rad)
                ty = cy + orbit_r * math.sin(rad)
                self.canvas.create_oval(tx - tr, ty - tr, tx + tr, ty + tr,
                                        fill=color, outline='')
            # Head dot
            rad = math.radians(head_deg)
            dx = cx + orbit_r * math.cos(rad)
            dy = cy + orbit_r * math.sin(rad)
            self.canvas.create_oval(dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r,
                                    fill=accent, outline='')

    def _draw_core_disc(self, cx: float, cy: float, radius: float) -> None:
        """The bright pulsing disc at the centre of the orb.

        Three concentric filled ovals create an inner glow:
          outermost: mid-colour, larger radius
          middle:    accent-inner, standard radius × pulse
          innermost: white-tinted highlight
        """
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        sr = radius * self._pulse_scale

        # Outer soft halo
        halo_r = sr * 1.22
        self.canvas.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r,
                                fill=colors[1], outline='')
        # Main disc
        self.canvas.create_oval(cx - sr, cy - sr, cx + sr, cy + sr,
                                fill=colors[0], outline='')
        # Specular highlight (tiny bright spot, upper-left)
        hl_r = sr * 0.30
        hl_x, hl_y = cx - sr * 0.25, cy - sr * 0.25
        self.canvas.create_oval(hl_x - hl_r, hl_y - hl_r, hl_x + hl_r, hl_y + hl_r,
                                fill='#ffffff', outline='')

    def _draw_center_bars(self, cx: float, cy: float, radius: float) -> None:
        """Recording: 3 reactive frequency bars overlaid on the core disc."""
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        bar_w = max(2.0, radius * 0.22)
        gap = bar_w * 0.7
        total_w = 3 * bar_w + 2 * gap
        x0 = cx - total_w / 2
        # Sample low / mid / high bands
        band_indices = [8, 32, 55]
        for i, bi in enumerate(band_indices):
            h = max(bar_w, self._waveform_values[bi] * radius * 1.6)
            x = x0 + i * (bar_w + gap)
            y_bot = cy + bar_w * 0.6
            y_top = y_bot - h
            self.canvas.create_rectangle(x, y_top, x + bar_w, y_bot,
                                         fill='#ffffff', outline='')

    def _draw_center_dots(self, cx: float, cy: float, radius: float) -> None:
        """Idle: 3 stacked dots — a minimalist mic-off / standby indicator."""
        if not self.canvas:
            return
        colors = self._interpolate_state_colors()
        dot_r = max(1.5, radius * 0.10)
        pulse = self._pulse_scale
        for idx, offset in enumerate((-0.38, 0.0, 0.38)):
            y = cy + radius * offset
            r = dot_r * (0.85 + 0.15 * pulse) if idx == 1 else dot_r * 0.8
            fill = colors[0] if idx == 1 else interpolate_color(colors[0], colors[2], 0.4)
            self.canvas.create_oval(cx - r, cy - r + radius * offset,
                                    cx + r, cy + r + radius * offset,
                                    fill=fill, outline='')

    def _draw_center_arc(self, cx: float, cy: float, radius: float) -> None:
        """Processing: a short spinning arc inside the core disc."""
        if not self.canvas:
            return
        r = radius * 0.70
        start = self._arc_angle
        # Draw a 120° bright arc
        arc_pts: list = []
        arc_span = 120
        steps = 16
        for s in range(steps + 1):
            a = math.radians(start + arc_span * s / steps)
            arc_pts.extend([cx + r * math.cos(a), cy + r * math.sin(a)])
        if len(arc_pts) >= 4:
            self.canvas.create_line(arc_pts, fill='#ffffff', width=2,
                                    smooth=True, capstyle=tk.ROUND)

    def _draw_ripple_effect(self, cx: float, cy: float) -> None:
        """Expanding ring on click — now fades toward transparent correctly."""
        if not self.canvas or not self._ripple_active or self._ripple_alpha <= 0:
            return
        colors = self._interpolate_state_colors()
        color = interpolate_color('#010203', colors[0], self._ripple_alpha)
        lw = max(1, int(self._ripple_alpha * 3))
        r = self._ripple_radius
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                outline=color, width=lw)

    def _draw_status_pill(self, cx: float) -> None:
        """Draw a status pill below the circle showing state and hotkey hint.

        Uses a dark-navy fill so it renders through the transparent window.
        Shows the current state in the accent colour and the hotkey in a
        secondary/dimmed colour beneath it.
        """
        if not self.canvas:
            return

        colors = self._interpolate_state_colors()
        state = self._target_state

        _LABELS = {
            "idle": "IDLE",
            "recording": "LISTENING",
            "processing": "PROCESSING",
            "feedback": "FEEDBACK",
        }
        label = _LABELS.get(state, state.upper())

        # Hotkey hint shown only when idle (so it doesn't clutter active states)
        hotkey_hint = ""
        if state == "idle" and self.config_manager:
            try:
                hk = self.config_manager.config.ui.hotkey
                hotkey_hint = hk.replace("+", " + ").upper()
            except Exception:
                pass

        # Pill geometry: centred horizontally, sits in the extra 28px strip
        pill_y_center = self.size + self._PILL_HEIGHT // 2
        pill_w = 96
        pill_h = 20
        x0 = cx - pill_w // 2
        y0 = pill_y_center - pill_h // 2
        x1 = cx + pill_w // 2
        y1 = pill_y_center + pill_h // 2
        r = pill_h // 2  # fully rounded ends

        pill_bg = "#0d1117"
        pill_points = [
            x0 + r, y0, x1 - r, y0, x1, y0,
            x1, y0 + r, x1, y1 - r, x1, y1,
            x1 - r, y1, x0 + r, y1, x0, y1,
            x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        self.canvas.create_polygon(pill_points, smooth=True, fill=pill_bg, outline='')

        if hotkey_hint:
            # Two-line layout: state label + hotkey hint
            self.canvas.create_text(
                cx, pill_y_center - 4,
                text=label,
                fill=colors[0],
                font=("Segoe UI", 9, "bold"),
                anchor="center",
            )
            self.canvas.create_text(
                cx, pill_y_center + 6,
                text=hotkey_hint,
                fill="#475569",
                font=("Segoe UI", 6),
                anchor="center",
            )
        else:
            self.canvas.create_text(
                cx, pill_y_center,
                text=label,
                fill=colors[0],
                font=("Segoe UI", 9, "bold"),
                anchor="center",
            )

    def _draw_hover_ring(self, cx: float, cy: float, orb_r: float) -> None:
        """Subtle hover indicator: a single thin ring around the orb."""
        if not self.canvas or self._hover_alpha < 0.05:
            return
        colors = self._interpolate_state_colors()
        ring_r = orb_r + 3
        color = interpolate_color('#010203', colors[1], self._hover_alpha * 0.55)
        self.canvas.create_oval(cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                                outline=color, width=1)

    def _update_animations(self, level: float) -> None:
        """Advance all animation state variables by one frame."""
        self._animation_frame += 1
        self._update_state_transition()

        # ── Pulse scale ───────────────────────────────────────────────────
        if self._target_state == "recording":
            self._target_pulse_scale = 1.0 + level * 0.18
        elif self._target_state == "processing":
            self._target_pulse_scale = 1.0 + 0.06 * (math.sin(self._animation_frame * 0.12) + 1) / 2
        else:
            self._breathing_phase += 0.018
            self._target_pulse_scale = 1.0 + 0.04 * math.sin(self._breathing_phase)
        self._pulse_scale = lerp(self._pulse_scale, self._target_pulse_scale, 0.2)

        # ── Waveform data ─────────────────────────────────────────────────
        self._update_waveform(level)

        # ── Sonar rings (idle only) ───────────────────────────────────────
        if self._target_state == "idle":
            self._sonar_timer += 1
            if self._sonar_timer >= self._sonar_interval:
                self._sonar_timer = 0
                self._sonar_rings.append({'r': self.size * 0.20, 'alpha': 0.85})
        else:
            self._sonar_timer = 0

        for ring in self._sonar_rings:
            ring['r'] += self.size * 0.004
            ring['alpha'] -= 0.014
        self._sonar_rings = [r for r in self._sonar_rings if r['alpha'] > 0]

        # ── Processing orbit ──────────────────────────────────────────────
        if self._target_state == "processing":
            self._spinner_angle = (self._spinner_angle + 4.2) % 360.0
            self._arc_angle = (self._arc_angle + 5.5) % 360.0

        # ── Hover / ripple ────────────────────────────────────────────────
        if self._is_hovering:
            self._hover_alpha = min(1.0, self._hover_alpha + 0.1)
        else:
            self._hover_alpha = max(0.0, self._hover_alpha - 0.1)

        if self._ripple_active:
            self._ripple_radius += self.size / 35
            self._ripple_alpha -= 0.045
            if self._ripple_alpha <= 0:
                self._ripple_active = False

    def _draw(self, level: float) -> None:
        """Orchestrate the full frame render in layer order.

        Layer stack (bottom → top):
          1  Radial-gradient orb sphere (PIL image)
          2  State-specific outer decoration
               idle       → sonar-ping rings
               recording  → vibrating waveform edge
               processing → orbiting comet dots
          3  Click ripple
          4  Core disc (bright pulsing centre)
          5  State icon overlaid on core
               recording  → reactive frequency bars
               idle       → standby dot-trio
               processing → spinning arc
          6  Hover ring (subtle, only when hovering)
          7  Status pill
        """
        if not self.canvas:
            return

        self._update_animations(level)
        self.canvas.delete('all')

        cx = cy = self.size / 2
        orb_r    = self.size * 0.44   # orb fills nearly the whole allocated square
        wave_r   = self.size * 0.36   # waveform ring baseline
        orbit_r  = self.size * 0.30   # processing-dot orbit radius
        core_r   = self.size * 0.20   # bright inner disc

        # ── Layer 1: orb background ───────────────────────────────────────
        self._draw_orb_background(cx, cy)

        # ── Layer 2: state outer decoration ──────────────────────────────
        state = self._target_state
        if state == "idle":
            self._draw_sonar_pings(cx, cy)
        elif state == "recording":
            self._draw_waveform_edge(cx, cy, wave_r)
        elif state == "processing":
            self._draw_processing_orbit(cx, cy, orbit_r)

        # ── Layer 3: ripple ───────────────────────────────────────────────
        self._draw_ripple_effect(cx, cy)

        # ── Layer 4: core disc ────────────────────────────────────────────
        self._draw_core_disc(cx, cy, core_r)

        # ── Layer 5: centre icon ──────────────────────────────────────────
        if state == "recording":
            self._draw_center_bars(cx, cy, core_r)
        elif state == "idle":
            self._draw_center_dots(cx, cy, core_r)
        elif state == "processing":
            self._draw_center_arc(cx, cy, core_r)

        # ── Layer 6: hover ring ───────────────────────────────────────────
        self._draw_hover_ring(cx, cy, orb_r)

        # ── Layer 7: status pill ──────────────────────────────────────────
        self._draw_status_pill(cx)

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
        # Store absolute screen coordinates instead of widget-relative
        self._drag_start_pos = (e.x_root, e.y_root)
        if self.win:
            self._drag_start_window_pos = (self.win.winfo_x(), self.win.winfo_y())
        self._dragged = False

    def _on_left_drag(self, e: tk.Event) -> None:
        """Handle left button drag (move overlay)."""
        if not self.win:
            return
        
        # Calculate movement using absolute screen coordinates
        dx = e.x_root - self._drag_start_pos[0]
        dy = e.y_root - self._drag_start_pos[1]
        
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

    # ========================================================================
    # COMMAND TOAST & FEEDBACK UI
    # ========================================================================

    def show_command_toast(self, phrase: str, tool: str) -> None:
        """Show a pill-shaped notification after a command fires.

        Wider (280×44) than the old toast with a slide-in entrance animation.
        The 'Wrong?' action is rendered as a subtle underlined link rather than
        a red pill, reducing visual noise while keeping the affordance clear.
        Must be called on the main Tk thread.
        """
        if not self.root or not self.win:
            return

        self._dismiss_toast()
        self._toast_phrase = phrase
        self._toast_tool = tool

        display_name = _TOOL_DISPLAY_NAMES.get(tool, tool)
        pill_w, pill_h = 280, 44
        radius = 10

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#0d1117")
        try:
            toast.attributes("-transparentcolor", "#0d1117")
            toast.wm_attributes("-alpha", 0.95)
        except Exception:
            pass

        cv = tk.Canvas(
            toast, width=pill_w, height=pill_h,
            bg="#0d1117", highlightthickness=0, borderwidth=0,
        )
        cv.pack()

        def _rounded_pill(x0, y0, x1, y1, r, **kw):
            pts = [
                x0 + r, y0, x1 - r, y0, x1, y0,
                x1, y0 + r, x1, y1 - r, x1, y1,
                x1 - r, y1, x0 + r, y1, x0, y1,
                x0, y1 - r, x0, y0 + r, x0, y0,
            ]
            cv.create_polygon(pts, smooth=True, **kw)

        # Dark pill background with subtle border
        _rounded_pill(1, 1, pill_w - 1, pill_h - 1, radius, fill="#1e293b", outline="#334155", width=1)

        # Icon dot — accent colour circle on the left
        colors = self._interpolate_state_colors()
        cv.create_oval(12, pill_h // 2 - 4, 20, pill_h // 2 + 4, fill=colors[0], outline="")

        # Command label
        cv.create_text(
            28, pill_h // 2 - 5,
            text=display_name,
            fill="#f1f5f9",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        # "Heard:" sub-label
        cv.create_text(
            28, pill_h // 2 + 7,
            text=f'"{phrase[:30]}{"…" if len(phrase) > 30 else ""}"',
            fill="#64748b",
            font=("Segoe UI", 8),
            anchor="w",
        )

        # "Wrong?" as an underlined link (right-aligned)
        wrong_x = pill_w - 10
        wrong_id = cv.create_text(
            wrong_x, pill_h // 2,
            text="Wrong?",
            fill="#94a3b8",
            font=("Segoe UI", 8, "underline"),
            anchor="e",
        )

        def _on_click(event):
            bbox = cv.bbox(wrong_id)
            if bbox and bbox[0] <= event.x <= bbox[2]:
                self._show_correction_dialog(phrase, tool)
            self._dismiss_toast()

        def _on_motion(event):
            bbox = cv.bbox(wrong_id)
            if bbox and bbox[0] <= event.x <= bbox[2]:
                cv.itemconfigure(wrong_id, fill="#f1f5f9")
                cv.configure(cursor="hand2")
            else:
                cv.itemconfigure(wrong_id, fill="#94a3b8")
                cv.configure(cursor="")

        cv.bind("<Button-1>", _on_click)
        cv.bind("<Motion>", _on_motion)

        # Position to the right of the overlay, then slide in from +20px offset
        if self.win.winfo_exists():
            ox = self.win.winfo_x()
            oy = self.win.winfo_y()
            final_x = ox + self.size + 8
            final_y = oy + (self.size // 4)
            # Start offset to the right for the slide-in
            toast.geometry(f"+{final_x + 20}+{final_y}")
            toast.update_idletasks()

            def _slide_in(step: int = 0, steps: int = 8) -> None:
                if not toast.winfo_exists():
                    return
                progress = step / steps
                eased = 1 - (1 - progress) ** 2  # ease-out quad
                x = int(final_x + 20 * (1 - eased))
                toast.geometry(f"+{x}+{final_y}")
                if step < steps:
                    toast.after(18, lambda: _slide_in(step + 1, steps))

            toast.after(10, _slide_in)

        self._toast_win = toast
        self._toast_after_id = self.root.after(4000, self._dismiss_toast)

    def show_correction_dialog_for_last(self) -> None:
        """Open the correction dialog for the last command phrase.

        Called when the user says 'that was wrong' (voice feedback trigger).
        """
        self._dismiss_toast()
        if self._toast_phrase:
            self._show_correction_dialog(self._toast_phrase, self._toast_tool)

    def _dismiss_toast(self) -> None:
        """Destroy any active toast window."""
        if self._toast_after_id and self.root:
            try:
                self.root.after_cancel(self._toast_after_id)
            except Exception:
                pass
            self._toast_after_id = None
        if self._toast_win:
            try:
                if self._toast_win.winfo_exists():
                    self._toast_win.destroy()
            except Exception:
                pass
            self._toast_win = None

    def _show_correction_dialog(self, phrase: str, tool: str) -> None:
        """Open a modal dialog to let the user choose the correct command tool.

        Uses a scrollable Listbox of human-readable display names instead of a
        raw key combobox, so users see "New Line" rather than "NEW_LINE".
        The current tool is pre-selected.
        """
        self._dismiss_toast()

        if not self.root:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Correct Command")
        dlg.attributes("-topmost", True)
        dlg.configure(bg="#0f172a")
        dlg.resizable(False, False)

        pad = {"padx": 16, "pady": 6}

        tk.Label(
            dlg,
            text="You said:",
            fg="#64748b",
            bg="#0f172a",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, **pad)

        tk.Label(
            dlg,
            text=f'"{phrase}"',
            fg="#f1f5f9",
            bg="#0f172a",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            wraplength=340,
        ).pack(fill=tk.X, padx=16, pady=(0, 4))

        tk.Label(
            dlg,
            text=f"Triggered:  {_TOOL_DISPLAY_NAMES.get(tool, tool)}",
            fg="#f59e0b",
            bg="#0f172a",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, **pad)

        tk.Frame(dlg, bg="#334155", height=1).pack(fill=tk.X, padx=16, pady=4)

        tk.Label(
            dlg,
            text="What should it do instead?",
            fg="#94a3b8",
            bg="#0f172a",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, **pad)

        # Build ordered (key, display) pairs for the listbox
        _tool_keys = list(_TOOL_DISPLAY_NAMES.keys())
        _tool_labels = [_TOOL_DISPLAY_NAMES[k] for k in _tool_keys]

        listbox_frame = tk.Frame(dlg, bg="#0f172a")
        listbox_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, bg="#334155",
                                 troughcolor="#1e293b", relief=tk.FLAT)
        lb = tk.Listbox(
            listbox_frame,
            height=min(len(_tool_labels), 7),
            bg="#1e293b",
            fg="#f1f5f9",
            selectbackground="#7c3aed",
            selectforeground="#ffffff",
            activestyle="none",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#334155",
            font=("Segoe UI", 9),
            yscrollcommand=scrollbar.set,
            exportselection=False,
        )
        scrollbar.config(command=lb.yview)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for label in _tool_labels:
            lb.insert(tk.END, f"  {label}")

        # Pre-select the current tool
        try:
            current_idx = _tool_keys.index(tool)
            lb.selection_set(current_idx)
            lb.see(current_idx)
        except ValueError:
            pass

        btn_frame = tk.Frame(dlg, bg="#0f172a")
        btn_frame.pack(fill=tk.X, padx=16, pady=(4, 14))

        def _save() -> None:
            sel = lb.curselection()
            if not sel:
                return
            new_tool = _tool_keys[sel[0]]
            if self.on_correction_save and new_tool:
                self.on_correction_save(phrase, new_tool)
                self._toast_phrase = phrase
                self._toast_tool = new_tool
            dlg.destroy()

        tk.Button(
            btn_frame,
            text="Save & Learn",
            bg="#16a34a",
            fg="white",
            activebackground="#15803d",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=_save,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame,
            text="Cancel",
            bg="#334155",
            fg="#94a3b8",
            activebackground="#475569",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            command=dlg.destroy,
        ).pack(side=tk.LEFT)

        # Center on screen
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

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
