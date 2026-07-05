"""`vype serve` — transcription + notes API for the mobile PWA and Siri Shortcuts.

Speaks the same OpenAI-compatible transcription shape the desktop app consumes,
so the phone can later point at any provider (or an on-device model) unchanged.
Serve over HTTPS with `tailscale serve` — the mic and service worker on the
phone require a secure context.

NOTE: no `from __future__ import annotations` here — FastAPI resolves type
hints at runtime, and stringified annotations can't see classes defined inside
create_app (params would silently degrade to query fields).
"""

import io
import logging
import secrets
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def _decode_wav(data: bytes) -> np.ndarray:
    """WAV bytes → 16 kHz mono float32 (linear resample if needed)."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
    except Exception as exc:
        raise ValueError(f"not a valid WAV file: {exc}") from exc

    if width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported sample width: {width}")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if rate != 16000:
        n_out = int(len(audio) * 16000 / rate)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, n_out), np.arange(len(audio)), audio
        ).astype(np.float32)
    return audio


def create_app(transcriber, notes, token: str):
    from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="vype serve")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_token(authorization: str | None = Header(default=None)) -> None:
        if authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="invalid or missing token")

    class NoteIn(BaseModel):
        text: str
        source: str = "app"
        tags: list[str] = []

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/v1/audio/transcriptions", dependencies=[Depends(require_token)])
    async def transcribe(file: UploadFile):
        data = await file.read()
        try:
            audio = _decode_wav(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        text = transcriber.transcribe(audio)
        return {"text": text}

    @app.post("/notes", dependencies=[Depends(require_token)])
    def add_note(note: NoteIn):
        if not note.text.strip():
            raise HTTPException(status_code=400, detail="empty note")
        return notes.add(note.text.strip(), source=note.source, tags=note.tags)

    @app.get("/notes", dependencies=[Depends(require_token)])
    def list_notes(limit: int = 50):
        return {"notes": notes.recent(limit)}

    return app


def run_serve() -> int:
    """Entry point for `vype serve`."""
    import uvicorn

    from .config import config_dir, load_config, save_config
    from .notes import NotesStore
    from .stt import create_transcriber

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    cfg = load_config()
    if not cfg.server.token:
        cfg.server.token = secrets.token_urlsafe(24)
        save_config(cfg)
        logger.info("Generated API token (saved to config)")

    transcriber = create_transcriber(cfg.stt)
    logger.info("Loading transcription model…")
    transcriber.load()

    notes = NotesStore(config_dir() / "notes.jsonl")
    app = create_app(transcriber=transcriber, notes=notes, token=cfg.server.token)

    # serve the PWA when a build exists next to the repo (dev) or the exe
    pwa_dist = Path(__file__).resolve().parents[2] / "mobile" / "dist"
    if pwa_dist.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(pwa_dist), html=True), name="pwa")
        logger.info("Serving PWA from %s", pwa_dist)

    # plain ASCII: Windows consoles often default to cp1252
    print(f"\nvype serve listening on http://{cfg.server.host}:{cfg.server.port}")
    print(f"API token: {cfg.server.token}")
    print("For phone access run:  tailscale serve --bg " f"{cfg.server.port}\n")
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port, log_level="info")
    return 0
