import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient

from api import auth, health
from main import app
from services import token_cache


@pytest.fixture
def redis_client(monkeypatch):
    client = fakeredis.FakeRedis()
    monkeypatch.setattr(token_cache, "get_redis", lambda: client)
    return client


def test_cache_roundtrip_stores_hash_not_token(redis_client):
    token_cache.cache_user("secret-token", {"id": "u1"})
    assert token_cache.get_cached_user("secret-token") == {"id": "u1"}
    assert token_cache.get_cached_user("other-token") is None
    assert all(b"secret-token" not in key for key in redis_client.keys("*"))
    assert 0 < redis_client.ttl(next(iter(redis_client.keys("*")))) <= token_cache.TOKEN_TTL_SECONDS


def test_supabase_called_once_for_repeated_token(redis_client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return httpx.Response(200, json={"id": "u1", "email": "a@b.c"})

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    assert auth._supabase_user_from_token("tok")["id"] == "u1"
    assert auth._supabase_user_from_token("tok")["id"] == "u1"
    assert len(calls) == 1


def test_rejected_token_is_not_cached(redis_client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: httpx.Response(401))
    with pytest.raises(Exception):
        auth._supabase_user_from_token("bad")
    assert token_cache.get_cached_user("bad") is None


def test_redis_down_falls_back_to_supabase(monkeypatch):
    def broken():
        raise ConnectionError("down")

    monkeypatch.setattr(token_cache, "get_redis", broken)
    assert token_cache.get_cached_user("tok") is None
    token_cache.cache_user("tok", {"id": "u1"})  # must not raise


def test_liveness_is_always_ok():
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}


def test_readiness_503_when_a_dependency_fails(monkeypatch):
    monkeypatch.setattr(health, "_check_database", lambda: None)
    monkeypatch.setattr(health, "_check_redis", lambda: "ok")
    monkeypatch.setattr(health, "_check_storage", lambda: "local disk")
    monkeypatch.setattr(health, "_check_supabase", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    response = TestClient(app).get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["supabase"] == "failed: RuntimeError"
    assert response.json()["checks"]["database"] == "ok"


def test_readiness_200_when_all_ok(monkeypatch):
    monkeypatch.setattr(health, "_check_database", lambda: None)
    monkeypatch.setattr(health, "_check_redis", lambda: "not configured")
    monkeypatch.setattr(health, "_check_storage", lambda: "local disk")
    monkeypatch.setattr(health, "_check_supabase", lambda: None)
    assert TestClient(app).get("/api/health/ready").status_code == 200
