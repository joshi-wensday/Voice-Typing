"""Integrated progressive output window.

A floating dark-themed window that shows the live transcript produced by
ProgressiveTranscriber.  Draft text appears dimmed and becomes brighter as
refinement passes improve accuracy.

Layout
------
┌──────────────────────────────────────────────┐
│  Vype Output                  [●] Refining…  │  ← header (dark)
├──────────────────────────────────────────────┤
│                                              │
│  [scrollable tk.Text — read-only]            │
│                                              │
│  draft text  → #94a3b8 (slate-400, dimmed)   │
│  refined     → #e2e8f0 (slate-200, bright)   │
│  final       → #f8fafc bold (near-white)     │
│                                              │
├──────────────────────────────────────────────┤
│  [ Copy All ]    [ Clear ]                   │  ← footer
└──────────────────────────────────────────────┘
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .effects import ColorTheme


# Status indicator colours
_STATUS_COLORS = {
    "idle":       "#64748b",   # slate-500 (grey)
    "refining":   "#f59e0b",   # amber-500
    "finalizing": "#8b5cf6",   # violet-500
    "done":       "#10b981",   # emerald-500
}
_STATUS_LABELS = {
    "idle":       "Ready",
    "refining":   "Refining…",
    "finalizing": "Finalizing…",
    "done":       "Done",
}

# Text tag styles
_TAG_DRAFT   = "draft"
_TAG_REFINED = "refined"
_TAG_FINAL   = "final"


class IntegratedOutputWindow:
    """Floating output window with progressive transcript refinement display.

    Callbacks
    ---------
    on_clear  – called when the user presses [Clear]; lets the controller/
                ProgressiveTranscriber reset its audio buffer.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self.win: Optional[tk.Toplevel] = None
        self._text: Optional[tk.Text] = None
        self._status_dot: Optional[tk.Label] = None
        self._status_label: Optional[tk.Label] = None
        self._visible = False

        # External callback: called when [Clear] is pressed
        self.on_clear: Optional[Callable[[], None]] = None

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.win = tk.Toplevel(self._root)
        self.win.title("Vype Output")
        self.win.geometry("560x420+820+100")
        self.win.configure(bg=ColorTheme.BG_DARK)
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)

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

        self._build_header()
        self._build_text_area()
        self._build_footer()

        self.win.withdraw()   # hidden until show() is called

    def _build_header(self) -> None:
        hdr = tk.Frame(self.win, bg=ColorTheme.BG_SIDEBAR, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Title
        tk.Label(
            hdr, text="Vype Output",
            bg=ColorTheme.BG_SIDEBAR, fg=ColorTheme.TEXT_PRIMARY,
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=12)

        # Status (right-aligned)
        status_frame = tk.Frame(hdr, bg=ColorTheme.BG_SIDEBAR)
        status_frame.pack(side=tk.RIGHT, padx=16)

        self._status_dot = tk.Label(
            status_frame, text="●",
            bg=ColorTheme.BG_SIDEBAR, fg=_STATUS_COLORS["idle"],
            font=("Segoe UI", 10),
        )
        self._status_dot.pack(side=tk.LEFT, padx=(0, 4))

        self._status_label = tk.Label(
            status_frame, text=_STATUS_LABELS["idle"],
            bg=ColorTheme.BG_SIDEBAR, fg=_STATUS_COLORS["idle"],
            font=("Segoe UI", 9),
        )
        self._status_label.pack(side=tk.LEFT)

        # Separator
        tk.Frame(self.win, bg=ColorTheme.BORDER, height=1).pack(fill=tk.X)

    def _build_text_area(self) -> None:
        frame = tk.Frame(self.win, bg=ColorTheme.BG_DARK)
        frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=0)

        style = ttk.Style()
        style.configure(
            "Output.Vertical.TScrollbar",
            background=ColorTheme.BG_CARD,
            troughcolor=ColorTheme.BG_DARKER,
            borderwidth=0, arrowsize=12, width=10,
        )
        style.map(
            "Output.Vertical.TScrollbar",
            background=[("active", ColorTheme.ACCENT_PRIMARY), ("!active", ColorTheme.BG_CARD)],
        )

        scrollbar = ttk.Scrollbar(frame, orient="vertical", style="Output.Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._text = tk.Text(
            frame,
            bg=ColorTheme.BG_DARKER,
            fg=ColorTheme.TEXT_SECONDARY,
            insertbackground=ColorTheme.TEXT_PRIMARY,
            selectbackground=ColorTheme.ACCENT_PRIMARY,
            selectforeground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT,
            borderwidth=0,
            font=("Segoe UI", 11),
            wrap=tk.WORD,
            padx=14,
            pady=10,
            spacing3=4,               # extra space between paragraphs
            yscrollcommand=scrollbar.set,
            state=tk.DISABLED,        # read-only; we enable briefly to modify
            cursor="arrow",
        )
        self._text.pack(fill=tk.BOTH, expand=True)
        scrollbar.configure(command=self._text.yview)

        # Configure text tags for the three refinement levels
        self._text.tag_configure(
            _TAG_DRAFT,
            foreground="#94a3b8",    # slate-400: dimmed, "in progress"
            font=("Segoe UI", 11),
        )
        self._text.tag_configure(
            _TAG_REFINED,
            foreground="#e2e8f0",    # slate-200: clearly readable
            font=("Segoe UI", 11),
        )
        self._text.tag_configure(
            _TAG_FINAL,
            foreground="#f8fafc",    # near-white
            font=("Segoe UI", 11, "bold"),
        )

    def _build_footer(self) -> None:
        # Separator
        tk.Frame(self.win, bg=ColorTheme.BORDER, height=1).pack(fill=tk.X)

        # Taller footer (64 px) so buttons are never clipped on HiDPI displays.
        footer = tk.Frame(self.win, bg=ColorTheme.BG_SIDEBAR, height=64)
        footer.pack(fill=tk.X)
        footer.pack_propagate(False)

        # Centre buttons vertically in the footer using an inner frame
        btn_row = tk.Frame(footer, bg=ColorTheme.BG_SIDEBAR)
        btn_row.place(relx=0, rely=0.5, anchor="w", x=14)

        btn_copy = tk.Button(
            btn_row, text="⎘  Copy All",
            bg=ColorTheme.ACCENT_PRIMARY, fg="#ffffff",
            activebackground="#6d28d9",
            activeforeground="#ffffff",
            relief=tk.FLAT, padx=16, pady=7,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2", bd=0,
            command=self.copy_to_clipboard,
        )
        btn_copy.pack(side=tk.LEFT, padx=(0, 8))

        btn_clear = tk.Button(
            btn_row, text="✕  Clear",
            bg="#1e293b", fg=ColorTheme.TEXT_SECONDARY,
            activebackground="#334155",
            activeforeground=ColorTheme.TEXT_PRIMARY,
            relief=tk.FLAT, padx=16, pady=7,
            font=("Segoe UI", 10),
            cursor="hand2", bd=0,
            command=self._on_clear,
        )
        btn_clear.pack(side=tk.LEFT)

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
        if self._visible:
            self.hide()
        else:
            self.show()

    @property
    def visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------------
    # Text operations (must be called on Tk main thread)
    # ------------------------------------------------------------------

    def append_draft(self, text: str) -> None:
        """Append draft segment text (dimmed colour).  Thread-safe via root.after."""
        if not text or not self._text:
            return

        def _do():
            # Insert a space between segments when the last character isn't
            # already a space or newline — prevents "word1word2" run-ons.
            current = self._text.get("1.0", tk.END)
            if current.rstrip("\n") and not current.rstrip("\n")[-1] in (" ", "\n"):
                self._text.insert(tk.END, " ", _TAG_DRAFT)
            self._text.insert(tk.END, text, _TAG_DRAFT)
            self._auto_scroll()

        self._modify(_do)

    def replace_refined(self, full_text: str, final: bool = False) -> None:
        """Replace all displayed text with a refined version.

        ``full_text`` is the complete session transcript:
          committed (older, draft quality) + refined (recent window, re-transcribed).
        ``final`` is True for the stop-dictation pass — uses bold white text.
        Thread-safe via root.after.
        """
        if not self._text or not full_text:
            return
        tag = _TAG_FINAL if final else _TAG_REFINED

        def _do():
            self._text.delete("1.0", tk.END)
            self._text.insert("1.0", full_text, tag)
            self._auto_scroll()

        self._modify(_do)

        if final:
            self.set_status("done")

    def clear(self) -> None:
        """Clear displayed text (audio buffer reset is handled externally)."""
        if self._text:
            self._modify(lambda: self._text.delete("1.0", tk.END))
        self.set_status("idle")

    def set_status(self, status: str) -> None:
        """Update the status indicator.  Must be called on Tk main thread."""
        if not self._status_dot or not self._status_label:
            return
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["idle"])
        label = _STATUS_LABELS.get(status, status.capitalize())
        self._status_dot.configure(fg=color)
        self._status_label.configure(fg=color, text=label)

    def copy_to_clipboard(self) -> None:
        """Copy the full text content to the system clipboard."""
        if not self._text:
            return
        text = self._text.get("1.0", tk.END).rstrip()
        if text:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            # Flash the status briefly
            self.set_status("done")
            self.win.after(1500, lambda: self.set_status("idle"))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auto_scroll(self) -> None:
        """Scroll to end only when the user hasn't scrolled up manually."""
        if self._text and self._text.yview()[1] >= 0.95:
            self._text.see(tk.END)

    def _modify(self, fn) -> None:
        """Temporarily enable the read-only Text widget, run fn, then re-disable."""
        if not self._text:
            return
        self._text.configure(state=tk.NORMAL)
        try:
            fn()
        finally:
            self._text.configure(state=tk.DISABLED)

    def _on_clear(self) -> None:
        """Handle [Clear] button: clear text + notify external callback."""
        self.clear()
        if self.on_clear:
            self.on_clear()
