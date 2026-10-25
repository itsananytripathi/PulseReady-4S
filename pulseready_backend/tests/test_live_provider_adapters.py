import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.integrations import elevenlabs_adapter, render_adapter
from app.integrations.external_clients import ExternalProviderError, IntegrationUnavailable


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        self.calls.append(("GET", args, kwargs))
        return self.response

    async def post(self, *args, **kwargs):
        self.calls.append(("POST", args, kwargs))
        return self.response


def test_render_service_listing_validates_and_parses_documented_response(monkeypatch):
    fake = FakeClient(httpx.Response(200, json=[{"service": {"id": "srv-synthetic"}}]))
    monkeypatch.setattr(render_adapter.httpx, "AsyncClient", lambda **_: fake)
    monkeypatch.setattr(render_adapter, "settings", SimpleNamespace(
        render_api_endpoint="https://api.render.com",
        render_api_token="synthetic-token",
        external_http_timeout_seconds=1.0,
    ))
    monkeypatch.setattr(render_adapter, "live_call_allowed", lambda service: service == "render")

    result = asyncio.run(render_adapter.list_services(limit=1))

    assert result == [{"service": {"id": "srv-synthetic"}}]
    assert fake.calls[0][0] == "GET"
    assert fake.calls[0][2]["headers"]["Authorization"] == "Bearer synthetic-token"


def test_render_errors_are_sanitized(monkeypatch):
    fake = FakeClient(httpx.Response(429, text="secret provider response"))
    monkeypatch.setattr(render_adapter.httpx, "AsyncClient", lambda **_: fake)
    monkeypatch.setattr(render_adapter, "settings", SimpleNamespace(
        render_api_endpoint="https://api.render.com",
        render_api_token="synthetic-token",
        external_http_timeout_seconds=1.0,
    ))
    monkeypatch.setattr(render_adapter, "live_call_allowed", lambda service: True)

    with pytest.raises(ExternalProviderError, match="unsuccessful") as error:
        asyncio.run(render_adapter.list_services())
    assert "secret provider response" not in str(error.value)


def test_elevenlabs_live_synthesis_validates_mp3_and_request(monkeypatch):
    sample = b"ID3" + b"synthetic-audio"
    fake = FakeClient(httpx.Response(200, content=sample))
    monkeypatch.setattr(elevenlabs_adapter.httpx, "AsyncClient", lambda **_: fake)
    monkeypatch.setattr(elevenlabs_adapter, "settings", SimpleNamespace(
        elevenlabs_api_endpoint="https://api.elevenlabs.io",
        elevenlabs_api_key="synthetic-key",
        elevenlabs_voice_id="synthetic-voice",
        elevenlabs_model_id="eleven_multilingual_v2",
        external_http_timeout_seconds=1.0,
    ))
    monkeypatch.setattr(elevenlabs_adapter, "live_call_allowed", lambda service: service == "elevenlabs")

    result = asyncio.run(elevenlabs_adapter.synthesize_speech(text="Synthetic briefing."))

    assert result == sample
    method, args, kwargs = fake.calls[0]
    assert method == "POST"
    assert args[0] == "/v1/text-to-speech/synthetic-voice"
    assert kwargs["json"] == {"text": "Synthetic briefing.", "model_id": "eleven_multilingual_v2"}
    assert kwargs["headers"]["xi-api-key"] == "synthetic-key"


def test_elevenlabs_live_synthesis_fails_closed_when_not_gated(monkeypatch):
    monkeypatch.setattr(elevenlabs_adapter, "settings", SimpleNamespace(
        elevenlabs_api_endpoint="https://api.elevenlabs.io",
        elevenlabs_api_key="synthetic-key",
        elevenlabs_voice_id="synthetic-voice",
        elevenlabs_model_id="eleven_multilingual_v2",
    ))
    monkeypatch.setattr(elevenlabs_adapter, "live_call_allowed", lambda service: False)

    with pytest.raises(IntegrationUnavailable):
        asyncio.run(elevenlabs_adapter.synthesize_speech(text="Synthetic briefing."))

