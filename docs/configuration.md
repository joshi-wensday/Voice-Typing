# Configuration Reference

Configuration file path: `~/.voice-typing/config.yaml`

## STT
- `model`: tiny|base|small|medium|large-v2
- `device`: auto|cuda|cpu
- `language`: e.g., en
- `compute_type`: int8|float16|float32

## Audio
- `device_id`: null or device index
- `sample_rate`: 16000
- `channels`: 1
- `chunk_duration`: seconds
- `vad_enabled`: boolean
- `vad_aggressiveness`: 0-3

## Punctuation
- `mode`: auto|manual|hybrid
- `auto_capitalize`: boolean
- `manual_commands`: map of command definitions

## Commands
- `enabled`: boolean
- `new_line`, `stop_dictation`: built-in command definitions
- `custom_commands`: user-defined commands

## UI
- `show_visualizer`: boolean
- `visualizer_size`: int
- `visualizer_opacity`: float 0-1
- `visualizer_position`: [x, y]
- `start_minimized`, `close_to_tray`: booleans
- `hotkey`: string

## Output
- `primary_method`: keyboard|uia|win32|clipboard
- `fallback_methods`: list
- `typing_speed`: seconds per character

## Logging
- `log_level`: DEBUG|INFO|WARNING|ERROR
- `log_file`: path or null
