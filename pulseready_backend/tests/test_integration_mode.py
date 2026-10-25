from types import SimpleNamespace

import pytest

from app import config
from app.integrations import adaption_adapter, browser_use_adapter, external_clients


def test_integration_mode_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("INTEGRATION_MODE", raising=False)
    assert config.parse_integration_mode(None) == "mock"
    assert config.parse_bool(None) is False


def test_unknown_mode_and_invalid_global_flag_are_rejected():
    with pytest.raises(RuntimeError, match="INTEGRATION_MODE"):
        config.parse_integration_mode("staging")
    with pytest.raises(RuntimeError, match="INTEGRATIONS_ENABLED"):
        config.parse_bool("maybe")


def test_mock_mode_never_constructs_http_client(monkeypatch):
    monkeypatch.setattr(external_clients, "settings", SimpleNamespace(
        integration_mode="mock",
        integrations_enabled=True,
        enabled_integrations=("elevenlabs",),
        elevenlabs_api_key="synthetic-key",
        elevenlabs_api_endpoint="https://provider.invalid",
        external_http_timeout_seconds=1.0,
    ))
    monkeypatch.setattr(external_clients.httpx, "AsyncClient", lambda **_: pytest.fail("HTTP client must not be created"))
    assert external_clients.live_call_allowed("elevenlabs") is False
    with pytest.raises(external_clients.IntegrationUnavailable, match="mock mode"):
        external_clients.create_provider_client("elevenlabs")


def test_live_mode_requires_global_gate_and_service_configuration(monkeypatch):
    monkeypatch.setattr(external_clients, "settings", SimpleNamespace(
        integration_mode="live",
        integrations_enabled=False,
        enabled_integrations=("elevenlabs",),
        elevenlabs_api_key="synthetic-key",
        elevenlabs_api_endpoint="https://provider.invalid",
        external_http_timeout_seconds=1.0,
    ))
    assert external_clients.live_call_allowed("elevenlabs") is False
    with pytest.raises(external_clients.IntegrationUnavailable, match="globally disabled"):
        external_clients.create_provider_client("elevenlabs")

    monkeypatch.setattr(external_clients, "settings", SimpleNamespace(
        integration_mode="live",
        integrations_enabled=True,
        enabled_integrations=("elevenlabs",),
        elevenlabs_api_key="YOUR_API_KEY_HERE",
        elevenlabs_api_endpoint="https://provider.invalid",
        external_http_timeout_seconds=1.0,
    ))
    assert external_clients.live_call_allowed("elevenlabs") is False


def test_mock_settings_accept_missing_provider_credentials(monkeypatch):
    monkeypatch.setenv("PULSEREADY_API_KEYS", '{"synthetic-key":"11111111-1111-4111-8111-111111111111"}')
    monkeypatch.setenv("INTEGRATION_MODE", "mock")
    monkeypatch.delenv("INTEGRATIONS_ENABLED", raising=False)
    for name in (
        "AGENT37_CLOUD_API_KEY", "ADAPTION_LABS_API_KEY", "ELEVENLABS_API_KEY",
        "BROWSER_USE_API_KEY", "NODUS_COMPUTE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = config.get_settings()
    assert settings.integration_mode == "mock"
    assert settings.integrations_enabled is False
    assert settings.elevenlabs_api_key is None


def test_provider_http_errors_timeouts_and_malformed_json_are_safe(monkeypatch):
    monkeypatch.setattr(external_clients, "settings", SimpleNamespace(
        integration_mode="live",
        integrations_enabled=True,
        enabled_integrations=("elevenlabs",),
        elevenlabs_api_key="synthetic-key",
        elevenlabs_api_endpoint="https://provider.invalid",
        external_http_timeout_seconds=1.0,
    ))

    class Client:
        async def request(self, *args, **kwargs):
            raise external_clients.httpx.TimeoutException("provider secret")

        async def aclose(self):
            pass

    monkeypatch.setattr(external_clients, "create_provider_client", lambda service: Client())
    import asyncio
    with pytest.raises(external_clients.ExternalProviderError, match="timed out") as error:
        asyncio.run(external_clients.request_json("elevenlabs", method="POST", path="/tts"))
    assert "provider secret" not in str(error.value)

    with pytest.raises(external_clients.IntegrationUnavailable, match="relative"):
        asyncio.run(external_clients.request_json("elevenlabs", method="GET", path="https://evil.invalid"))


def test_diagnostics_never_return_secret_values(monkeypatch):
    monkeypatch.setattr(external_clients, "settings", SimpleNamespace(
        integration_mode="mock",
        integrations_enabled=False,
        enabled_integrations=(),
        agent37_cloud_api_key="synthetic-secret",
        agent37_cloud_endpoint="https://secret.example/path",
        agent37_personal_api_key=None,
        agent37_personal_endpoint=None,
        adaption_labs_api_key=None,
        adaption_labs_endpoint=None,
        render_api_token=None,
        render_api_endpoint=None,
        nodus_compute_api_key=None,
        nodus_compute_endpoint=None,
        elevenlabs_api_key=None,
        elevenlabs_api_endpoint=None,
        browser_use_api_key=None,
        browser_use_endpoint=None,
        flutterflow_api_key=None,
        flutterflow_endpoint=None,
    ))
    result = external_clients.integration_statuses()
    assert result[0]["capability"] == "agent37_cloud"
    assert result[0]["credential_configured"] is True
    assert result[0]["endpoint_configured"] is True
    assert all("synthetic-secret" not in str(item) for item in result)
    assert all("secret.example" not in str(item) for item in result)


def test_mock_mode_blocks_adaption_and_browser_use_even_when_credentials_exist(monkeypatch):
    monkeypatch.setattr(adaption_adapter, "settings", SimpleNamespace(
        integration_mode="mock", integrations_enabled=True, adaption_enabled=True,
        enabled_integrations=("adaption_labs",), adaption_labs_api_key="synthetic",
        adaption_labs_endpoint="https://provider.invalid", external_http_timeout_seconds=1.0,
    ))
    assert adaption_adapter.is_configured() is False
    with pytest.raises(adaption_adapter.AdaptionUnavailable):
        import asyncio
        asyncio.run(adaption_adapter.run_dataset_adaptation(dataset_id="dataset", column_mapping={}, job_specification={}))

    monkeypatch.setattr(browser_use_adapter, "settings", SimpleNamespace(
        integration_mode="mock", integrations_enabled=True,
        enabled_integrations=("browser_use",), browser_use_api_key="synthetic",
        browser_use_endpoint="https://provider.invalid",
    ))
    assert browser_use_adapter.is_configured() is False
    with pytest.raises(browser_use_adapter.BrowserUseUnavailable):
        import asyncio
        asyncio.run(browser_use_adapter.run_hosted_task(task="synthetic task"))


def test_integration_status_route_is_authenticated_and_non_secret(api):
    client, _, _ = api
    assert client.get("/api/v1/integrations/status").status_code == 401
    response = client.get("/api/v1/integrations/status", headers={"X-API-Key": "tenant-a-test-key"})
    assert response.status_code == 200
    body = response.json()
    assert {item["capability"] for item in body} == set(external_clients.INTEGRATION_SPECS)
    assert all("api_key" not in item and "endpoint" not in item for item in body)
    assert all(item["mode"] == "mock" for item in body)
    assert any(item["status"] == "mock_active" for item in body)
    assert all("message" in item for item in body)
