import pytest

from app.config import parse_cors_origins
from conftest import KEY_B, auth


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_allowed_preflight_has_explicit_origin_methods_and_headers(api, origin):
    client, _, _ = api
    response = client.options(
        "/api/v1/overview",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert set(response.headers["access-control-allow-methods"].split(", ")) >= {"GET", "POST", "OPTIONS"}
    assert set(response.headers["access-control-allow-headers"].lower().split(", ")) >= {"content-type", "x-api-key"}
    assert "access-control-allow-credentials" not in response.headers


def test_unapproved_origin_does_not_receive_approval_header(api):
    client, _, _ = api
    response = client.get("/healthz", headers={"Origin": "https://unapproved.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_does_not_bypass_auth_tenant_scope_or_validation(api):
    client, _, _ = api
    assert client.get("/healthz", headers={"Origin": "http://localhost:5173"}).json() == {
        "status": "ok", "mode": "synthetic-demo"
    }
    assert client.get("/api/v1/overview", headers={"Origin": "http://localhost:5173"}).status_code == 401
    foreign = client.post(
        "/api/v1/simulate",
        headers={**auth(KEY_B), "Origin": "http://localhost:5173"},
        json={"facility_code": "A-01", "baseline_demand_beds": 10},
    )
    assert foreign.status_code == 404
    invalid = client.post(
        "/api/v1/simulate",
        headers={**auth(), "Origin": "http://localhost:5173"},
        json={"facility_code": "A-01", "baseline_demand_beds": "not-an-integer"},
    )
    assert invalid.status_code == 422


@pytest.mark.parametrize("raw", ["*", "localhost:5173", "http://localhost:5173/path", "http://localhost:5173,"])
def test_malformed_cors_configuration_is_rejected(raw):
    with pytest.raises(RuntimeError):
        parse_cors_origins(raw)
