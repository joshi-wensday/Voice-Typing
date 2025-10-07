"""Draggable circular overlay visualizer showing audio level/VAD activity."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import Canvas
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


class Overlay:
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
        self._drag_start_pos = (0, 0)
        self._drag_start_window_pos = (0, 0)
        self._dragged = False
        self._running = False

        # Callbacks
        self.on_toggle: Optional[Callable[[], None]] = None
        self.on_settings: Optional[Callable[[], None]] = None

    def _build(self) -> None:
        assert self.win is not None
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", self.opacity)
        self.win.geometry(f"{self.size}x{self.size}+{self.position[0]}+{self.position[1]}")
        self.win.configure(bg="black")
        self.canvas = Canvas(self.win, width=self.size, height=self.size, bg="black", highlightthickness=0)
        self.canvas.pack()
        # Left-click: drag or toggle (depending on movement)
        self.canvas.bind('<ButtonPress-1>', self._on_left_press)
        self.canvas.bind('<B1-Motion>', self._on_left_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_left_release)
        # Right-click to open settings
        self.canvas.bind('<Button-3>', self._on_right_click)
        self._draw(0.0)

    def _draw(self, level: float) -> None:
        if not self.canvas:
            return
        self.canvas.delete('all')
        cx = cy = self.size / 2
        r = self.size / 3
        color = '#44ff44'
        # base circle
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=2)
        # radial spikes
        spikes = 36
        for i in range(spikes):
            ang = 2 * math.pi * i / spikes
            ext = level * (self.size / 6)
            x0 = cx + r * math.cos(ang)
            y0 = cy + r * math.sin(ang)
            x1 = cx + (r + ext) * math.cos(ang)
            y1 = cy + (r + ext) * math.sin(ang)
            self.canvas.create_line(x0, y0, x1, y1, fill=color, width=2)
        # center fill
        self.canvas.create_oval(cx - r / 3, cy - r / 3, cx + r / 3, cy + r / 3, fill=color, outline='')

    def _tick(self) -> None:
        if not self._running or self.win is None:
            return
        lvl = max(0.0, min(1.0, float(self.get_level())))
        self._draw(lvl)
        self.win.after(50, self._tick)

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
            # Click (no drag) - toggle
            if self.on_toggle:
                self.on_toggle()

    def show(self) -> None:
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
        self._running = False
        if self.win:
            self.win.withdraw()
