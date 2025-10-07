from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from voice_typing.audio.capture import AudioCapture


@patch("sounddevice.query_devices")
def test_list_devices_filters_input(mock_query_devices: MagicMock) -> None:
    mock_query_devices.return_value = [
        {"name": "OutOnly", "max_input_channels": 0, "default_samplerate": 48000},
        {"name": "Mic 1", "max_input_channels": 2, "default_samplerate": 44100},
    ]
    ac = AudioCapture()
    devices = ac.list_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "Mic 1"


@patch("sounddevice.InputStream")
def test_start_and_stop_records_audio(mock_stream_cls: MagicMock) -> None:
    # Mock stream to call back with synthetic data
    callbacks = {}

    def _init_stream(callback=None, **kwargs):
        callbacks["cb"] = callback
        m = MagicMock()
        return m

    mock_stream_cls.side_effect = _init_stream

    ac = AudioCapture(sample_rate=16000, channels=1, chunk_duration=0.01)
    ac.start_recording()

    # Simulate callback delivering audio chunk
    samples = np.random.randn(160).astype(np.float32)
    callbacks["cb"](samples.reshape(-1, 1), 160, None, None)

    out = ac.stop_recording()
    assert out.dtype == np.float32
    assert out.size > 0
