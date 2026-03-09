"""Modern settings window with sidebar navigation and card-based layout."""

from __future__ import annotations

import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, Any
from PIL import Image, ImageDraw, ImageTk

from ..config.manager import ConfigManager
from ..audio.capture import AudioCapture
from ..stt.model_manager import ModelManager
from ..stt.model_tester import ModelTester
from .effects import ColorTheme, create_card_frame, ease_out_sine, interpolate_color
from .hotkey_capture import HotkeyCapture


# ---------------------------------------------------------------------------
# Reusable widget components
# ---------------------------------------------------------------------------

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

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self._draw()

    def _draw(self):
        self.delete('all')
        w, h = self.width, self.height
        if self.primary:
            if self._is_pressed:
                bg_color = '#6366f1'
            elif self._is_hovering:
                bg_color = '#8b5cf6'
            else:
                bg_color = '#7c3aed'
        else:
            if self._is_pressed:
                bg_color = ColorTheme.BG_CARD_RAISED
            elif self._is_hovering:
                bg_color = ColorTheme.BORDER_LIGHT
            else:
                bg_color = ColorTheme.BORDER
        self._create_rounded_rect(2, 2, w - 2, h - 2, radius=8, fill=bg_color, outline='')
        self.create_text(
            w // 2, h // 2,
            text=self.text,
            fill=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 10, 'normal'),
        )

    def _create_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_enter(self, _e):
        self._is_hovering = True
        self._draw()

    def _on_leave(self, _e):
        self._is_hovering = False
        self._draw()

    def _on_press(self, _e):
        self._is_pressed = True
        self._draw()

    def _on_release(self, _e):
        self._is_pressed = False
        self._draw()
        if self._is_hovering and self.command:
            self.command()


class ModernEntry(tk.Frame):
    """Custom modern entry field with rounded corners and styling."""

    def __init__(self, parent, textvariable=None, width=30, **kwargs):
        super().__init__(parent, bg=ColorTheme.BG_CARD_RAISED)
        self.canvas = tk.Canvas(self, height=32, bg=ColorTheme.BG_CARD_RAISED, highlightthickness=0)
        self.canvas.pack(fill=tk.X, expand=True)
        self._draw_background()
        self.entry = tk.Entry(
            self.canvas,
            textvariable=textvariable,
            bg=ColorTheme.BG_CARD,
            fg=ColorTheme.TEXT_PRIMARY,
            insertbackground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT,
            font=('Segoe UI', 10),
            width=width,
            **kwargs,
        )
        self.canvas.create_window(4, 16, anchor=tk.W, window=self.entry)
        self.entry.bind('<FocusIn>', lambda _e: self._on_focus(True))
        self.entry.bind('<FocusOut>', lambda _e: self._on_focus(False))

    def _draw_background(self, focused=False):
        self.canvas.delete('background')
        border_color = ColorTheme.ACCENT_PRIMARY if focused else ColorTheme.CARD_BORDER
        w = self.canvas.winfo_reqwidth() or 200
        self._create_rounded_rect(
            self.canvas, 0, 0, w, 32,
            radius=6, fill=ColorTheme.BG_CARD, outline=border_color,
            width=1, tags='background',
        )
        self.canvas.tag_lower('background')

    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius=10, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _on_focus(self, has_focus):
        self._draw_background(has_focus)

    def get(self):
        return self.entry.get()


class ColorPicker(tk.Frame):
    """Simple color picker with preview and hex input."""

    def __init__(self, parent, textvariable=None, width=20):
        super().__init__(parent, bg=ColorTheme.BG_CARD_RAISED)
        self.textvariable = textvariable or tk.StringVar()
        self.width = width
        self.preview_canvas = tk.Canvas(
            self, width=32, height=32,
            bg=ColorTheme.BG_CARD,
            highlightthickness=1,
            highlightbackground=ColorTheme.CARD_BORDER,
            cursor='hand2',
        )
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.preview_canvas.bind('<Button-1>', self._open_color_picker)
        self.entry = ModernEntry(self, textvariable=self.textvariable, width=width)
        self.entry.pack(side=tk.LEFT)
        self.textvariable.trace_add('write', lambda *_: self._update_preview())
        self._update_preview()

    def _update_preview(self):
        color = self.textvariable.get()
        try:
            if color.startswith('#') and len(color) == 7:
                self.preview_canvas.configure(bg=color)
            else:
                self.preview_canvas.configure(bg=ColorTheme.BG_CARD)
        except Exception:
            self.preview_canvas.configure(bg=ColorTheme.BG_CARD)

    def _open_color_picker(self, _event=None):
        from tkinter import colorchooser
        current_color = self.textvariable.get()
        parent_window = self.winfo_toplevel()
        was_topmost = False
        try:
            was_topmost = parent_window.attributes('-topmost')
            if was_topmost:
                parent_window.attributes('-topmost', False)
        except Exception:
            pass
        color = colorchooser.askcolor(color=current_color, title="Choose Color", parent=parent_window)
        try:
            if was_topmost:
                parent_window.attributes('-topmost', True)
        except Exception:
            pass
        if color and color[1]:
            self.textvariable.set(color[1])

    def get(self):
        return self.textvariable.get()


class ModernSlider(tk.Frame):
    """Custom modern slider with value display."""

    def __init__(self, parent, variable=None, from_=0.0, to=1.0, resolution=0.01, width=200):
        super().__init__(parent, bg=ColorTheme.BG_CARD_RAISED)
        self.variable = variable or tk.DoubleVar()
        self.scale = tk.Scale(
            self,
            from_=from_, to=to, resolution=resolution,
            orient=tk.HORIZONTAL, variable=self.variable,
            bg=ColorTheme.BG_CARD_RAISED, fg=ColorTheme.TEXT_PRIMARY,
            troughcolor=ColorTheme.BORDER, highlightthickness=0,
            length=width, width=18, sliderrelief=tk.FLAT,
            activebackground=ColorTheme.ACCENT_PRIMARY,
        )
        self.scale.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(
            self, textvariable=self.variable,
            bg=ColorTheme.BG_CARD_RAISED, fg=ColorTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9), width=6,
        ).pack(side=tk.LEFT)

    def get(self):
        return self.variable.get()


# ---------------------------------------------------------------------------
# SettingsWindow — sidebar + card layout
# ---------------------------------------------------------------------------

class SettingsWindow:
    """Settings window with sidebar navigation and card-based panel layout.

    Layout (780×660):
        ┌──────────────────────────────────────┐
        │ Sidebar (180) │ Content area (580)   │
        │               │  [scrollable cards]  │
        ├───────────────┴──────────────────────┤
        │  Footer: status badge  [Reset] [Save]│
        └──────────────────────────────────────┘
    """

    _NAV_ITEMS = [
        ("🎙", "General"),
        ("🔊", "Speech"),
        ("🎚", "Audio"),
        ("⌨", "Commands"),
        ("🧠", "Brain / AI"),
        ("🎨", "Appearance"),
        ("⚙", "Advanced"),
        ("📦", "Models"),
    ]

    def __init__(self, cfgm: ConfigManager, root: Optional[tk.Tk] = None) -> None:
        self.cfgm = cfgm
        self.root: Optional[tk.Tk] = root
        self.win: Optional[tk.Toplevel] = None

        self._fade_alpha = 0.0
        self._active_panel: int = 0
        self._panels: dict[str, tk.Frame] = {}
        self._nav_buttons: list[tk.Canvas] = []

        self.model_manager = ModelManager()
        self.model_tester = ModelTester()
        self._original_config = None

        # Footer status label (created in _build_footer)
        self._status_label: Optional[tk.Label] = None
        self._status_after_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Window-level helpers
    # ------------------------------------------------------------------

    def _apply_dark_titlebar(self) -> None:
        try:
            import ctypes
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            self.win.update()
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

    def _setup_modern_style(self) -> None:
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Modern.TFrame', background=ColorTheme.BG_DARK)
        style.configure(
            'Modern.Vertical.TScrollbar',
            background=ColorTheme.BG_CARD,
            troughcolor=ColorTheme.BG_DARKER,
            borderwidth=0, arrowsize=12, width=10,
        )
        style.map(
            'Modern.Vertical.TScrollbar',
            background=[('active', ColorTheme.ACCENT_PRIMARY), ('!active', ColorTheme.BG_CARD)],
        )
        style.configure(
            'Modern.TCombobox',
            fieldbackground=ColorTheme.BG_CARD,
            background=ColorTheme.BG_CARD,
            foreground=ColorTheme.TEXT_PRIMARY,
            arrowcolor=ColorTheme.TEXT_PRIMARY,
            borderwidth=1, relief=tk.FLAT,
        )
        style.configure(
            'Modern.TCheckbutton',
            background=ColorTheme.BG_CARD_RAISED,
            foreground=ColorTheme.TEXT_PRIMARY,
            font=('Segoe UI', 10),
        )
        style.map(
            'Modern.TCheckbutton',
            background=[('active', ColorTheme.BG_CARD_RAISED)],
            foreground=[('active', ColorTheme.ACCENT_PRIMARY)],
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        assert self.win is not None

        self.win.title("Vype Settings")
        self.win.geometry("780x660+200+150")
        self.win.configure(bg=ColorTheme.BG_DARK)
        self.win.resizable(False, False)

        try:
            self.win.attributes('-alpha', self.cfgm.config.ui.settings_window_opacity)
        except Exception:
            pass

        self._apply_dark_titlebar()
        self._setup_modern_style()

        # ── Outer shell: sidebar + content stacked above footer ──────────
        outer = tk.Frame(self.win, bg=ColorTheme.BG_DARK)
        outer.pack(fill=tk.BOTH, expand=True)

        # Sidebar (fixed 180px)
        self._sidebar_frame = tk.Frame(outer, bg=ColorTheme.BG_SIDEBAR, width=180)
        self._sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar_frame.pack_propagate(False)
        self._build_sidebar()

        # Thin separator between sidebar and content
        tk.Frame(outer, bg=ColorTheme.BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Content area
        content_outer = tk.Frame(outer, bg=ColorTheme.BG_DARK)
        content_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._content_canvas = tk.Canvas(
            content_outer, bg=ColorTheme.BG_DARK, highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            content_outer, orient="vertical",
            command=self._content_canvas.yview,
            style='Modern.Vertical.TScrollbar',
        )
        self._content_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._content_frame = tk.Frame(self._content_canvas, bg=ColorTheme.BG_DARK)
        self._content_canvas.create_window((0, 0), window=self._content_frame, anchor="nw")

        self._content_frame.bind("<Configure>", self._on_content_configure)
        self._content_canvas.bind("<Configure>", self._on_canvas_configure)
        self._content_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # ── Footer (full width, below the sidebar+content pair) ──────────
        self._build_footer()

        # Build all panels (hidden initially)
        self._build_panels()

        # Show first panel
        self._show_panel(0)

        self._animate_fade_in()

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _on_content_configure(self, _e) -> None:
        self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._content_canvas.itemconfig(
            self._content_canvas.find_all()[0] if self._content_canvas.find_all() else 1,
            width=e.width,
        )

    def _on_mousewheel(self, e) -> None:
        if self.win and self.win.winfo_exists():
            self._content_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> None:
        # Logo / app name header
        header = tk.Frame(self._sidebar_frame, bg=ColorTheme.BG_SIDEBAR, height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="Vype", bg=ColorTheme.BG_SIDEBAR,
            fg=ColorTheme.TEXT_PRIMARY, font=("Segoe UI", 14, "bold"),
        ).place(x=20, y=20)
        tk.Label(
            header, text="Settings", bg=ColorTheme.BG_SIDEBAR,
            fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9),
        ).place(x=20, y=42)

        # Divider
        tk.Frame(self._sidebar_frame, bg=ColorTheme.BORDER, height=1).pack(fill=tk.X)

        # Nav items
        self._nav_buttons = []
        for idx, (icon, label) in enumerate(self._NAV_ITEMS):
            btn = self._make_nav_item(self._sidebar_frame, icon, label, idx)
            btn.pack(fill=tk.X)
            self._nav_buttons.append(btn)

    def _make_nav_item(self, parent, icon: str, label: str, idx: int) -> tk.Canvas:
        item = tk.Canvas(
            parent, bg=ColorTheme.BG_SIDEBAR, height=46,
            highlightthickness=0, cursor="hand2",
        )

        def _redraw(active: bool = False, hover: bool = False) -> None:
            item.delete("all")
            w = 180
            if active:
                item.create_rectangle(0, 0, 4, 46, fill=ColorTheme.ACTIVE_NAV, outline="")
                item.create_rectangle(4, 0, w, 46, fill="#1d2b3f", outline="")
                icon_fill = ColorTheme.ACCENT_PRIMARY
                text_fill = ColorTheme.TEXT_PRIMARY
            elif hover:
                item.create_rectangle(0, 0, w, 46, fill="#182030", outline="")
                icon_fill = ColorTheme.TEXT_SECONDARY
                text_fill = ColorTheme.TEXT_PRIMARY
            else:
                icon_fill = ColorTheme.TEXT_DISABLED
                text_fill = ColorTheme.TEXT_SECONDARY
            item.create_text(20, 23, text=icon, fill=icon_fill,
                             font=("Segoe UI", 13), anchor="w")
            item.create_text(46, 23, text=label, fill=text_fill,
                             font=("Segoe UI", 10), anchor="w")

        _redraw(active=(idx == 0))
        item._redraw = _redraw  # type: ignore[attr-defined]

        def _enter(_e) -> None:
            if idx != self._active_panel:
                _redraw(hover=True)

        def _leave(_e) -> None:
            if idx != self._active_panel:
                _redraw()

        def _click(_e) -> None:
            self._show_panel(idx)

        item.bind("<Enter>", _enter)
        item.bind("<Leave>", _leave)
        item.bind("<Button-1>", _click)
        return item

    def _show_panel(self, idx: int) -> None:
        self._active_panel = idx
        for i, btn in enumerate(self._nav_buttons):
            btn._redraw(active=(i == idx))  # type: ignore[attr-defined]
        for frame in self._panels.values():
            frame.pack_forget()
        name = self._NAV_ITEMS[idx][1]
        if name in self._panels:
            self._panels[name].pack(fill=tk.BOTH, expand=True)
        self._content_canvas.yview_moveto(0)

    # ------------------------------------------------------------------
    # Panel bootstrap
    # ------------------------------------------------------------------

    def _build_panels(self) -> None:
        for _, name in self._NAV_ITEMS:
            panel = tk.Frame(self._content_frame, bg=ColorTheme.BG_DARK)
            self._panels[name] = panel

        self._build_general_panel(self._panels["General"])
        self._build_speech_panel(self._panels["Speech"])
        self._build_audio_panel(self._panels["Audio"])
        self._build_commands_panel(self._panels["Commands"])
        self._build_brain_panel(self._panels["Brain / AI"])
        self._build_appearance_panel(self._panels["Appearance"])
        self._build_advanced_panel(self._panels["Advanced"])
        self._build_models_panel(self._panels["Models"])

    # ------------------------------------------------------------------
    # Card / row helpers
    # ------------------------------------------------------------------

    def _panel_header(self, parent: tk.Frame, title: str, subtitle: str = "") -> None:
        """Render a panel title + optional subtitle at the top."""
        hdr = tk.Frame(parent, bg=ColorTheme.BG_DARK)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 4))
        tk.Label(
            hdr, text=title, bg=ColorTheme.BG_DARK,
            fg=ColorTheme.TEXT_PRIMARY, font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                hdr, text=subtitle, bg=ColorTheme.BG_DARK,
                fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9),
            ).pack(anchor="w", pady=(2, 0))

    def _make_card(self, parent: tk.Frame, title: str = "", description: str = "") -> tk.Frame:
        """Create a raised card.  Returns the body Frame for placing widgets."""
        card = tk.Frame(
            parent, bg=ColorTheme.BG_CARD_RAISED, bd=0,
            highlightthickness=1, highlightbackground=ColorTheme.CARD_BORDER,
        )
        card.pack(fill=tk.X, padx=20, pady=6)

        if title:
            hdr = tk.Frame(card, bg=ColorTheme.BG_CARD_RAISED)
            hdr.pack(fill=tk.X, padx=16, pady=(10, 0))
            tk.Label(
                hdr, text=title, bg=ColorTheme.BG_CARD_RAISED,
                fg=ColorTheme.TEXT_PRIMARY, font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w")
            if description:
                tk.Label(
                    hdr, text=description, bg=ColorTheme.BG_CARD_RAISED,
                    fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9),
                    wraplength=480, justify="left",
                ).pack(anchor="w", pady=(2, 0))
            tk.Frame(card, bg=ColorTheme.CARD_BORDER, height=1).pack(fill=tk.X, padx=16, pady=(8, 0))

        body = tk.Frame(card, bg=ColorTheme.BG_CARD_RAISED)
        body.pack(fill=tk.X, padx=16, pady=(8, 14))
        return body

    def _card_row(
        self, parent: tk.Frame, label: str, help_text: str = "",
    ) -> tk.Frame:
        """Create a two-column label + widget row.  Returns the right-side frame."""
        row = tk.Frame(parent, bg=ColorTheme.BG_CARD_RAISED)
        row.pack(fill=tk.X, pady=5)

        lbl_col = tk.Frame(row, bg=ColorTheme.BG_CARD_RAISED, width=190)
        lbl_col.pack(side=tk.LEFT)
        lbl_col.pack_propagate(False)
        tk.Label(
            lbl_col, text=label, bg=ColorTheme.BG_CARD_RAISED,
            fg=ColorTheme.TEXT_PRIMARY, font=("Segoe UI", 10), anchor="w",
        ).pack(anchor="w")
        if help_text:
            tk.Label(
                lbl_col, text=help_text, bg=ColorTheme.BG_CARD_RAISED,
                fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 8),
                wraplength=165, anchor="w", justify="left",
            ).pack(anchor="w")

        widget_col = tk.Frame(row, bg=ColorTheme.BG_CARD_RAISED)
        widget_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return widget_col

    def _make_combobox(
        self, parent, textvariable=None, values=None, width: int = 24,
    ) -> ttk.Combobox:
        combo = ttk.Combobox(
            parent, textvariable=textvariable,
            values=values or [], state="readonly",
            width=width, font=('Segoe UI', 10),
            style='Modern.TCombobox',
        )
        return combo

    def _make_checkbutton(self, parent, text: str, variable) -> ttk.Checkbutton:
        return ttk.Checkbutton(
            parent, text=text, variable=variable,
            style='Modern.TCheckbutton',
        )

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def _build_general_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "General", "Hotkey binding and startup behaviour")

        # ── Hotkey card ────────────────────────────────────────────────
        body = self._make_card(panel, "Push-to-Talk Hotkey",
                               "Click the field then press your desired key combination.")
        wc = self._card_row(body, "Hotkey", "Global shortcut to start/stop dictation")
        self.var_hotkey = tk.StringVar(master=self.win, value=self.cfgm.config.ui.hotkey)
        HotkeyCapture(wc, textvariable=self.var_hotkey, width=22).pack(anchor="w")

        # ── Startup card ───────────────────────────────────────────────
        body2 = self._make_card(panel, "Startup & Tray")
        self.var_start_minimized = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.ui.start_minimized,
        )
        self._make_checkbutton(
            body2, "Start minimised to tray", self.var_start_minimized,
        ).pack(anchor="w", pady=3)

        self.var_close_to_tray = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.ui.close_to_tray,
        )
        self._make_checkbutton(
            body2, "Closing window sends app to tray (don't quit)", self.var_close_to_tray,
        ).pack(anchor="w", pady=3)

    def _build_speech_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Speech", "Speech-to-text model and compute settings")

        # ── Model card ─────────────────────────────────────────────────
        body = self._make_card(
            panel, "STT Model",
            "Larger models are more accurate but slower. Restart required after changes.",
        )
        # Backend selector (controls which options are shown)
        inferred_backend = "nemo" if str(self.cfgm.config.stt.model) == "canary-qwen-2.5b" else "whisper"
        cfg_backend = getattr(self.cfgm.config.stt, "backend", inferred_backend)

        wc0 = self._card_row(body, "Backend", "Whisper (faster-whisper) or NeMo (Canary)")
        self.var_backend = tk.StringVar(master=self.win, value=str(cfg_backend))
        self.backend_combo = self._make_combobox(
            wc0, textvariable=self.var_backend, values=["whisper", "nemo"], width=20
        )
        self.backend_combo.pack(anchor="w")

        wc = self._card_row(body, "Model", "Options depend on backend")
        self.var_model = tk.StringVar(master=self.win, value=self.cfgm.config.stt.model)
        self.model_combo = self._make_combobox(wc, textvariable=self.var_model, values=[], width=20)
        self.model_combo.pack(anchor="w")

        wc2 = self._card_row(body, "Device", "Restart required")
        self.var_device = tk.StringVar(master=self.win, value=self.cfgm.config.stt.device)
        self._make_combobox(
            wc2, textvariable=self.var_device,
            values=["auto", "cpu", "cuda"], width=20,
        ).pack(anchor="w")

        wc3 = self._card_row(body, "Compute Type",
                              "int8_float16 is fastest on CUDA")
        self.var_compute = tk.StringVar(master=self.win, value=self.cfgm.config.stt.compute_type)
        self._make_combobox(
            wc3, textvariable=self.var_compute,
            values=["float16", "float32", "int8", "int8_float16"], width=20,
        ).pack(anchor="w")

        wc4 = self._card_row(body, "Language", "e.g. en, fr, de — leave blank for auto")
        self.var_language = tk.StringVar(
            master=self.win, value=getattr(self.cfgm.config.stt, 'language', 'en'),
        )
        ModernEntry(wc4, textvariable=self.var_language, width=10).pack(anchor="w")

        # Keep row handles so we can hide/show based on backend choice
        self._stt_row_model = wc.master
        self._stt_row_compute = wc3.master
        self._stt_row_language = wc4.master

        def _sync_backend_ui(*_args) -> None:
            backend = (self.var_backend.get() or "whisper").strip().lower()

            if backend == "nemo":
                # NeMo backend currently exposes Canary only in this app.
                self.model_combo.configure(values=["canary-qwen-2.5b"])
                if self.var_model.get().strip().lower() != "canary-qwen-2.5b":
                    self.var_model.set("canary-qwen-2.5b")

                # Hide Whisper-only compute_type for NeMo
                self._stt_row_compute.pack_forget()

                # Canary is English-only; keep the field but nudge towards "en"
                if not self.var_language.get().strip():
                    self.var_language.set("en")
            else:
                # Whisper backend
                self.model_combo.configure(values=["tiny", "base", "small", "medium", "large-v2", "large-v3"])
                if self.var_model.get().strip().lower() == "canary-qwen-2.5b":
                    self.var_model.set("large-v3")

                # Ensure compute_type row is visible (pack again in original order)
                if not self._stt_row_compute.winfo_ismapped():
                    self._stt_row_compute.pack(fill=tk.X, pady=5)

        def _sync_backend_from_model(*_args) -> None:
            model = (self.var_model.get() or "").strip().lower()
            if model == "canary-qwen-2.5b":
                if (self.var_backend.get() or "").strip().lower() != "nemo":
                    self.var_backend.set("nemo")
            else:
                if (self.var_backend.get() or "").strip().lower() == "nemo":
                    # If user flips model away from canary, keep backend as-is (they may want NeMo later).
                    pass

        self.var_backend.trace_add("write", _sync_backend_ui)
        self.var_model.trace_add("write", _sync_backend_from_model)
        _sync_backend_ui()

        # ── Post-processing card ────────────────────────────────────────
        body2 = self._make_card(
            panel, "Post-Processing",
            "Requires the Brain / AI module (Ollama) to be enabled.",
        )
        self.var_remove_fillers = tk.BooleanVar(
            master=self.win,
            value=getattr(self.cfgm.config.stt, 'remove_filler_words', False),
        )
        self._make_checkbutton(
            body2, "Remove filler words (um, uh, like…)", self.var_remove_fillers,
        ).pack(anchor="w", pady=3)

        self.var_improve_grammar = tk.BooleanVar(
            master=self.win,
            value=getattr(self.cfgm.config.stt, 'improve_grammar', False),
        )
        self._make_checkbutton(
            body2, "Improve grammar with context-aware corrections",
            self.var_improve_grammar,
        ).pack(anchor="w", pady=3)

    def _build_audio_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Audio", "Microphone and voice-activity detection")

        # ── Input device card ──────────────────────────────────────────
        body = self._make_card(panel, "Input Device")
        devices = AudioCapture().list_devices()
        device_names = [f"{d['id']}: {d['name']}" for d in devices]
        device_id_val = (
            "default" if self.cfgm.config.audio.device_id is None
            else str(self.cfgm.config.audio.device_id)
        )
        self.var_device_id = tk.StringVar(master=self.win, value=device_id_val)
        wc = self._card_row(body, "Microphone")
        self._make_combobox(
            wc, textvariable=self.var_device_id,
            values=["default"] + device_names, width=34,
        ).pack(anchor="w")

        wc2 = self._card_row(body, "Sample Rate", "16000 Hz recommended for Whisper")
        self.var_sr = tk.IntVar(master=self.win, value=self.cfgm.config.audio.sample_rate)
        ModernEntry(wc2, textvariable=self.var_sr, width=10).pack(anchor="w")

        # ── VAD card ───────────────────────────────────────────────────
        body2 = self._make_card(
            panel, "Voice Activity Detection",
            "Controls how Vype decides when you start and stop speaking.",
        )
        wc3 = self._card_row(body2, "VAD Method")
        self.var_vad_method = tk.StringVar(
            master=self.win, value=self.cfgm.config.vad.method,
        )
        self._make_combobox(
            wc3, textvariable=self.var_vad_method,
            values=["silero", "energy"], width=16,
        ).pack(anchor="w")

        wc4 = self._card_row(body2, "Speech Threshold",
                              "0.0–1.0; higher = less sensitive")
        self.var_vad_threshold = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.vad.threshold,
        )
        ModernSlider(wc4, variable=self.var_vad_threshold,
                     from_=0.0, to=1.0, resolution=0.05, width=160).pack(anchor="w")

        wc5 = self._card_row(body2, "Min Speech (ms)",
                              "Minimum speech duration to count as a segment")
        self.var_vad_min_speech = tk.IntVar(
            master=self.win, value=self.cfgm.config.vad.min_speech_duration_ms,
        )
        ModernEntry(wc5, textvariable=self.var_vad_min_speech, width=8).pack(anchor="w")

        wc6 = self._card_row(body2, "Min Silence (ms)",
                              "Silence duration that ends a segment")
        self.var_vad_min_silence = tk.IntVar(
            master=self.win, value=self.cfgm.config.vad.min_silence_duration_ms,
        )
        ModernEntry(wc6, textvariable=self.var_vad_min_silence, width=8).pack(anchor="w")

    def _build_commands_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Commands",
                           "Voice commands and punctuation handling")

        # ── Voice commands card ────────────────────────────────────────
        body = self._make_card(
            panel, "Voice Commands",
            "Say phrases like 'new line', 'stop dictation', 'undo' to trigger actions.",
        )
        self.var_commands_enabled = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.commands.enabled,
        )
        self._make_checkbutton(
            body, "Enable voice commands", self.var_commands_enabled,
        ).pack(anchor="w", pady=3)

        # ── Punctuation card ───────────────────────────────────────────
        body2 = self._make_card(
            panel, "Punctuation",
            "Auto mode uses Whisper's built-in punctuation. "
            "Manual lets you say 'period', 'comma', etc. "
            "Hybrid uses both (voice commands override auto).",
        )
        wc = self._card_row(body2, "Punctuation Mode")
        self.var_punct_mode = tk.StringVar(
            master=self.win, value=self.cfgm.config.punctuation.mode,
        )
        self._make_combobox(
            wc, textvariable=self.var_punct_mode,
            values=["auto", "manual", "hybrid"], width=16,
        ).pack(anchor="w")

        self.var_auto_capitalize = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.punctuation.auto_capitalize,
        )
        self._make_checkbutton(
            body2, "Auto-capitalise start of sentences",
            self.var_auto_capitalize,
        ).pack(anchor="w", pady=(6, 3))

    def _build_brain_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Brain / AI",
                           "Local LLM integration via Ollama for enhanced transcription")

        # ── Connection card ────────────────────────────────────────────
        body = self._make_card(
            panel, "Ollama Connection",
            "Ollama must be running locally. Install from ollama.com.",
        )
        self.var_brain_enabled = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.brain.enabled,
        )
        self._make_checkbutton(
            body, "Enable AI Brain (requires Ollama)", self.var_brain_enabled,
        ).pack(anchor="w", pady=(0, 6))

        wc = self._card_row(body, "Endpoint URL", "Default: http://localhost:11434")
        self.var_brain_endpoint = tk.StringVar(
            master=self.win, value=self.cfgm.config.brain.endpoint,
        )
        ModernEntry(wc, textvariable=self.var_brain_endpoint, width=28).pack(anchor="w")

        wc2 = self._card_row(body, "LLM Model",
                              "Must be pulled in Ollama first")
        self.var_brain_model = tk.StringVar(
            master=self.win, value=self.cfgm.config.brain.model,
        )
        self._make_combobox(
            wc2, textvariable=self.var_brain_model,
            values=["llama3.2", "llama3", "llama3.1", "mistral", "mistral-nemo",
                    "phi3", "gemma2", "qwen2.5"],
            width=24,
        ).pack(anchor="w")

        wc3 = self._card_row(body, "Timeout (s)", "Max wait for LLM response")
        self.var_brain_timeout = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.brain.timeout_sec,
        )
        ModernSlider(wc3, variable=self.var_brain_timeout,
                     from_=1.0, to=30.0, resolution=0.5, width=160).pack(anchor="w")

        # ── Feature toggles card ───────────────────────────────────────
        body2 = self._make_card(
            panel, "Features",
            "Each feature adds latency.  Disable if your LLM is slow.",
        )
        self.var_intent_routing = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.brain.intent_routing_enabled,
        )
        self._make_checkbutton(
            body2, "Intent routing  (map phrases to commands)",
            self.var_intent_routing,
        ).pack(anchor="w", pady=3)

        self.var_refinement = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.brain.refinement_enabled,
        )
        self._make_checkbutton(
            body2, "Text refinement  (grammar + filler removal)",
            self.var_refinement,
        ).pack(anchor="w", pady=3)

        self.var_context_summarizer = tk.BooleanVar(
            master=self.win, value=self.cfgm.config.brain.context_summarizer_enabled,
        )
        self._make_checkbutton(
            body2, "Context summariser  (rolling transcript window)",
            self.var_context_summarizer,
        ).pack(anchor="w", pady=3)

        # Context window card
        body3 = self._make_card(panel, "Context Window")
        wc4 = self._card_row(body3, "Window (seconds)",
                              "How many seconds of transcript to keep in context")
        self.var_context_window = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.brain.context_window_sec,
        )
        ModernSlider(wc4, variable=self.var_context_window,
                     from_=30.0, to=300.0, resolution=10.0, width=180).pack(anchor="w")

    def _build_appearance_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Appearance",
                           "Overlay colours, sizes, and window opacity")

        # ── Accent colours card ────────────────────────────────────────
        body = self._make_card(
            panel, "Accent Colours",
            "The overlay circle changes colour to reflect app state.",
        )
        wc = self._card_row(body, "Idle")
        self.var_color_idle = tk.StringVar(
            master=self.win, value=self.cfgm.config.ui.accent_color_idle,
        )
        ColorPicker(wc, textvariable=self.var_color_idle, width=12).pack(anchor="w")

        wc2 = self._card_row(body, "Recording")
        self.var_color_recording = tk.StringVar(
            master=self.win, value=self.cfgm.config.ui.accent_color_recording,
        )
        ColorPicker(wc2, textvariable=self.var_color_recording, width=12).pack(anchor="w")

        wc3 = self._card_row(body, "Processing")
        self.var_color_processing = tk.StringVar(
            master=self.win, value=self.cfgm.config.ui.accent_color_processing,
        )
        ColorPicker(wc3, textvariable=self.var_color_processing, width=12).pack(anchor="w")

        # ── Overlay card ───────────────────────────────────────────────
        body2 = self._make_card(panel, "Overlay")
        wc4 = self._card_row(body2, "Size (px)", "50–120 px diameter")
        self.var_visualizer_size = tk.IntVar(
            master=self.win, value=self.cfgm.config.ui.visualizer_size,
        )
        ModernSlider(wc4, variable=self.var_visualizer_size,
                     from_=50, to=120, resolution=5, width=180).pack(anchor="w")

        wc5 = self._card_row(body2, "Opacity")
        self.var_overlay_opacity = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.ui.overlay_opacity,
        )
        ModernSlider(wc5, variable=self.var_overlay_opacity,
                     from_=0.5, to=1.0, resolution=0.05, width=180).pack(anchor="w")

        # ── Settings window card ───────────────────────────────────────
        body3 = self._make_card(panel, "Settings Window")
        wc6 = self._card_row(body3, "Window Opacity",
                              "Applies immediately on next open")
        self.var_settings_opacity = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.ui.settings_window_opacity,
        )
        ModernSlider(wc6, variable=self.var_settings_opacity,
                     from_=0.7, to=1.0, resolution=0.05, width=180).pack(anchor="w")

        tk.Label(
            panel, text="Note: size and opacity changes take effect on next launch",
            bg=ColorTheme.BG_DARK, fg=ColorTheme.TEXT_DISABLED,
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=20, pady=(4, 12))

    def _build_advanced_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Advanced",
                           "Streaming, decoding, and text-output tuning")

        # ── Streaming card ─────────────────────────────────────────────
        body = self._make_card(
            panel, "Streaming & Segmentation",
            "Controls how audio is chunked before being sent to Whisper.",
        )
        wc = self._card_row(body, "Segmentation")
        self.var_seg = tk.StringVar(
            master=self.win, value=self.cfgm.config.streaming.segmentation,
        )
        self._make_combobox(wc, textvariable=self.var_seg,
                            values=["vad", "energy"], width=14).pack(anchor="w")

        wc2 = self._card_row(body, "Min Segment (s)")
        self.var_min_seg = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.streaming.min_segment_sec,
        )
        ModernEntry(wc2, textvariable=self.var_min_seg, width=8).pack(anchor="w")

        wc3 = self._card_row(body, "Min Silence (s)")
        self.var_min_sil = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.streaming.min_silence_sec,
        )
        ModernEntry(wc3, textvariable=self.var_min_sil, width=8).pack(anchor="w")

        wc4 = self._card_row(body, "Energy Threshold",
                              "Used when segmentation=energy")
        self.var_energy = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.streaming.energy_threshold,
        )
        ModernEntry(wc4, textvariable=self.var_energy, width=8).pack(anchor="w")

        # ── Decoding card ──────────────────────────────────────────────
        body2 = self._make_card(
            panel, "Decoding",
            "Whisper beam search and sampling parameters.",
        )
        wc5 = self._card_row(body2, "Beam Size",
                             "Higher = more accurate, slower  (1–10)")
        self.var_beam = tk.IntVar(
            master=self.win, value=self.cfgm.config.decoding.beam_size,
        )
        ModernEntry(wc5, textvariable=self.var_beam, width=8).pack(anchor="w")

        wc6 = self._card_row(body2, "Temperature",
                             "0.0 = deterministic (recommended)")
        self.var_temp = tk.DoubleVar(
            master=self.win, value=self.cfgm.config.decoding.temperature,
        )
        ModernEntry(wc6, textvariable=self.var_temp, width=8).pack(anchor="w")

        # ── Output card ────────────────────────────────────────────────
        body3 = self._make_card(
            panel, "Text Output",
            "How transcribed text is injected into the active window.",
        )
        wc7 = self._card_row(body3, "Primary Method",
                             "keyboard: simulate keypresses\nclipboard: paste via clipboard")
        self.var_output_method = tk.StringVar(
            master=self.win, value=self.cfgm.config.output.primary_method,
        )
        self._make_combobox(
            wc7, textvariable=self.var_output_method,
            values=["keyboard", "clipboard", "uia", "win32"], width=18,
        ).pack(anchor="w")

        wc8 = self._card_row(body3, "Clipboard threshold (chars)",
                             "Switch to clipboard paste for segments longer than this")
        self.var_prefer_clipboard = tk.IntVar(
            master=self.win,
            value=self.cfgm.config.output.prefer_clipboard_over_chars,
        )
        ModernEntry(wc8, textvariable=self.var_prefer_clipboard, width=8).pack(anchor="w")

    def _build_models_panel(self, panel: tk.Frame) -> None:
        self._panel_header(panel, "Models",
                           "Install, download, and benchmark Whisper models")

        # ── Installed card ─────────────────────────────────────────────
        body = self._make_card(panel, "Installed Models")
        ModernButton(
            body, text="Refresh", command=self._refresh_installed_models,
            width=90, height=30,
        ).pack(anchor="w", pady=(0, 6))
        self.installed_models_list = tk.Frame(body, bg=ColorTheme.BG_CARD_RAISED)
        self.installed_models_list.pack(fill=tk.X)
        self._refresh_installed_models()

        # ── Download card ──────────────────────────────────────────────
        body2 = self._make_card(
            panel, "Download Models",
            "Models are stored in the Vype model directory.",
        )
        dl_row = tk.Frame(body2, bg=ColorTheme.BG_CARD_RAISED)
        dl_row.pack(fill=tk.X, pady=(0, 6))
        self.var_download_model = tk.StringVar(value="base")
        self._make_combobox(
            dl_row, textvariable=self.var_download_model,
            values=list(self.model_manager.AVAILABLE_MODELS.keys()), width=18,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ModernButton(
            dl_row, text="Download", command=self._download_selected_model,
            width=110, height=30, primary=True,
        ).pack(side=tk.LEFT)

        self.model_info_label = tk.Label(
            body2, text="", bg=ColorTheme.BG_CARD_RAISED,
            fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9),
            wraplength=500, justify="left",
        )
        self.model_info_label.pack(anchor="w", pady=(0, 4))
        self.var_download_model.trace_add('write', lambda *_: self._update_model_info())
        self._update_model_info()

        hf_row = tk.Frame(body2, bg=ColorTheme.BG_CARD_RAISED)
        hf_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(
            hf_row, text="HuggingFace URL:", bg=ColorTheme.BG_CARD_RAISED,
            fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.var_hf_url = tk.StringVar()
        ModernEntry(hf_row, textvariable=self.var_hf_url, width=32).pack(side=tk.LEFT)

        # ── Manual install card ────────────────────────────────────────
        body3 = self._make_card(panel, "Manual Installation")
        tk.Label(
            body3,
            text=(
                "1. Download model files from HuggingFace\n"
                "2. Place them in the model directory\n"
                "3. Click 'Refresh' above to detect new models"
            ),
            bg=ColorTheme.BG_CARD_RAISED, fg=ColorTheme.TEXT_SECONDARY,
            font=("Segoe UI", 9), justify="left",
        ).pack(anchor="w", pady=(0, 6))
        ModernButton(
            body3, text="Open Model Folder",
            command=self._open_model_folder, width=150, height=30,
        ).pack(anchor="w")

        # ── NeMo / Canary card ─────────────────────────────────────────
        body_nemo = self._make_card(
            panel,
            "NeMo / Canary Models",
            "Canary-Qwen runs via NVIDIA NeMo (not managed by faster-whisper).",
        )

        self._nemo_status_label = tk.Label(
            body_nemo, text="", bg=ColorTheme.BG_CARD_RAISED,
            fg=ColorTheme.TEXT_SECONDARY, font=("Segoe UI", 9), justify="left",
            wraplength=500,
        )
        self._nemo_status_label.pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(body_nemo, bg=ColorTheme.BG_CARD_RAISED)
        btn_row.pack(fill=tk.X)
        ModernButton(
            btn_row, text="Refresh", command=self._refresh_nemo_models,
            width=90, height=30,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ModernButton(
            btn_row, text="Cache Canary-Qwen-2.5B",
            command=self._cache_canary_model,
            width=190, height=30, primary=True,
        ).pack(side=tk.LEFT)

        self._refresh_nemo_models()

        # ── Test card ──────────────────────────────────────────────────
        body4 = self._make_card(
            panel, "Model Benchmarking",
            "Run all installed models on a test clip to compare speed and accuracy.",
        )
        ModernButton(
            body4, text="Test All Models",
            command=self._test_models, width=140, height=30, primary=True,
        ).pack(anchor="w", pady=(0, 6))
        self.test_results_text = tk.Text(
            body4, height=9,
            bg=ColorTheme.BG_CARD, fg=ColorTheme.TEXT_PRIMARY,
            font=('Consolas', 9), wrap=tk.WORD, state=tk.DISABLED,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=ColorTheme.CARD_BORDER,
        )
        self.test_results_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self) -> None:
        footer = tk.Frame(self.win, bg=ColorTheme.BG_DARKER, height=56)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        footer.pack_propagate(False)

        # Thin separator above footer
        tk.Frame(self.win, bg=ColorTheme.BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)

        # Status badge (left)
        self._status_label = tk.Label(
            footer, text="", bg=ColorTheme.BG_DARKER,
            fg=ColorTheme.ACCENT_SUCCESS, font=("Segoe UI", 9),
        )
        self._status_label.pack(side=tk.LEFT, padx=20, pady=14)

        # Buttons (right)
        btn_row = tk.Frame(footer, bg=ColorTheme.BG_DARKER)
        btn_row.pack(side=tk.RIGHT, padx=16, pady=10)

        ModernButton(
            btn_row, text="Reset to Defaults",
            command=self._reset_to_defaults, width=140, height=36,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ModernButton(
            btn_row, text="Save", command=self._save,
            width=90, height=36, primary=True,
        ).pack(side=tk.LEFT)

    def _show_status(self, message: str, color: str = ColorTheme.ACCENT_SUCCESS) -> None:
        if not self._status_label:
            return
        if self._status_after_id and self.win:
            try:
                self.win.after_cancel(self._status_after_id)
            except Exception:
                pass
        self._status_label.configure(text=message, fg=color)

        def _fade() -> None:
            if self._status_label:
                self._status_label.configure(text="")
        self._status_after_id = self.win.after(3000, _fade) if self.win else None

    # ------------------------------------------------------------------
    # Models helpers
    # ------------------------------------------------------------------

    def _refresh_installed_models(self) -> None:
        for w in self.installed_models_list.winfo_children():
            w.destroy()
        installed = self.model_manager.list_installed_models()
        if not installed:
            tk.Label(
                self.installed_models_list, text="No models installed yet",
                bg=ColorTheme.BG_CARD_RAISED, fg=ColorTheme.TEXT_SECONDARY,
                font=("Segoe UI", 9),
            ).pack(anchor="w", pady=4)
        else:
            for model in installed:
                tk.Label(
                    self.installed_models_list,
                    text=f"✓  {model.name}  ({model.parameters}, {model.size_mb} MB)",
                    bg=ColorTheme.BG_CARD_RAISED, fg=ColorTheme.TEXT_PRIMARY,
                    font=("Segoe UI", 9),
                ).pack(anchor="w", pady=2)

    def _refresh_nemo_models(self) -> None:
        """Refresh NeMo/Canary cache status."""
        hub = Path.home() / ".cache" / "huggingface" / "hub"
        cached_dir = hub / "models--nvidia--canary-qwen-2.5b"
        cached = cached_dir.exists()

        backend = (getattr(self.cfgm.config.stt, "backend", "") or "").strip().lower()
        selected_model = str(self.cfgm.config.stt.model)

        parts = []
        parts.append(f"Backend selected: {backend or 'whisper'}")
        parts.append(f"Model selected: {selected_model}")
        parts.append("✓ Canary cache found" if cached else "• Canary cache not found (will download on first use)")
        parts.append('Install backend: `pip install -e ".[canary]"`')

        if getattr(self, "_nemo_status_label", None):
            self._nemo_status_label.configure(text="\n".join(parts))

    def _cache_canary_model(self) -> None:
        """Trigger NeMo to download/cache the Canary checkpoint."""
        try:
            from ..stt.canary_engine import CanaryQwenEngine

            eng = CanaryQwenEngine(model="nvidia/canary-qwen-2.5b", device="cuda", language="en")
            eng.preload()
            messagebox.showinfo("Cached", "Canary-Qwen-2.5B is cached and ready.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to cache Canary model:\n\n{exc}")
        finally:
            self._refresh_nemo_models()

    def _update_model_info(self) -> None:
        model_name = self.var_download_model.get()
        info = self.model_manager.get_model_info(model_name)
        if info:
            self.model_info_label.configure(text=(
                f"{info.description}  —  "
                f"{info.size_mb} MB  |  {info.parameters}  |  "
                f"Speed: {info.relative_speed}  |  Accuracy: {info.accuracy}"
            ))

    def _download_selected_model(self) -> None:
        model_name = self.var_download_model.get()
        success = self.model_manager.download_model(model_name, lambda _msg: None)
        if success:
            messagebox.showinfo("Downloaded", f"Model '{model_name}' is ready.")
            self._refresh_installed_models()
        else:
            messagebox.showerror("Error", f"Failed to download '{model_name}'.")

    def _open_model_folder(self) -> None:
        if not self.model_manager.open_model_directory():
            messagebox.showwarning("Warning", "Could not open model directory.")

    def _test_models(self) -> None:
        installed = self.model_manager.list_installed_models()
        if not installed:
            messagebox.showinfo("No Models", "No models installed to test.")
            return
        model_names = [m.name for m in installed]
        self.test_results_text.configure(state=tk.NORMAL)
        self.test_results_text.delete(1.0, tk.END)
        self.test_results_text.insert(tk.END, "Testing models, please wait…\n")
        self.test_results_text.configure(state=tk.DISABLED)
        self.test_results_text.update()

        def _progress(message: str) -> None:
            self.test_results_text.configure(state=tk.NORMAL)
            self.test_results_text.insert(tk.END, f"{message}\n")
            self.test_results_text.configure(state=tk.DISABLED)
            self.test_results_text.update()

        results = self.model_tester.test_all_models(
            model_names,
            device=self.cfgm.config.stt.device,
            compute_type=self.cfgm.config.stt.compute_type,
            progress_callback=_progress,
        )
        table = self.model_tester.format_results_table(results)
        self.test_results_text.configure(state=tk.NORMAL)
        self.test_results_text.delete(1.0, tk.END)
        self.test_results_text.insert(tk.END, table)
        self.test_results_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Save / reset / animate
    # ------------------------------------------------------------------

    def _reset_to_defaults(self) -> None:
        """Restore config to factory defaults after confirmation."""
        if not messagebox.askyesno(
            "Reset to Defaults",
            "This will reset ALL settings to their defaults.\nContinue?",
        ):
            return
        from ..config.schema import AppConfig
        defaults = AppConfig()
        self.cfgm.config = defaults
        self.cfgm.save()
        self._show_status("✓  Reset to defaults — please reopen Settings", ColorTheme.ACCENT_SUCCESS)
        if self.win:
            self.win.after(1200, self.win.destroy)

    def _save(self) -> None:
        try:
            hk = self.var_hotkey.get().strip()
            backend = (getattr(self, "var_backend", None).get().strip() if hasattr(self, "var_backend") else "whisper")
            model = self.var_model.get().strip()
            device = self.var_device.get().strip()
            compute = self.var_compute.get().strip()
            language = self.var_language.get().strip()
            sr = int(self.var_sr.get())
            device_id_raw = self.var_device_id.get()

            if device_id_raw in ("default", ""):
                did = None
            else:
                did = int(device_id_raw.split(":", 1)[0]) if ":" in device_id_raw else int(device_id_raw)

            needs_restart = (
                backend != str(getattr(self.cfgm.config.stt, "backend", "whisper"))
                or model != self.cfgm.config.stt.model
                or device != self.cfgm.config.stt.device
                or compute != self.cfgm.config.stt.compute_type
            )

            self.cfgm.update(
                # General
                ui__hotkey=hk,
                ui__start_minimized=self.var_start_minimized.get(),
                ui__close_to_tray=self.var_close_to_tray.get(),
                # Speech
                stt__backend=backend,
                stt__model=model,
                stt__device=device,
                stt__compute_type=compute,
                stt__language=language,
                stt__remove_filler_words=self.var_remove_fillers.get(),
                stt__improve_grammar=self.var_improve_grammar.get(),
                # Audio
                audio__sample_rate=sr,
                audio__device_id=did,
                vad__method=self.var_vad_method.get().strip(),
                vad__threshold=float(self.var_vad_threshold.get()),
                vad__min_speech_duration_ms=int(self.var_vad_min_speech.get()),
                vad__min_silence_duration_ms=int(self.var_vad_min_silence.get()),
                # Commands
                commands__enabled=self.var_commands_enabled.get(),
                punctuation__mode=self.var_punct_mode.get().strip(),
                punctuation__auto_capitalize=self.var_auto_capitalize.get(),
                # Brain / AI
                brain__enabled=self.var_brain_enabled.get(),
                brain__endpoint=self.var_brain_endpoint.get().strip(),
                brain__model=self.var_brain_model.get().strip(),
                brain__timeout_sec=float(self.var_brain_timeout.get()),
                brain__intent_routing_enabled=self.var_intent_routing.get(),
                brain__refinement_enabled=self.var_refinement.get(),
                brain__context_summarizer_enabled=self.var_context_summarizer.get(),
                brain__context_window_sec=float(self.var_context_window.get()),
                # Appearance
                ui__accent_color_idle=self.var_color_idle.get().strip(),
                ui__accent_color_recording=self.var_color_recording.get().strip(),
                ui__accent_color_processing=self.var_color_processing.get().strip(),
                ui__visualizer_size=int(self.var_visualizer_size.get()),
                ui__overlay_opacity=float(self.var_overlay_opacity.get()),
                ui__settings_window_opacity=float(self.var_settings_opacity.get()),
                # Advanced — streaming
                streaming__segmentation=self.var_seg.get().strip(),
                streaming__min_segment_sec=float(self.var_min_seg.get()),
                streaming__min_silence_sec=float(self.var_min_sil.get()),
                streaming__energy_threshold=float(self.var_energy.get()),
                # Advanced — decoding
                decoding__beam_size=int(self.var_beam.get()),
                decoding__temperature=float(self.var_temp.get()),
                # Advanced — output
                output__primary_method=self.var_output_method.get().strip(),
                output__prefer_clipboard_over_chars=int(self.var_prefer_clipboard.get()),
            )

            if needs_restart:
                self._show_status(
                    "✓  Saved — restart required for model/device changes",
                    '#f59e0b',
                )
            else:
                self._show_status("✓  All changes saved", ColorTheme.ACCENT_SUCCESS)

        except Exception as exc:
            messagebox.showerror("Settings Error", f"Failed to save: {exc}")

    def _animate_fade_in(self) -> None:
        if not self.win:
            return
        target_alpha = self.cfgm.config.ui.settings_window_opacity
        steps = 15

        def _step(n: int) -> None:
            if not self.win or n > steps:
                return
            try:
                self.win.attributes('-alpha', (n / steps) * target_alpha)
            except Exception:
                pass
            if n < steps:
                self.win.after(20, lambda: _step(n + 1))

        try:
            self.win.attributes('-alpha', 0.0)
            _step(0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Show
    # ------------------------------------------------------------------

    def _show_impl(self) -> None:
        self._original_config = copy.deepcopy(self.cfgm.config)

        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()

        if self.win is not None and tk.Toplevel.winfo_exists(self.win):
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            self.win.update_idletasks()
            return

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

    def show(self) -> None:
        if self.root is not None:
            try:
                self.root.after(0, self._show_impl)
                return
            except Exception:
                pass
        self._show_impl()
