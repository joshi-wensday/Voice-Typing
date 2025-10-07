# Configuration Reference

Complete reference for Voice Typing configuration options.

## Configuration File Location

**Default Path**:
```
Windows: C:\Users\YourName\.voice-typing\config.yaml
```

**Creation**:
- Created automatically on first run with default values
- Copy from `config.example.yaml` for a template with comments

**Editing**:
- Edit file directly in a text editor
- Or use Settings UI (right-click overlay visualizer)
- Restart application after manual edits

---

## STT Configuration

Speech-to-text engine settings.

### `stt.model`

**Type**: String (enum)  
**Default**: `base`  
**Options**: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`

Whisper model size. Larger models are more accurate but slower.

| Model | Size | Accuracy | Speed (GTX 1080) | VRAM | Use Case |
|-------|------|----------|-------------------|------|----------|
| tiny | 39M | Low | <1s | 1GB | Testing, very low-end hardware |
| base | 74M | Good | 1-2s | 1GB | **Recommended for most users** |
| small | 244M | Better | 2-3s | 2GB | Better accuracy, acceptable speed |
| medium | 769M | High | 4-6s | 5GB | High accuracy, requires good GPU |
| large-v2 | 1550M | Best | 8-12s | 10GB | Maximum accuracy, powerful GPU |
| large-v3 | 1550M | Best | 8-12s | 10GB | Latest, best accuracy |

**Example**:
```yaml
stt:
  model: base
```

### `stt.device`

**Type**: String (enum)  
**Default**: `auto`  
**Options**: `auto`, `cuda`, `cpu`

Compute device for inference.

- **auto**: Automatically use GPU if available, fallback to CPU
- **cuda**: Force GPU (fails if CUDA not available)
- **cpu**: Force CPU (slower but works on any hardware)

**Example**:
```yaml
stt:
  device: auto  # Recommended
```

### `stt.language`

**Type**: String  
**Default**: `en`  
**Options**: ISO 639-1 language codes

Language for transcription. Whisper supports 99 languages.

Common codes: `en` (English), `es` (Spanish), `fr` (French), `de` (German), `zh` (Chinese), `ja` (Japanese)

**Example**:
```yaml
stt:
  language: en
```

### `stt.compute_type`

**Type**: String (enum)  
**Default**: `float16`  
**Options**: `float16`, `float32`, `int8`

Numerical precision for model computations.

- **float16**: Fastest on GPU, may not work on CPU (default)
- **float32**: Compatible with all devices, slower
- **int8**: Smallest memory footprint, fastest, slight accuracy loss

**Example**:
```yaml
stt:
  compute_type: float16
```

---

## Audio Configuration

Microphone and audio capture settings.

### `audio.device_id`

**Type**: Integer or null  
**Default**: `null` (system default)

Audio input device ID.

- `null`: Use system default microphone
- Integer: Specific device ID (see Settings UI for list)

**Finding Device IDs**:
Open Settings UI or run:
```python
from voice_typing.audio.capture import AudioCapture
for dev in AudioCapture().list_devices():
    print(f"{dev['id']}: {dev['name']}")
```

**Example**:
```yaml
audio:
  device_id: null  # or 1, 2, etc.
```

### `audio.sample_rate`

**Type**: Integer  
**Default**: `16000`  
**Recommended**: `16000` (Whisper requirement)

Audio sample rate in Hz. Must be 16000 for Whisper.

**Example**:
```yaml
audio:
  sample_rate: 16000
```

### `audio.channels`

**Type**: Integer  
**Default**: `1`  
**Options**: `1` (mono), `2` (stereo)

Number of audio channels. Whisper uses mono (1 channel).

**Example**:
```yaml
audio:
  channels: 1
```

### `audio.chunk_duration`

**Type**: Float  
**Default**: `0.5`  
**Range**: `0.1` - `2.0`

Duration of audio chunks in seconds. Affects streaming responsiveness.

- Lower: More responsive energy detection, higher CPU overhead
- Higher: Less overhead, delayed silence detection

**Example**:
```yaml
audio:
  chunk_duration: 0.5
```

### `audio.vad_enabled`

**Type**: Boolean  
**Default**: `false`

Enable Voice Activity Detection (experimental).

**Example**:
```yaml
audio:
  vad_enabled: false
```

### `audio.vad_aggressiveness`

**Type**: Integer  
**Default**: `2`  
**Range**: `0` - `3`

VAD sensitivity (if enabled). Higher values are more aggressive in filtering non-speech.

**Example**:
```yaml
audio:
  vad_aggressiveness: 2
```

---

## Punctuation Configuration

Control punctuation insertion behavior.

### `punctuation.mode`

**Type**: String (enum)  
**Default**: `hybrid`  
**Options**: `auto`, `manual`, `hybrid`

Punctuation handling mode:

- **auto**: Use Whisper's built-in punctuation only
- **manual**: Voice commands only (disable Whisper's punctuation)
- **hybrid**: Both (manual commands override auto punctuation)

**Example**:
```yaml
punctuation:
  mode: hybrid  # Recommended
```

### `punctuation.auto_capitalize`

**Type**: Boolean  
**Default**: `true`

Automatically capitalize the first letter of sentences.

**Example**:
```yaml
punctuation:
  auto_capitalize: true
```

### `punctuation.manual_commands`

**Type**: Object (map of command definitions)

Manual punctuation voice commands.

**Command Definition Structure**:
```yaml
punctuation:
  manual_commands:
    command_name:
      enabled: true/false
      pattern: "regex pattern"
      action: "text to insert"
      description: "human readable description"
```

**Default Commands**:
- `period`: "period" or "full stop" → `.`
- `comma`: "comma" → `,`
- `question_mark`: "question mark" → `?`
- `exclamation_mark`: "exclamation mark" or "exclamation point" → `!`

**Example (disable comma command)**:
```yaml
punctuation:
  manual_commands:
    comma:
      enabled: false
```

---

## Commands Configuration

Voice command settings.

### `commands.enabled`

**Type**: Boolean  
**Default**: `true`

Enable/disable all voice commands globally.

**Example**:
```yaml
commands:
  enabled: true
```

### `commands.new_line`

**Type**: Command definition  
**Default**: Enabled, pattern: `\b(new line|newline)\b`, action: `\n`

Built-in command for inserting line breaks.

**Example (customize)**:
```yaml
commands:
  new_line:
    enabled: true
    pattern: "\\b(new line|newline|next line)\\b"
    action: "\\n"
    description: Insert line break
```

### `commands.stop_dictation`

**Type**: Command definition  
**Default**: Enabled, pattern: `\b(stop dictation|stop listening)\b`

Built-in command to end recording session.

**Example**:
```yaml
commands:
  stop_dictation:
    enabled: true
    pattern: "\\b(stop dictation|stop listening)\\b"
    action: "STOP"
    description: End recording session
```

### `commands.custom_commands`

**Type**: Object (map of custom commands)  
**Default**: `{}`

User-defined custom commands.

**Examples**:

**Insert email address**:
```yaml
commands:
  custom_commands:
    my_email:
      enabled: true
      pattern: "\\b(insert email|my email)\\b"
      action: "your@email.com"
      description: Insert email address
```

**Insert email signature**:
```yaml
commands:
  custom_commands:
    signature:
      enabled: true
      pattern: "\\b(insert signature)\\b"
      action: "Best regards,\\nYour Name"
      description: Insert email signature
```

**Insert current date**:
```yaml
commands:
  custom_commands:
    today:
      enabled: true
      pattern: "\\b(insert date|today's date)\\b"
      action: "2025-01-08"  # Note: Static, not dynamic
      description: Insert current date
```

**Tips**:
- Use `\\b` for word boundaries (prevents false matches)
- Escape special characters: `\\n` for newline, `\\t` for tab
- Test patterns with multiple phrasings
- Keep patterns specific to avoid false triggers

---

## UI Configuration

User interface settings.

### `ui.show_visualizer`

**Type**: Boolean  
**Default**: `true`

Show circular audio visualizer overlay.

**Example**:
```yaml
ui:
  show_visualizer: true
```

### `ui.visualizer_size`

**Type**: Integer  
**Default**: `100`  
**Range**: `50` - `300`

Visualizer diameter in pixels.

**Example**:
```yaml
ui:
  visualizer_size: 100
```

### `ui.visualizer_opacity`

**Type**: Float  
**Default**: `0.8`  
**Range**: `0.0` - `1.0`

Visualizer window opacity (0.0 = transparent, 1.0 = opaque).

**Example**:
```yaml
ui:
  visualizer_opacity: 0.8
```

### `ui.visualizer_position`

**Type**: Array `[x, y]`  
**Default**: `[100, 100]`

Initial visualizer position (pixels from top-left corner).

Position is automatically updated when you drag the visualizer.

**Example**:
```yaml
ui:
  visualizer_position: [100, 100]
```

### `ui.start_minimized`

**Type**: Boolean  
**Default**: `true`

Start application minimized to system tray.

**Example**:
```yaml
ui:
  start_minimized: true
```

### `ui.close_to_tray`

**Type**: Boolean  
**Default**: `true`

Minimize to tray instead of exiting when closing window.

**Example**:
```yaml
ui:
  close_to_tray: true
```

### `ui.hotkey`

**Type**: String  
**Default**: `ctrl+shift+space`

Global hotkey for toggling dictation (press to start/stop).

**Format**: `modifier+modifier+key`

**Modifiers**: `ctrl`, `alt`, `shift`, `win`  
**Keys**: Letters, numbers, `space`, `tab`, function keys, etc.

**Examples**:
```yaml
ui:
  hotkey: ctrl+shift+space  # Default
  hotkey: ctrl+alt+v        # Alternative
  hotkey: ctrl+alt+shift+d  # Three modifiers
```

**Note**: If the specified hotkey fails to register, the app will try fallback hotkeys automatically.

---

## Output Configuration

Text injection settings.

### `output.primary_method`

**Type**: String (enum)  
**Default**: `keyboard`  
**Options**: `keyboard`, `uia`, `win32`, `clipboard`

Primary method for inserting text.

| Method | Speed | Compatibility | Notes |
|--------|-------|---------------|-------|
| keyboard | Fast | 90% apps | Simulated keystrokes |
| uia | Slow | 95% apps | UI Automation (modern apps) |
| win32 | Fast | 80% apps | Win32 API (legacy apps) |
| clipboard | Fastest | 99% apps | Overwrites clipboard temporarily |

**Example**:
```yaml
output:
  primary_method: keyboard
```

### `output.fallback_methods`

**Type**: Array of strings  
**Default**: `[clipboard]`

Fallback methods if primary fails (tried in order).

**Example**:
```yaml
output:
  fallback_methods: [clipboard]
```

### `output.typing_speed`

**Type**: Float  
**Default**: `0.01`  
**Range**: `0.001` - `0.1`

Delay between characters in seconds (for keyboard method).

- Lower: Faster typing, may cause issues in some apps
- Higher: Slower, more compatible

**Example**:
```yaml
output:
  typing_speed: 0.01
```

### `output.prefer_clipboard_over_chars`

**Type**: Integer  
**Default**: `200`

Use clipboard method for text longer than this many characters.

Reduces latency for long transcriptions.

**Example**:
```yaml
output:
  prefer_clipboard_over_chars: 200
```

---

## Streaming Configuration

Real-time transcription and segmentation settings.

### `streaming.mode`

**Type**: String (enum)  
**Default**: `final_only`  
**Options**: `final_only` (future: `semi_streaming`)

Streaming mode for transcription.

**Example**:
```yaml
streaming:
  mode: final_only
```

### `streaming.segmentation`

**Type**: String (enum)  
**Default**: `energy`  
**Options**: `energy` (future: `vad`)

Segmentation method for splitting audio.

- **energy**: Silence detection based on audio energy

**Example**:
```yaml
streaming:
  segmentation: energy
```

### `streaming.min_segment_sec`

**Type**: Float  
**Default**: `1.2`  
**Range**: `0.5` - `5.0`

Minimum segment length in seconds before transcription.

- Lower: More responsive, may transcribe incomplete thoughts
- Higher: Less frequent transcription, may delay results

**Example**:
```yaml
streaming:
  min_segment_sec: 1.2
```

### `streaming.min_silence_sec`

**Type**: Float  
**Default**: `0.6`  
**Range**: `0.3` - `2.0`

Minimum silence duration to finalize a segment.

- Lower: More responsive, may cut off mid-sentence
- Higher: Wait longer for pauses, less likely to interrupt

**Example**:
```yaml
streaming:
  min_silence_sec: 0.6
```

### `streaming.energy_threshold`

**Type**: Float  
**Default**: `0.015`  
**Range**: `0.001` - `0.1`

Energy threshold for silence detection (0.0 = silence, 1.0 = max).

- Lower: More sensitive (detects faint speech as active)
- Higher: Less sensitive (requires louder speech)

**Tuning**: If segments finalize too early, increase this value. If they wait too long, decrease it.

**Example**:
```yaml
streaming:
  energy_threshold: 0.015
```

---

## Decoding Configuration

Whisper model decoding parameters.

### `decoding.beam_size`

**Type**: Integer  
**Default**: `5`  
**Range**: `1` - `10`

Beam size for beam search decoding.

- `1`: Greedy search (fastest, slight accuracy loss)
- `5`: Default (good balance)
- `10+`: Maximum quality (slower)

**Example**:
```yaml
decoding:
  beam_size: 5
```

### `decoding.temperature`

**Type**: Float  
**Default**: `0.0`  
**Range**: `0.0` - `1.0`

Sampling temperature.

- `0.0`: Deterministic (recommended)
- Higher: More randomness in transcription

**Example**:
```yaml
decoding:
  temperature: 0.0
```

### `decoding.condition_on_previous_text`

**Type**: Boolean  
**Default**: `true`

Use previous transcription as context for coherence.

Improves accuracy for continuous speech.

**Example**:
```yaml
decoding:
  condition_on_previous_text: true
```

---

## Logging Configuration

Application logging settings.

### `log_level`

**Type**: String (enum)  
**Default**: `INFO`  
**Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`

Logging verbosity level.

- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages
- **WARNING**: Warning messages only
- **ERROR**: Errors only

**Example**:
```yaml
log_level: INFO
```

### `log_file`

**Type**: String or null  
**Default**: `null` (console only)

Path to log file. If `null`, logs only to console.

**Example**:
```yaml
log_file: null
# or
log_file: C:\Users\YourName\.voice-typing\voice-typing.log
```

---

## Complete Example Configuration

See `config.example.yaml` in the repository for a fully documented example configuration with all options.

## Configuration Best Practices

1. **Start with defaults**: Default config works well for most users
2. **Change incrementally**: Modify one setting at a time
3. **Test thoroughly**: Test in multiple applications after changes
4. **Keep backups**: Save working configurations before experimenting
5. **Use comments**: Document why you changed settings

## Troubleshooting Configuration Issues

**Invalid YAML syntax**:
- Use a YAML validator or editor with YAML support
- Check indentation (must use spaces, not tabs)
- Quote strings with special characters

**Config not loading**:
- Check file location: `~/.voice-typing/config.yaml`
- Verify permissions (file must be readable)
- Check console output for error messages

**Changes not applying**:
- Restart application after editing config file
- Or use Settings UI for some hot-reload options
- Verify YAML syntax is correct

**Default values used instead of custom**:
- Check indentation and nesting
- Verify field names match exactly (case-sensitive)
- Look for typos in configuration keys
