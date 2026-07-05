"""Cleaner: OpenAI-compatible chat call, minimal-edit prompt, hard fallback rules."""

import json

import httpx
import pytest

from vype.cleanup import CleanupUnavailable, Cleaner
from vype.config import CleanupConfig


def make_cleaner(handler, **cfg_overrides):
    cfg = CleanupConfig(base_url="http://test/v1", **cfg_overrides)
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url=cfg.base_url, timeout=cfg.timeout_s)
    return Cleaner(cfg, client=client)


def ok_response(content="Cleaned text."):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    return handler


def test_clean_returns_model_output():
    cleaner = make_cleaner(ok_response("Hello there."))
    assert cleaner.clean("um hello there") == "Hello there."


def test_request_shape():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    cleaner = make_cleaner(handler, model="test-model", api_key="sk-abc")
    cleaner.clean("some text")

    assert captured["url"].endswith("/chat/completions")
    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["messages"][0]["role"] == "system"
    assert "minimum edits" in body["messages"][0]["content"].lower()
    assert body["messages"][1] == {"role": "user", "content": "some text"}
    assert captured["auth"] == "Bearer sk-abc"


def test_no_auth_header_without_api_key():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    cleaner = make_cleaner(handler)
    cleaner.clean("text")
    assert captured["auth"] is None


def test_blank_input_short_circuits():
    def handler(request):  # pragma: no cover - must never be called
        raise AssertionError("no HTTP call expected for blank input")

    cleaner = make_cleaner(handler)
    assert cleaner.clean("   ") == "   "


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, text="boom"),
        lambda request: httpx.Response(429, text="rate limited"),
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
        lambda request: httpx.Response(200, json={"unexpected": "shape"}),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused")),
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
    ],
)
def test_failures_raise_cleanup_unavailable(handler):
    cleaner = make_cleaner(handler)
    with pytest.raises(CleanupUnavailable):
        cleaner.clean("some text")
