"""HotkeyListener combo logic: all keys down → press; any key up → release.

_on_event is pure state tracking — tests feed fake keyboard events directly.
"""

from vype.hotkey import HotkeyListener


class Event:
    def __init__(self, event_type, name):
        self.event_type = event_type
        self.name = name


class Recorder:
    def __init__(self):
        self.calls = []

    def press(self):
        self.calls.append("press")

    def release(self):
        self.calls.append("release")

    def escape(self):
        self.calls.append("escape")


def make(key):
    r = Recorder()
    listener = HotkeyListener(key, on_press=r.press, on_release=r.release, on_escape=r.escape)
    return listener, r


def test_single_key_press_release():
    listener, r = make("f8")
    listener._on_event(Event("down", "f8"))
    listener._on_event(Event("up", "f8"))
    assert r.calls == ["press", "release"]


def test_auto_repeat_fires_press_once():
    listener, r = make("f8")
    for _ in range(5):
        listener._on_event(Event("down", "f8"))
    listener._on_event(Event("up", "f8"))
    assert r.calls == ["press", "release"]


def test_combo_requires_all_keys():
    listener, r = make("ctrl+alt")
    listener._on_event(Event("down", "ctrl"))
    assert r.calls == []
    listener._on_event(Event("down", "alt"))
    assert r.calls == ["press"]


def test_combo_releases_when_any_key_lifts():
    listener, r = make("ctrl+alt")
    listener._on_event(Event("down", "ctrl"))
    listener._on_event(Event("down", "alt"))
    listener._on_event(Event("up", "ctrl"))
    assert r.calls == ["press", "release"]
    # lifting the second key must not fire a second release
    listener._on_event(Event("up", "alt"))
    assert r.calls == ["press", "release"]


def test_combo_can_cycle():
    listener, r = make("ctrl+alt")
    for _ in range(2):
        listener._on_event(Event("down", "ctrl"))
        listener._on_event(Event("down", "alt"))
        listener._on_event(Event("up", "alt"))
        listener._on_event(Event("up", "ctrl"))
    assert r.calls == ["press", "release", "press", "release"]


def test_left_right_modifier_variants_normalize():
    listener, r = make("ctrl+alt")
    listener._on_event(Event("down", "left ctrl"))
    listener._on_event(Event("down", "right alt"))
    assert r.calls == ["press"]
    listener._on_event(Event("up", "right alt"))
    assert r.calls == ["press", "release"]


def test_unrelated_keys_ignored():
    listener, r = make("ctrl+alt")
    listener._on_event(Event("down", "ctrl"))
    listener._on_event(Event("down", "a"))
    listener._on_event(Event("up", "a"))
    assert r.calls == []


def test_escape_fires_callback():
    listener, r = make("f8")
    listener._on_event(Event("down", "esc"))
    assert r.calls == ["escape"]


def test_single_right_ctrl_spec_still_works():
    """Backwards compatible with the old default config value."""
    listener, r = make("right ctrl")
    listener._on_event(Event("down", "right ctrl"))
    listener._on_event(Event("up", "right ctrl"))
    assert r.calls == ["press", "release"]


def test_none_event_name_is_ignored():
    listener, r = make("ctrl+alt")
    listener._on_event(Event("down", None))
    assert r.calls == []
