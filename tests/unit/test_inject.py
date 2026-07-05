"""Injector: clipboard snapshot → set → paste → conditional restore."""

from vype.inject import Injector


class FakeClipboard:
    def __init__(self, initial=""):
        self.value = initial
        self.writes = []

    def read(self):
        return self.value

    def write(self, text):
        self.value = text
        self.writes.append(text)


class FakeKeys:
    def __init__(self):
        self.sent = []

    def send(self, combo):
        self.sent.append(combo)


class ImmediateScheduler:
    """Captures the restore callback so tests control when it fires."""

    def __init__(self):
        self.pending = []

    def __call__(self, delay_s, fn):
        self.pending.append(fn)

    def fire(self):
        for fn in self.pending:
            fn()
        self.pending.clear()


def make(initial_clip="previous"):
    clip, keys, sched = FakeClipboard(initial_clip), FakeKeys(), ImmediateScheduler()
    return Injector(clipboard=clip, keys=keys, schedule=sched), clip, keys, sched


def test_paste_sets_clipboard_then_sends_ctrl_v():
    inj, clip, keys, _ = make()
    inj.paste("hello")
    assert clip.writes == ["hello"]
    assert keys.sent == ["ctrl+v"]


def test_restore_returns_previous_clipboard():
    inj, clip, keys, sched = make("previous")
    inj.paste("hello")
    sched.fire()
    assert clip.value == "previous"


def test_restore_skipped_if_user_copied_something_else():
    inj, clip, keys, sched = make("previous")
    inj.paste("hello")
    clip.value = "user copied this meanwhile"
    sched.fire()
    assert clip.value == "user copied this meanwhile"


def test_empty_text_is_noop():
    inj, clip, keys, sched = make()
    inj.paste("")
    assert clip.writes == []
    assert keys.sent == []
    assert sched.pending == []


def test_clipboard_read_failure_still_pastes():
    inj, clip, keys, sched = make()
    clip.read = lambda: (_ for _ in ()).throw(RuntimeError("clipboard locked"))
    inj.paste("hello")
    assert clip.value == "hello"
    assert keys.sent == ["ctrl+v"]
    sched.fire()  # nothing to restore; must not raise
    assert clip.value == "hello"
