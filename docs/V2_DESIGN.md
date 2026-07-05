# Vype V2 — Design Document

**Status:** Proposed
**Date:** 2026-07-05
**Author:** Josh + Claude

---

## 1. Why a rewrite

V1 is ~6,350 lines of source. Its complexity exists almost entirely to work around one
assumption: **transcription is slow**. Because Canary-Qwen 2.5B takes seconds per call,
V1 built streaming VAD segmentation, per-segment draft typing, a two-zone
locked/unrefined transcript, pause-triggered re-refinement, sliding 35-second windows,
and a final whole-session pass — plus an 824-line animated orb and a 1,385-line settings
window to present it all.

That assumption is false in 2026. On an RTX 3080:

| Engine | 10 s utterance | 5 min journal dump |
|---|---|---|
| Parakeet TDT 0.6B v3 (onnx, GPU) | ~0.1 s | ~2–4 s |
| faster-whisper large-v3-turbo (int8) | ~0.3–0.5 s | ~10–15 s |
| V1 Canary-Qwen 2.5B (SALM) | ~1–2 s per segment | minutes of churn |

When a whole utterance transcribes in under half a second, **record-then-transcribe
beats streaming on every axis**: accuracy (model sees full context — no stitching
artifacts, no missed segment boundaries, no "smart sentence joining" heuristics),
latency (one pass instead of draft + refine + final), and code size (no VAD segmenter,
no ProgressiveTranscriber, no locked-text state machine).

This is exactly the architecture of freeflow and Wispr Flow: **hold key → record →
release → transcribe once → optional minimal-edit LLM cleanup → paste at cursor.**

## 2. Product definition

One sentence: *hold a key, talk, release, and your words appear at the cursor.*

Primary use: dumping thoughts into AI agents (Claude Code, chat UIs), brainstorming,
journaling. The consumer of the text is usually an LLM, so **raw speed matters more
than perfect prose** — cleanup is optional and off the hot path.

### What V2 does

1. **Push-to-talk**: hold the hotkey, speak, release → text pasted at cursor.
2. **Hands-free toggle**: tap the hotkey (< 300 ms) to start, tap again to stop —
   for long journal dumps where holding a key is annoying.
3. **Live preview**: while recording, the pill shows a live caption of what you've
   said so far (see §3.7 — cheap because the engine is fast; zero effect on the
   final paste path).
4. **Optional AI cleanup**: a mode toggle (tray/pill/hotkey chord). When on, the
   transcript passes through a minimal-edit LLM pass before pasting.
5. **Transcript history**: every transcript appended to a local JSONL file. Journal
   dumps are never lost, even if paste lands nowhere.
6. **Minimal UI**: a small bottom-center pill (state + audio level + live caption),
   a tray icon, and one compact settings dialog.

### What V2 deliberately does NOT do

- ❌ Live typing *into the target app* while you speak (that requires backspacing
  over corrections in someone else's text field — the source of most V1 complexity).
  Live text appears on the pill instead; the target app gets one clean paste.
- ❌ Voice commands ("scratch that", "new line") — with utterance-at-once dictation
  you just… re-speak. The cleanup LLM applies spoken self-corrections
  ("no wait, make that Tuesday") when cleanup mode is on.
- ❌ Multi-pass refinement, sliding windows, locked-text zones
- ❌ Model download/benchmark manager UI (a config field + first-run auto-download)
- ❌ Custom-drawn tkinter widgets, spectrum FFT analyzers, sonar-ring animations

Deferred to V2.1 (seams designed in, see §8):
- 🔜 Interactive review: show cleanup diff, accept/refine by voice, iterate
- 🔜 Per-app context hints (frontmost window title → cleanup prompt)
- 🔜 Personal dictionary / custom vocabulary

## 3. Architecture

### 3.1 The pipeline (the whole app)

```
 hotkey (press/release/tap)
   │
   ▼
 Recorder ── start() / stop() → np.float32 mono 16 kHz array
   │
   ▼
 Transcriber.transcribe(audio) → str          [protocol; local or API backend]
   │
   ▼
 Cleaner.clean(text) → str                    [optional; skipped when mode off]
   │
   ▼
 Injector.paste(text)                         [clipboard paste + restore]
   │
   ▼
 History.append(raw, cleaned)                 [JSONL, fire-and-forget]
```

One utterance = one linear pass. No queues between stages, no shared mutable
transcript state, no timers. The only concurrency: the pipeline runs on a single
worker thread so the UI/hotkey never block; the model is preloaded at startup.

### 3.2 State machine

Recording starts on key **press** either way (no lost audio); tap-vs-hold is decided
at release time (threshold 300 ms):

```
                 press
        IDLE ───────────► HELD_RECORDING
          ▲                   │
          │        release ≥ 300 ms → PROCESSING
          │        release < 300 ms → HANDSFREE_RECORDING
          │                                │ press → PROCESSING
          │                                │ esc   → IDLE (cancel)
          └── done/error ── PROCESSING ◄───┘
```

- Press during PROCESSING: ignored (pill shows busy).
- `Esc` in either recording state: cancel, discard audio.
- Utterances shorter than 0.3 s are discarded (accidental tap guard).
- This enum + transition table is pure logic → first thing written under TDD.

### 3.3 Module layout (~1,200 lines total, target)

```
src/vype/
  app.py               ~120   composition root: wire hotkey→pipeline→ui, Qt event loop
  pipeline.py          ~100   state machine + worker thread; the only orchestrator
  hotkey.py             ~90   global key listener; classifies press/hold/tap
  recorder.py           ~80   sounddevice capture; level meter for the pill
  stt/
    __init__.py         ~30   Transcriber protocol + factory from config
    parakeet.py         ~70   onnx-asr, Parakeet TDT 0.6B v3 (default, GPU)
    whisper.py          ~70   faster-whisper large-v3-turbo (multilingual alt)
    openai_api.py       ~60   POST /v1/audio/transcriptions (any key/base_url)
  cleanup.py            ~90   OpenAI-compatible chat client + minimal-edit prompt
  inject.py             ~70   clipboard snapshot → set → Ctrl+V → restore
  history.py            ~40   append-only JSONL at ~/.vype/history.jsonl
  config.py            ~110   pydantic schema + YAML at ~/.vype/config.yaml
  ui/
    pill.py            ~160   frameless translucent bottom-center pill (Qt)
    tray.py             ~70   tray icon + menu (mode toggle, copy last, settings, quit)
    settings.py        ~250   one compact dialog: hotkey, engine, cleanup, audio device
```

Compare V1: 6,344 lines, of which UI alone was 3,657.

### 3.4 Key interfaces

```python
class Transcriber(Protocol):
    def load(self) -> None: ...                          # called once at startup, warm
    def transcribe(self, audio: np.ndarray) -> str: ...  # 16 kHz mono float32 in, text out

class Cleaner(Protocol):
    def clean(self, text: str) -> str: ...               # raises CleanupUnavailable → paste raw
```

That's the entire modularity story. **Local vs API is a config change, not a code
change** (freeflow's trick): the `openai_api` backend and the `cleanup` client both
speak the OpenAI-compatible API, so pointing `base_url` at `http://localhost:11434/v1`
(Ollama), LM Studio, Groq, or api.openai.com is the same code path.

```yaml
# ~/.vype/config.yaml
hotkey: right ctrl        # hold = push-to-talk, tap = toggle hands-free
stt:
  backend: parakeet        # parakeet | whisper | openai
  device: cuda
  # openai backend only:
  base_url: null
  api_key: null
  model: whisper-1
cleanup:
  enabled: false           # runtime-toggleable from tray/pill
  base_url: http://localhost:11434/v1
  api_key: null
  model: qwen3:8b
audio:
  device_id: null          # system default mic
ui:
  show_pill: true
```

### 3.5 Technology decisions

| Decision | Choice | Rationale |
|---|---|---|
| STT default | **Parakeet TDT 0.6B v3** via `onnx-asr` | ~6.3% WER (beats whisper-large-v3), tens-of-ms latency on a 3080, ~1.5 GB VRAM, tiny dependency (no NeMo). English-focused fits the use case. |
| STT alternative | faster-whisper large-v3-turbo int8 | Multilingual, built-in Silero VAD filter for silence hallucinations, battle-tested, still <0.5 s per utterance. |
| Drop NeMo | yes | `nemo_toolkit` is a multi-GB dependency tree for one model class; both replacements are pip-light. Canary-Qwen 2.5B was also the latency problem. |
| UI framework | **PySide6** | Frameless translucent windows, DPI awareness, dark mode, real widgets, thread-safe signals — for free. Deletes all 472 lines of `effects.py` and every custom-drawn widget. tkinter is why V1 looks dated. |
| Text injection | **clipboard paste + restore** (primary), keystroke typing (fallback for apps that block paste) | Instant for any length, no per-char timing bugs, works in terminals/Electron/browsers. Snapshot clipboard → set → `Ctrl+V` → restore after 1 s, **only if the clipboard still holds our text** (don't clobber a copy the user made in between). |
| Hotkey | `keyboard` lib press/release hooks | PTT needs key-up events; Win32 `RegisterHotKey` only gives key-down (why V1 grew two hotkey systems — V2 has one). Tap-vs-hold threshold: 300 ms. |
| Audio | `sounddevice`, 16 kHz mono float32, in-memory buffer | Same as V1's capture core (the one V1 part worth keeping). No temp-WAV round-trip: arrays pass straight to the engine. |
| Cleanup LLM | Ollama-hosted small model by default (e.g. qwen3:8b), any OpenAI-compatible endpoint | 3080 has 10 GB VRAM: Parakeet (1.5 GB) + an 8B Q4 model fit together. Cloud key = paste into settings. |
| Process model | one process, model warm at startup | App lives in tray; no server processes to babysit. The protocol keeps the server option open. |

### 3.6 Live preview (how V2 gets live text without V1's architecture)

While in a recording state, a preview loop ticks every ~1.5 s:

1. Snapshot the accumulated audio buffer (capped to the **last 30 s** for long dumps).
2. Re-transcribe the snapshot **from scratch** (skip the tick if the engine is busy).
3. Show the result as a caption on the pill.

That's the entire feature. No VAD segmentation, no stitching, no locked zones, no
draft-vs-refined text classes — because the engine is fast enough (~200 ms for 30 s
of audio) that throwing the preview away and redoing it each tick is affordable.

Invariants that keep it simple:
- Preview text is **disposable** — it never feeds the paste path. The final paste
  always comes from one clean pass over the full utterance audio.
- Preview and final transcription share one engine lock; final always wins
  (a preview tick is skipped, never queued).
- `ui.live_preview: false` turns the loop off entirely; nothing else changes.

### 3.7 Latency budget (key release → text at cursor)

| Stage | Raw mode | Cleanup mode |
|---|---|---|
| Stop recording (in-memory) | ~0 ms | ~0 ms |
| Parakeet transcribe (10 s speech) | ~100–300 ms | ~100–300 ms |
| LLM cleanup (local 8B) | — | ~0.5–2 s |
| Clipboard paste | ~50 ms | ~50 ms |
| **Total** | **< 0.5 s** | **~1–2.5 s** |

Raw mode is the default because the usual consumer is an AI agent that tolerates
messy text. Cleanup mode is for human-facing output.

## 4. UX specification

### The pill (the only always-visible UI)

A small rounded pill, bottom-center, always-on-top, click-through except on hover:

- **Idle**: nearly invisible (thin dim bar). Hover reveals the hotkey hint.
- **Recording**: expands slightly; live audio-level bars (Wispr's Flow Bar pattern);
  timer appears after 10 s (`0:42`) for long dumps.
- **Processing**: subtle indeterminate shimmer, < 1 s in raw mode.
- **Cleanup mode on**: small accent dot on the pill; click the pill to toggle.
- **Error**: brief red flash + toast ("No mic input", "Cleanup offline — pasted raw").

### The tray

Icon reflects state. Menu: `Cleanup mode ✓ / ✗ · Copy last transcript · History… ·
Settings… · Quit`. "Copy last transcript" is the safety net when a paste landed in
the wrong window.

### Settings (one dialog, ~8 controls)

Hotkey capture, mic device dropdown + live level, STT backend + device, cleanup
on/off + endpoint/model/key, launch-at-startup. No theme editors, no model
benchmark tables, no opacity sliders.

## 5. The cleanup prompt (freeflow's philosophy, proven)

> Make the **minimum edits** needed for clean output. Remove filler ("um", "uh"),
> hesitations, duplicate starts, and abandoned fragments. Fix punctuation,
> capitalization, spacing, and obvious transcription mistakes. Apply the speaker's
> self-corrections ("no wait, make that…") and remove the correction phrase.
> Preserve tone, word choice, and language. Never add content, never answer
> questions in the text, never comment. Output only the edited text.

Temperature 0. On timeout (5 s) or connection error: **paste the raw transcript**
and toast — cleanup must never lose words or block dictation.

## 6. Test-driven development plan

Design rule that makes TDD possible: **every module is pure logic behind a thin I/O
edge.** Hardware (mic, GPU, keyboard, clipboard) is injected, so unit tests run
anywhere in milliseconds.

### Test pyramid

```
tests/
  unit/            fast, no hardware, run on every commit
    test_state_machine.py     all transitions incl. tap-during-processing, Esc-cancel
    test_hotkey_classifier.py press/release timing → tap vs hold (fake clock)
    test_config.py            defaults, YAML roundtrip, env overrides, migration from v1 path
    test_cleanup.py           prompt assembly, timeout→raw fallback, mocked HTTP (respx)
    test_inject.py            snapshot/set/paste/restore ordering (fake clipboard+keys)
    test_history.py           JSONL append, rotation
    test_stt_factory.py       config → backend selection, API backend request shape
  contract/
    test_transcriber_contract.py  every backend satisfies the protocol (FakeTranscriber
                                  + real classes with mocked engines): 16 kHz float32 in,
                                  str out, empty audio → "", load() idempotent
  integration/     marked @pytest.mark.gpu / @pytest.mark.audio, run locally
    test_parakeet_real.py     fixture WAVs → expected transcripts (WER threshold)
    test_e2e_latency.py       fixture WAV through full pipeline < 1.0 s budget
    fixtures/                 3–5 short WAVs: clean speech, filler-heavy, long-form
```

### Process

1. **Red → green per module**, in dependency order: `config` → `state machine` →
   `hotkey classifier` → `history` → `inject` → `cleanup` → `stt factory/contract` →
   `recorder` → `pipeline` (wires fakes end-to-end) → UI last (thin, mostly manual).
2. A **FakeTranscriber / FakeCleaner / FakeClipboard** trio lives in `tests/conftest.py`;
   the full pipeline is testable end-to-end with zero hardware.
3. CI (GitHub Actions, Windows runner): unit + contract on every push; integration
   suite is local-only (`pytest -m "gpu or audio"`).
4. Coverage gate on the non-UI core: 90 %.

## 7. Migration plan

1. **Branch `v2`**, tag current main as `v1.0.0-final`. V1 keeps working while V2 grows.
2. Scaffold new package layout + tooling (`ruff` replaces black+flake8), delete
   committed `venv/`, `build/`, `dist/`, `.coverage` from git.
3. TDD the core in the order above. The V1 `AudioCapture` internals (sounddevice
   callback + level meter) port over with light cleanup; everything else is new.
4. First dogfood milestone: **hotkey → Parakeet → paste** working end-to-end (raw
   mode only, tray-only UI). Use it daily immediately; this is < half the code.
5. Add pill → settings dialog → cleanup mode → installer.
6. When V2 is daily-driver stable: merge to main, V1 code deleted (git history keeps it).

## 8. V2.1 seams (designed now, built later)

- **Interactive review**: `Cleaner.clean()` already returns text separately from
  `Injector.paste()` — a review window slots between them. Diff view (raw vs
  cleaned), then a voice reply ("keep the first change, drop the second") re-invokes
  the cleaner with the diff + instruction as context. Iterate until "send it" → paste.
- **Context awareness**: `win32gui.GetForegroundWindow()` title captured at
  record-start, passed as a hint in the cleanup prompt ("target: Slack" → casual).
- **Personal dictionary**: a word list in config, injected into the Whisper
  `initial_prompt` / cleanup prompt (freeflow caps this at ~224 tokens).
- **Streaming preview** (only if ever missed): the Transcriber protocol gains an
  optional `transcribe_stream()`; nothing else changes.

## 9. Summary of what dies and why

| V1 component (lines) | Fate | Replaced by |
|---|---|---|
| SileroVADSegmenter + streaming loop (413) | ☠️ deleted | record whole utterance |
| ProgressiveTranscriber (406) | ☠️ deleted | one fast transcribe pass |
| CanaryQwenEngine + NeMo (380 + GB of deps) | ☠️ deleted | Parakeet onnx / faster-whisper |
| Voice-command regex + segment deletion (150) | ☠️ deleted | re-speak; LLM self-corrections |
| Overlay orb + effects + spectrum (1,468) | ☠️ deleted | Qt pill (~160) |
| SettingsWindow (1,385) | ☠️ deleted | Qt dialog (~250) |
| Dual hotkey systems (171) | ☠️ deleted | one `keyboard` listener (~90) |
| 3 output strategies + handler (177) | simplified | paste + restore (~70) |
| IntegratedOutputWindow (452) | ☠️ deleted | history JSONL + "Copy last" |
| Model manager UI (175) | ☠️ deleted | config field + auto-download |
| AudioCapture core | ✅ ported | recorder.py |
| Pydantic config pattern | ✅ ported | config.py (smaller schema) |
