"""Integrated progressive output window.

Layout
------
┌──────────────────────────────────────────────────────┐
│  Vype Output          [⎘ Copy]  [✕]  [●] Ready       │  ← header
├──────────────────────────────────────────────────────┤
│                                                      │
│  [scrollable tk.Text — read-only]          ║  slim  │
│                                            ║  scroll │
│  draft text  → #94a3b8 (dimmed)            ║  bar   │
│  refined     → #e2e8f0 (bright)            ║        │
│  final       → #f8fafc bold                ║        │
│                                                      │
└──────────────────────────────────────────────────────┘

Design decisions
----------------
* Buttons live in the header so they are always visible no matter how small
  the window is resized — no footer whose height might get clipped.
* The scrollbar is a custom canvas widget (SlimScrollbar) that renders a slim
  dark pill with no native OS chrome, arrows or borders.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .effects import ColorTheme


# ---------------------------------------------------------------------------
# Custom slim scrollbar
# ---------------------------------------------------------------------------

class SlimScrollbar(tk.Canvas):
    """Canvas-based vertical scrollbar — no native OS chrome, fully styleable.

    Drop-in replacement for ttk.Scrollbar:
      • Implements the standard Tkinter scrollbar protocol (set / yview).
      • Works with ``yscrollcommand=scrollbar.set`` on tk.Text / tk.Listbox.
    """

    _WIDTH        = 8
    _TROUGH_BG    = "#0f172a"
    _THUMB_NORMAL = "#334155"
    _THUMB_HOVER  = "#475569"
    _THUMB_DRAG   = "#64748b"
    _THUMB_MIN_PX = 28
    _PAD          = 1   # horizontal padding inside the canvas

    def __init__(self, parent: tk.Widget, command: Optional[Callable] = None, **kw) -> None:
        kw.setdefault("width", self._WIDTH)
        kw.setdefault("bg", self._TROUGH_BG)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, **kw)

        self._command = command
        self._first: float = 0.0
        self._last: float  = 1.0

        self._hover  = False
        self._drag_y: Optional[int] = None
        self._drag_first: float     = 0.0

        self.bind("<Configure>",        self._draw)
        self.bind("<Enter>",            self._on_enter)
        self.bind("<Leave>",            self._on_leave)
        self.bind("<ButtonPress-1>",    self._on_press)
        self.bind("<B1-Motion>",        self._on_drag)
        self.bind("<ButtonRelease-1>",  self._on_release)

    # ------------------------------------------------------------------
    # Standard scrollbar protocol
    # ------------------------------------------------------------------

    def set(self, first: str | float, last: str | float) -> None:
        """Called by the text widget when the view changes."""
        self._first = float(first)
        self._last  = float(last)
        self._draw()

    def configure(self, **kw) -> None:
        if "command" in kw:
            self._command = kw.pop("command")
        if kw:
            super().configure(**kw)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self, _event=None) -> None:
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h < 4 or w < 4:
            return

        # Thumb geometry
        span  = self._last - self._first
        span  = max(0.0, min(1.0, span))
        t_h   = max(self._THUMB_MIN_PX, int(span * h))
        t_y   = int(self._first * h)
        t_y   = min(t_y, h - t_h)    # clamp

        x1 = self._PAD
        x2 = w - self._PAD
        y1 = t_y + 2
        y2 = t_y + t_h - 2

        if self._drag_y is not None:
            color = self._THUMB_DRAG
        elif self._hover:
            color = self._THUMB_HOVER
        else:
            color = self._THUMB_NORMAL

        # Rounded rectangle
        r = (x2 - x1) // 2
        self._rounded_rect(x1, y1, x2, y2, r, color)

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, fill: str) -> None:
        r = min(r, (x2 - x1) // 2, max(1, (y2 - y1) // 2))
        self.create_polygon(
            x1 + r, y1,   x2 - r, y1,
            x2,     y1 + r,
            x2,     y2 - r,
            x2 - r, y2,   x1 + r, y2,
            x1,     y2 - r,
            x1,     y1 + r,
            fill=fill, outline="", smooth=True,
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_enter(self, _e) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _e) -> None:
        self._hover = False
        self._draw()

    def _on_press(self, e: tk.Event) -> None:
        h = self.winfo_height()
        if h < 1:
            return
        span  = max(0.0, min(1.0, self._last - self._first))
        t_h   = max(self._THUMB_MIN_PX, int(span * h))
        t_y   = min(int(self._first * h), h - t_h)

        if t_y <= e.y <= t_y + t_h:
            # Click on thumb — start drag
            self._drag_y     = e.y
            self._drag_first = self._first
        else:
            # Click on trough — jump
            if self._command:
                self._command("moveto", str(e.y / h))
        self._draw()

    def _on_drag(self, e: tk.Event) -> None:
        if self._drag_y is None:
            return
        h = self.winfo_height()
        if h < 1:
            return
        delta    = (e.y - self._drag_y) / h
        new_first = max(0.0, min(1.0 - (self._last - self._first),
                                  self._drag_first + delta))
        if self._command:
            self._command("moveto", str(new_first))

    def _on_release(self, _e) -> None:
        self._drag_y = None
        self._draw()


# ---------------------------------------------------------------------------
# Status colours / labels
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "idle":       "#64748b",
    "refining":   "#f59e0b",
    "finalizing": "#8b5cf6",
    "done":       "#10b981",
}
_STATUS_LABELS = {
    "idle":       "Ready",
    "refining":   "Refining…",
    "finalizing": "Finalizing…",
    "done":       "Done",
}

_TAG_DRAFT   = "draft"
_TAG_REFINED = "refined"
_TAG_FINAL   = "final"


# ---------------------------------------------------------------------------
# Output window
# ---------------------------------------------------------------------------

class IntegratedOutputWindow:
    """Floating output window that shows live + progressively refined text.

    Callbacks
    ---------
    on_clear  – called when [✕] is pressed so the ProgressiveTranscriber can
                reset its audio buffer in sync with the UI.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self.win: Optional[tk.Toplevel] = None
        self._text: Optional[tk.Text]   = None
        self._status_dot: Optional[tk.Label]   = None
        self._status_label: Optional[tk.Label] = None
        self._visible = False

        self.on_clear: Optional[Callable[[], None]] = None

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.win = tk.Toplevel(self._root)
        self.win.title("Vype Output")
        self.win.geometry("580x440+820+100")
        self.win.configure(bg=ColorTheme.BG_DARK)
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        self.win.minsize(320, 200)

        # Windows dark title bar
        try:
            import ctypes
            self.win.update()
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

        self._build_header()
        self._build_text_area()

        self.win.withdraw()

    def _build_header(self) -> None:
        hdr = tk.Frame(self.win, bg=ColorTheme.BG_SIDEBAR)
        hdr.pack(fill=tk.X)

        # ── Title ─────────────────────────────────────────────────────────
        tk.Label(
            hdr, text="Vype Output",
            bg=ColorTheme.BG_SIDEBAR, fg=ColorTheme.TEXT_PRIMARY,
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT, padx=(14, 0), pady=10)

        # ── Status (right-most) ───────────────────────────────────────────
        status_frame = tk.Frame(hdr, bg=ColorTheme.BG_SIDEBAR)
        status_frame.pack(side=tk.RIGHT, padx=(0, 14), pady=10)

        self._status_dot = tk.Label(
            status_frame, text="●",
            bg=ColorTheme.BG_SIDEBAR, fg=_STATUS_COLORS["idle"],
            font=("Segoe UI", 9),
        )
        self._status_dot.pack(side=tk.LEFT, padx=(0, 3))

        self._status_label = tk.Label(
            status_frame, text=_STATUS_LABELS["idle"],
            bg=ColorTheme.BG_SIDEBAR, fg=_STATUS_COLORS["idle"],
            font=("Segoe UI", 9),
        )
        self._status_label.pack(side=tk.LEFT)

        # ── Buttons (left of status, right of title) ──────────────────────
        btn_clear = tk.Button(
            hdr, text="✕  Clear",
            bg=ColorTheme.BG_SIDEBAR, fg="#64748b",
            activebackground="#1e293b", activeforeground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT, padx=10, pady=4,
            font=("Segoe UI", 9), cursor="hand2", bd=0,
            command=self._on_clear,
        )
        btn_clear.pack(side=tk.RIGHT, padx=(0, 6), pady=10)

        btn_copy = tk.Button(
            hdr, text="⎘  Copy",
            bg=ColorTheme.ACCENT_PRIMARY, fg="#ffffff",
            activebackground="#6d28d9", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=4,
            font=("Segoe UI", 9, "bold"), cursor="hand2", bd=0,
            command=self.copy_to_clipboard,
        )
        btn_copy.pack(side=tk.RIGHT, padx=(0, 4), pady=10)

        # Separator under header
        tk.Frame(self.win, bg=ColorTheme.BORDER, height=1).pack(fill=tk.X)

    def _build_text_area(self) -> None:
        frame = tk.Frame(self.win, bg=ColorTheme.BG_DARKER)
        frame.pack(fill=tk.BOTH, expand=True)

        # Custom slim scrollbar (right edge)
        self._scrollbar = SlimScrollbar(frame)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2), pady=4)

        self._text = tk.Text(
            frame,
            bg=ColorTheme.BG_DARKER,
            fg=ColorTheme.TEXT_SECONDARY,
            insertbackground=ColorTheme.TEXT_PRIMARY,
            selectbackground=ColorTheme.ACCENT_PRIMARY,
            selectforeground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT, borderwidth=0,
            font=("Segoe UI", 11),
            wrap=tk.WORD,
            padx=14, pady=10, spacing3=4,
            yscrollcommand=self._scrollbar.set,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self._text.pack(fill=tk.BOTH, expand=True)
        self._scrollbar.configure(command=self._text.yview)

        self._text.tag_configure(_TAG_DRAFT,   foreground="#94a3b8", font=("Segoe UI", 11))
        self._text.tag_configure(_TAG_REFINED, foreground="#e2e8f0", font=("Segoe UI", 11))
        self._text.tag_configure(_TAG_FINAL,   foreground="#f8fafc", font=("Segoe UI", 11, "bold"))

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def show(self) -> None:
        if self.win:
            self.win.deiconify()
            self.win.lift()
            self._visible = True

    def hide(self) -> None:
        if self.win:
            self.win.withdraw()
            self._visible = False

    def toggle(self) -> None:
        (self.hide if self._visible else self.show)()

    @property
    def visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------------
    # Text operations (Tk main thread only)
    # ------------------------------------------------------------------

    def append_draft(self, text: str) -> None:
        """Append a new unrefined segment (dimmed).  Call via root.after."""
        if not text or not self._text:
            return

        def _do() -> None:
            # Add a space between segments to prevent word run-ons
            existing = self._text.get("1.0", tk.END).rstrip("\n")
            if existing and existing[-1] not in (" ", "\n"):
                self._text.insert(tk.END, " ", _TAG_DRAFT)
            self._text.insert(tk.END, text, _TAG_DRAFT)
            self._auto_scroll()

        self._modify(_do)

    def replace_refined(self, full_text: str, final: bool = False) -> None:
        """Replace all displayed text with the current locked transcript.

        ``full_text`` is only the **locked** (refined) portion — previously
        refined text is included because it is appended in ProgressiveTranscriber.
        Any new unrefined segments will be re-appended as drafts afterwards.
        ``final`` uses bold white text and sets status to Done.
        """
        if not self._text or not full_text:
            return
        tag = _TAG_FINAL if final else _TAG_REFINED

        def _do() -> None:
            self._text.delete("1.0", tk.END)
            self._text.insert("1.0", full_text, tag)
            self._auto_scroll()

        self._modify(_do)
        if final:
            self.set_status("done")

    def clear(self) -> None:
        """Clear displayed text and reset status."""
        if self._text:
            self._modify(lambda: self._text.delete("1.0", tk.END))
        self.set_status("idle")

    def set_status(self, status: str) -> None:
        if not self._status_dot or not self._status_label:
            return
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["idle"])
        label = _STATUS_LABELS.get(status, status.capitalize())
        self._status_dot.configure(fg=color)
        self._status_label.configure(fg=color, text=label)

    def copy_to_clipboard(self) -> None:
        if not self._text:
            return
        text = self._text.get("1.0", tk.END).rstrip()
        if text:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self.set_status("done")
            if self.win:
                self.win.after(1500, lambda: self.set_status("idle"))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auto_scroll(self) -> None:
        if self._text and self._text.yview()[1] >= 0.95:
            self._text.see(tk.END)

    def _modify(self, fn: Callable) -> None:
        if not self._text:
            return
        self._text.configure(state=tk.NORMAL)
        try:
            fn()
        finally:
            self._text.configure(state=tk.DISABLED)

    def _on_clear(self) -> None:
        self.clear()
        if self.on_clear:
            self.on_clear()
