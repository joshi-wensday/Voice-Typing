# 🎤 Vype V2

**Hold a key, talk, release, and your words appear at the cursor.**

Local-first voice dictation for Windows. Built for dumping thoughts into AI agents,
brainstorming, and journaling — raw speed first, optional AI cleanup when the text
is for humans.

> V2 is a ground-up rewrite (~1,200 lines vs V1's ~6,300). Design and rationale:
> [docs/V2_DESIGN.md](docs/V2_DESIGN.md). V1 lives at the `v1.0.0-final` tag.

## How it works

```
hold hotkey → speak → release → transcribe (local GPU) → [optional LLM cleanup] → paste
```

- **Hold** `right ctrl` (configurable): push-to-talk. Release pastes at the cursor.
- **Tap** it instead: hands-free mode for long journal dumps; tap again to stop. `Esc` cancels.
- **Live preview**: a pill at the bottom of the screen shows your words as you speak.
- **AI cleanup mode** (tray toggle): a minimal-edit LLM pass — removes filler,
  applies "no wait, make that…" self-corrections, fixes punctuation. Falls back to
  the raw transcript if the LLM is unreachable; it never blocks or loses words.
- **History**: every transcript is appended to `~/.vype/history.jsonl`.

## Install (dev)

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .[ui,parakeet,dev]
# GPU: onnxruntime-gpu needs CUDA 12.x; see onnx-asr docs if install fails
vype
```

Engines (config `stt.backend`):

| backend | engine | notes |
|---|---|---|
| `parakeet` (default) | NVIDIA Parakeet TDT 0.6B v3 (onnx) | fastest + most accurate, English + EU languages |
| `whisper` | faster-whisper large-v3-turbo | multilingual |
| `openai` | any OpenAI-compatible `/audio/transcriptions` | set `stt.base_url` + `stt.api_key` |

Cleanup uses any OpenAI-compatible chat endpoint — Ollama locally
(`http://localhost:11434/v1`, default) or a cloud key. Config lives at
`~/.vype/config.yaml` (tray → *Open config file*).

## Tests

```powershell
pytest              # unit + contract suite, no hardware needed (<1 s)
pytest -m gpu       # real-model integration tests (downloads weights, needs CUDA)
```
