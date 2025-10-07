"""System tray integration using pystray."""

from __future__ import annotations

import threading
from typing import Callable, Optional

try:
    import pystray  # type: ignore
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - not always present in CI
    pystray = None  # type: ignore
    Image = None  # type: ignore


class TrayApp:
    def __init__(self, on_toggle: Callable[[], None], on_exit: Callable[[], None]) -> None:
        self.on_toggle = on_toggle
        self.on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._status = "idle"  # idle|recording|processing

    def is_available(self) -> bool:
        return pystray is not None and Image is not None

    def _create_image(self, color: tuple[int, int, int]) -> Image.Image:  # type: ignore[name-defined]
        # Simple 16x16 filled circle
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for x in range(16):
            for y in range(16):
                dx = x - 8
                dy = y - 8
                if dx * dx + dy * dy <= 49:
                    img.putpixel((x, y), (*color, 255))
        return img

    def _color_for_status(self) -> tuple[int, int, int]:
        return {
            "idle": (68, 255, 68),        # green
            "recording": (255, 68, 68),   # red
            "processing": (255, 220, 68), # yellow
        }.get(self._status, (68, 255, 68))

    def _update_icon_image(self) -> None:
        if self._icon is None:
            return
        image = self._create_image(self._color_for_status())
        self._icon.icon = image

    def _build_menu(self) -> "pystray.Menu":  # type: ignore[name-defined]
        return pystray.Menu(
            pystray.MenuItem("Toggle Dictation", lambda: self.on_toggle()),
            pystray.MenuItem("Exit", lambda: self._exit())
        )

    def _exit(self) -> None:
        if self._icon is not None:
            self._icon.stop()
        self.on_exit()

    def set_status(self, status: str) -> None:
        self._status = status
        self._update_icon_image()

    def run(self) -> None:
        if not self.is_available():
            return
        image = self._create_image(self._color_for_status())
        self._icon = pystray.Icon("voice_typing", image, "Voice Typing", self._build_menu())
        # Run tray in a separate thread so main thread can continue
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()
