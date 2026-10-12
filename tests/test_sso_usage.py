"""SSO + usage-reporting endpoints (ask-moris integration)."""
import json
import os
import tempfile
import uuid

import pytest

from init import db


@pytest.fixture
def app(monkeypatch):
    from app import create_app

    db_file = os.path.join(tempfile.gettempdir(), f"testing_{uuid.uuid4().hex}.db")
    # TestingConfig reads SQLALCHEMY_DATABASE_URI first — setting it before
    # create_app is the only way to actually isolate the engine (a post-hoc
    # app.config override is ignored: the engine is created during app setup).
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_file}")
    app = create_app("testing")
    with app.app_context():
        from angel_claw.config import settings

        settings.auth_mode = "shopyo"

        # Explicitly import models so they register with SQLAlchemy
        import modules.agent.models  # noqa: F401
        import modules.api.models  # noqa: F401

        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    if os.path.exists(db_file):
        os.remove(db_file)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_user(app):
    with app.app_context():
        from shopyo_auth.models import User

        user = User()
        user.email = "test@example.com"
        user.password = "password"  # User model hashes this automatically
        user.is_email_confirmed = True
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return {"id": user.id, "email": user.email}


def _create_api_key(client):
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "password"},
        follow_redirects=True,
    )
    resp = client.post(
        "/api/api-key",
        data=json.dumps({"name": "ask-moris"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["key"]


def test_sso_token_roundtrip(client, auth_user):
    r = client.post(
        "/api/sso/token",
        json={"email": "test@example.com", "password": "password"},
    )
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["status"] == "success"
    assert data["user"]["email"] == "test@example.com"
    assert data["token"]
    assert data["expires_in"] > 0

    v = client.post("/api/sso/verify", json={"token": data["token"]})
    assert v.status_code == 200
    assert v.get_json()["user"]["id"] == data["user"]["id"]

    # tampered token rejected
    bad = client.post("/api/sso/verify", json={"token": data["token"] + "x"})
    assert bad.status_code == 401

    # missing/unknown token rejected
    assert client.post("/api/sso/verify", json={}).status_code == 400


def test_sso_token_bad_credentials(client, auth_user):
    r = client.post(
        "/api/sso/token",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert r.status_code == 401

    r = client.post(
        "/api/sso/token",
        json={"email": "nobody@example.com", "password": "password"},
    )
    assert r.status_code == 401

    r = client.post("/api/sso/token", json={})
    assert r.status_code == 400


def test_usage_requires_api_key(client, auth_user):
    r = client.post("/api/usage", json={"app": "ask-moris", "event": "search"})
    assert r.status_code == 401

    r = client.post(
        "/api/usage",
        json={"app": "ask-moris", "event": "search"},
        headers={"Authorization": "Bearer ac_v1_deadbeef_notakey"},
    )
    assert r.status_code == 401


def test_usage_records_and_summary(client, auth_user, app):
    key = _create_api_key(client)
    headers = {"Authorization": f"Bearer {key}"}
    payload = {
        "app": "ask-moris",
        "event": "search",
        "user": {"id": str(auth_user["id"]), "email": auth_user["email"]},
        "quantity": 2,
        "meta": {"query": "passport", "hits": 8},
    }
    r = client.post("/api/usage", json=payload, headers=headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["status"] == "success"

    with app.app_context():
        from modules.api.models import UsageEvent

        rows = UsageEvent.query.all()
        assert len(rows) == 1
        assert rows[0].app == "ask-moris"
        assert rows[0].event == "search"
        assert rows[0].quantity == 2
        assert rows[0].email == auth_user["email"]
        assert rows[0].reported_by == str(auth_user["id"])
        assert rows[0].meta_json == {"query": "passport", "hits": 8}

    # summary via dashboard session
    s = client.get("/api/usage/summary")
    assert s.status_code == 200
    data = s.get_json()
    assert data["total_events"] == 1
    assert data["total_quantity"] == 2
    assert any(a["app"] == "ask-moris" and a["quantity"] == 2 for a in data["by_app"])
    assert any(e["event"] == "search" for e in data["by_event"])
    assert data["by_user"][0]["email"] == auth_user["email"]
    assert data["recent"][0]["meta"] == {"query": "passport", "hits": 8}
    assert len(data["daily"]) == 1

    # summary via API key (no session)
    s2 = client.get("/api/usage/summary", headers=headers)
    assert s2.status_code == 200


def test_usage_summary_unauthorized(client, auth_user):
    assert client.get("/api/usage/summary").status_code == 401


def test_usage_requires_fields(client, auth_user):
    key = _create_api_key(client)
    headers = {"Authorization": f"Bearer {key}"}
    r = client.post("/api/usage", json={"event": "search"}, headers=headers)
    assert r.status_code == 400
    r = client.post("/api/usage", json={"app": "ask-moris"}, headers=headers)
    assert r.status_code == 400
