"""Interactive hotkey capture widget for settings."""

from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable, Set
from .effects import ColorTheme


class HotkeyCapture(tk.Frame):
    """Custom widget for capturing keyboard shortcuts interactively.
    
    Features:
    - Click to enter capture mode
    - Real-time display of pressed keys
    - Visual feedback when capturing
    - Confirm/cancel buttons
    - Validation of key combinations
    """
    
    # Valid modifier keys
    MODIFIERS = {'ctrl', 'alt', 'shift', 'win', 'cmd'}
    
    # Keys that should have a modifier
    REQUIRES_MODIFIER = set('abcdefghijklmnopqrstuvwxyz0123456789')
    
    def __init__(self, parent, textvariable=None, width=30, on_change: Optional[Callable] = None):
        super().__init__(parent, bg=ColorTheme.BG_DARK)
        
        self.textvariable = textvariable or tk.StringVar()
        self.width = width
        self.on_change = on_change
        
        # Capture state
        self._capturing = False
        self._current_keys: Set[str] = set()
        self._captured_combo = ""
        
        # Main container
        self.container = tk.Frame(self, bg=ColorTheme.BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Display canvas
        self.canvas = tk.Canvas(
            self.container,
            height=32,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Buttons (hidden initially)
        self.button_frame = tk.Frame(self.container, bg=ColorTheme.BG_DARK)
        self.button_frame.pack(side=tk.LEFT, padx=(5, 0))
        
        # Confirm button
        self.confirm_btn = tk.Canvas(
            self.button_frame,
            width=24,
            height=24,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
            cursor="hand2"
        )
        self.confirm_btn.pack(side=tk.LEFT, padx=2)
        self._draw_checkmark()
        self.confirm_btn.bind('<Button-1>', self._on_confirm)
        
        # Cancel button
        self.cancel_btn = tk.Canvas(
            self.button_frame,
            width=24,
            height=24,
            bg=ColorTheme.BG_DARK,
            highlightthickness=0,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=2)
        self._draw_x()
        self.cancel_btn.bind('<Button-1>', self._on_cancel)
        
        # Hide buttons initially
        self.button_frame.pack_forget()
        
        # Bind events
        self.canvas.bind('<Button-1>', self._on_click)
        
        # Draw initial state
        self._draw()
    
    def _draw_checkmark(self):
        """Draw checkmark icon."""
        self.confirm_btn.delete('all')
        # Draw circle background
        self.confirm_btn.create_oval(
            2, 2, 22, 22,
            fill=ColorTheme.ACCENT_SUCCESS,
            outline=''
        )
        # Draw checkmark
        self.confirm_btn.create_line(
            7, 12, 10, 16, 16, 8,
            fill='white',
            width=2,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
    
    def _draw_x(self):
        """Draw X icon."""
        self.cancel_btn.delete('all')
        # Draw circle background
        self.cancel_btn.create_oval(
            2, 2, 22, 22,
            fill=ColorTheme.BORDER,
            outline=''
        )
        # Draw X
        self.cancel_btn.create_line(
            8, 8, 16, 16,
            fill='white',
            width=2,
            capstyle=tk.ROUND
        )
        self.cancel_btn.create_line(
            16, 8, 8, 16,
            fill='white',
            width=2,
            capstyle=tk.ROUND
        )
    
    def _draw(self):
        """Draw the hotkey display."""
        self.canvas.delete('all')
        
        w = self.canvas.winfo_reqwidth() or (self.width * 7)
        h = 32
        
        # Background color based on state
        if self._capturing:
            bg_color = ColorTheme.BORDER_LIGHT
            border_color = ColorTheme.ACCENT_PRIMARY
        else:
            bg_color = ColorTheme.BG_CARD
            border_color = ColorTheme.BORDER
        
        # Draw rounded rectangle background
        self._create_rounded_rect(
            self.canvas, 0, 0, w, h,
            radius=6,
            fill=bg_color,
            outline=border_color,
            width=2 if self._capturing else 1
        )
        
        # Draw text
        if self._capturing:
            if self._current_keys:
                text = self._format_keys(self._current_keys)
            else:
                text = "Press keys..."
            text_color = ColorTheme.TEXT_PRIMARY
        else:
            text = self.textvariable.get() or "Click to set hotkey"
            text_color = ColorTheme.TEXT_SECONDARY if not self.textvariable.get() else ColorTheme.TEXT_PRIMARY
        
        self.canvas.create_text(
            10, h // 2,
            text=text,
            fill=text_color,
            font=('Segoe UI', 10),
            anchor=tk.W
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
    
    def _format_keys(self, keys: Set[str]) -> str:
        """Format key set as display string."""
        # Order: ctrl, alt, shift, win, others
        order = ['ctrl', 'alt', 'shift', 'win', 'cmd']
        formatted = []
        
        for mod in order:
            if mod in keys:
                formatted.append(mod.capitalize())
        
        # Add other keys
        others = sorted(keys - set(order))
        for key in others:
            formatted.append(key.capitalize())
        
        return ' + '.join(formatted)
    
    def _on_click(self, event):
        """Handle click to start capture."""
        if not self._capturing:
            self._start_capture()
    
    def _start_capture(self):
        """Start capturing hotkey."""
        self._capturing = True
        self._current_keys.clear()
        self._captured_combo = ""
        
        # Show buttons
        self.button_frame.pack(side=tk.LEFT, padx=(5, 0))
        
        # Bind keyboard events
        self.canvas.focus_set()
        self.canvas.bind('<KeyPress>', self._on_key_press)
        self.canvas.bind('<KeyRelease>', self._on_key_release)
        self.canvas.bind('<FocusOut>', self._on_focus_out)
        
        self._draw()
    
    def _stop_capture(self):
        """Stop capturing hotkey."""
        self._capturing = False
        self._current_keys.clear()
        
        # Hide buttons
        self.button_frame.pack_forget()
        
        # Unbind keyboard events
        self.canvas.unbind('<KeyPress>')
        self.canvas.unbind('<KeyRelease>')
        self.canvas.unbind('<FocusOut>')
        
        self._draw()
    
    def _on_key_press(self, event):
        """Handle key press during capture."""
        if not self._capturing:
            return
        
        # Normalize key name
        key = event.keysym.lower()
        
        # Map special keys
        key_map = {
            'control_l': 'ctrl',
            'control_r': 'ctrl',
            'alt_l': 'alt',
            'alt_r': 'alt',
            'shift_l': 'shift',
            'shift_r': 'shift',
            'win_l': 'win',
            'win_r': 'win',
            'super_l': 'win',
            'super_r': 'win',
            'command': 'cmd',
        }
        
        key = key_map.get(key, key)
        
        # Add to current keys
        self._current_keys.add(key)
        
        self._draw()
    
    def _on_key_release(self, event):
        """Handle key release during capture."""
        # Don't remove keys - wait for confirm/cancel
        pass
    
    def _on_focus_out(self, event):
        """Handle focus loss - cancel capture."""
        if self._capturing:
            self._on_cancel()
    
    def _validate_combo(self, keys: Set[str]) -> tuple[bool, str]:
        """Validate a key combination.
        
        Returns:
            (is_valid, error_message)
        """
        if not keys:
            return False, "No keys captured"
        
        # Check if single key without modifier
        if len(keys) == 1:
            key = list(keys)[0]
            if key not in self.MODIFIERS and key.lower() in self.REQUIRES_MODIFIER:
                return False, "Single letter/number requires a modifier (Ctrl, Alt, or Shift)"
        
        # Check if only modifiers
        if all(k in self.MODIFIERS for k in keys):
            return False, "Must include at least one non-modifier key"
        
        # Check for valid combination
        non_modifiers = [k for k in keys if k not in self.MODIFIERS]
        if len(non_modifiers) > 1:
            return False, "Can only have one non-modifier key"
        
        return True, ""
    
    def _on_confirm(self, event=None):
        """Confirm the captured hotkey."""
        if not self._capturing:
            return
        
        # Validate
        is_valid, error_msg = self._validate_combo(self._current_keys)
        
        if not is_valid:
            # Show error (could use tooltip or message)
            import tkinter.messagebox as mb
            mb.showwarning("Invalid Hotkey", error_msg)
            return
        
        # Format and save
        combo = self._format_keys(self._current_keys)
        combo_lower = '+'.join(sorted(k.lower() for k in self._current_keys))
        
        self.textvariable.set(combo_lower)
        self._captured_combo = combo_lower
        
        # Callback
        if self.on_change:
            self.on_change(combo_lower)
        
        self._stop_capture()
    
    def _on_cancel(self, event=None):
        """Cancel hotkey capture."""
        self._stop_capture()
    
    def get(self):
        """Get current hotkey value."""
        return self.textvariable.get()
    
    def set(self, value):
        """Set hotkey value."""
        self.textvariable.set(value)
        self._draw()

