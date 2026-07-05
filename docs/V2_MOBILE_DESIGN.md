# Vype Mobile — Design Document

**Status:** Approved (v1 scaffolded)
**Date:** 2026-07-05
**Owner:** Josh + Claude

---

## 1. Purpose

A **capture tool** for the phone. Not system-wide dictation (iOS forbids it), not
retrieval, not a second brain — just: get the thought out of your head and safely
stored, with the least possible friction. Two concrete moments:

1. **Quick dictation** — open app, hold screen, talk, release. Swipe right to
   copy (→ paste into WhatsApp etc.), swipe left to save as a note.
2. **Podcast/driving capture** — phone mounted or pocketed, podcast playing in
   the car. Pause the podcast from the wheel, speak a thought, it becomes a
   note. Zero touches. *(v2 — needs a native shell, see §6.)*

Retrieval/processing of captured notes is explicitly out of scope.

## 2. Architecture

```
┌────────────── iPhone ──────────────┐        ┌───────── PC (RTX 3080) ─────────┐
│ PWA (mobile/)                      │        │ vype serve  (FastAPI)           │
│  hold-to-talk UI + gestures        │ HTTPS  │  POST /v1/audio/transcriptions  │
│  WebAudio → 16 kHz WAV             │──────► │   → existing Transcriber        │
│  offline queue (IndexedDB)         │ (tail- │  POST/GET /notes → notes.jsonl  │
│  recents (expiring) + notes        │  scale)│  serves the PWA static files    │
└────────────────────────────────────┘        └─────────────────────────────────┘
```

- **Server-first transcription.** The iPhone 8 (A11, iOS 16, no WebGPU) can't
  run a decent model in the browser. The PC already runs Parakeet; the phone
  sends 16 kHz WAV over Tailscale and gets text back in ~1 s.
- **Modular by URL.** The PWA speaks the OpenAI-compatible transcription API —
  the same boundary as desktop. Moving to cloud hosting (or, post-phone-upgrade,
  an on-device model) is a config change, not a rewrite.
- **Capture can never be lost.** Audio is persisted to IndexedDB the moment
  recording stops, *then* uploaded. No signal → it queues and retries when the
  `online` event fires (event-driven, no battery-burning polling).

### Hosting / HTTPS (required — mic + service worker need a secure context)

v1: the vype server serves the PWA itself, fronted by **`tailscale serve`**,
which provides a real HTTPS cert on your tailnet
(`https://<pc>.<tailnet>.ts.net`). Single origin, no CORS pain, installable to
the home screen from anywhere on the tailnet. CORS is enabled anyway so the
static files can later move to GitHub Pages/Vercel unchanged.

### Audio format

WebAudio capture → downsample to 16 kHz mono → WAV encoded in JS. Deliberately
avoids MediaRecorder codec hell (iOS emits AAC/mp4, which the server would need
ffmpeg to decode). WAV is ~1.9 MB/min — fine for dictation-length clips.

## 3. UX specification (v1 PWA)

One screen, dark, same visual language as desktop (teal accent).

- **Hold anywhere** → recording (waveform + timer). **Release** → transcribe,
  result appears as a card.
- **Swipe up while holding** → lock hands-free; tap to stop.
- On a result card: **swipe right = copy** (teal blink, like desktop),
  **swipe left = save to Notes**.
- **Swipe down** (idle) → history: *Recents* (auto-expire after 48 h) and
  *Notes* (persist until deleted).
- Pending uploads show a queued badge; they resolve to text when the server is
  reachable. The audio is already safe either way.
- Settings (gear): server URL + token, test-connection button.

## 4. Server (`vype serve`)

Runs inside the existing desktop package (`vype serve` from the CLI):

- `POST /v1/audio/transcriptions` — multipart WAV → `{"text": ...}` via the
  already-loaded Transcriber. Accepts any sample rate (resamples to 16 kHz).
- `POST /notes` `{text, source?, tags?}` / `GET /notes?limit=` — append-only
  JSONL at `~/.vype/notes.jsonl`. **Notes persist** (unlike desktop dictation
  history) — capture must survive.
- `GET /health` — used by the PWA's test-connection button.
- Bearer-token auth (token auto-generated into config on first run).
- Serves `mobile/dist` at `/` when present.

## 5. Siri Shortcut (capture of last resort)

One-time manual setup, documented here because it can't be code:

> Shortcuts app → new shortcut "Podcast note": **Dictate text** →
> **Get contents of URL** (POST `https://<pc>…/notes`, JSON
> `{"text": <dictated>, "source": "siri"}`, header
> `Authorization: Bearer <token>`).

"Hey Siri, podcast note" then works **hands-free with the screen locked**, in
any app, even when the native shell (v2) is expired or broken. Apple-quality
transcription rather than Parakeet, which is acceptable for short notes.

## 6. v2 — Podcast mode (native shell)

A PWA cannot listen with the screen off or while another app is foregrounded —
hard iOS limit. Podcast mode therefore ships as a **Capacitor shell** around
the same web app plus one native module:

- Keep-alive via a background audio session; observe
  `AVAudioSession.isOtherAudioPlaying`.
- Podcast **pauses** → arm the mic (never while audio plays: avoids the
  Bluetooth HFP quality-drop and podcast bleed-through). Wake-phrase gate
  ("take a note") before capture; podcast resumes → disarm.
- Spotify currently-playing (OAuth) tags the note with show/episode/position.
- **Build without a Mac:** GitHub Actions macOS runners build the IPA;
  **SideStore/AltStore** (companion runs on Windows) signs with a free Apple ID
  and auto-refreshes over Wi-Fi — the 7-day free-signing expiry becomes
  invisible because the PC is always on. Known risk: this toolchain breaks for
  a few weeks after some iOS updates; acceptable for a personal tool.
- Weekly review is an **app feature** (surface the week's captures for triage),
  deliberately not coupled to the signing cadence.

## 7. Testing

Same doctrine as desktop: pure logic behind thin I/O edges.

- **PWA (vitest):** gesture state machine (hold/lock/swipes), WAV encode +
  resample (golden bytes), upload queue retry/backoff (fake store + fake
  fetch), recents expiry, API request shapes.
- **Server (pytest):** endpoints via FastAPI TestClient with FakeTranscriber —
  auth rejection, WAV decode/resample, notes roundtrip, health.
- Manual: real-device mic capture, Tailscale roundtrip, home-screen install.

## 8. Milestones

1. **M1 (this scaffold):** `vype serve` + PWA with full quick-dictation loop,
   tested cores. Dogfood on Wi-Fi.
2. **M2:** Tailscale-serve setup note, Siri Shortcut configured, offline-queue
   hardening from real use.
3. **M3:** Capacitor shell + audio-session spike in the actual car (the
   go/no-go for podcast mode's "capture while other audio playing" ambitions).
4. **M4:** Spotify tagging, weekly review view.
