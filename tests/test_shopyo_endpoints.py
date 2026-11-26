import pytest
import os
import json
import asyncio
from unittest.mock import patch, AsyncMock
from flask import url_for
from flask_login import login_user
from init import db
from shopyo_auth.models import User
from angel_claw.models import EngineResponse

@pytest.fixture
def app(monkeypatch):
    from app import create_app
    import uuid
    import os
    db_file = f"testing_{uuid.uuid4().hex}.db"
    # Set the URI *before* create_app: the engine is created during app setup,
    # so a post-hoc app.config override is ignored (it would otherwise hit
    # ~/.angelclaw/angelclaw.db — the real user database).
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{os.path.abspath(db_file)}")
    app = create_app("testing")
    with app.app_context():
        # Ensure auth_mode is shopyo for these tests
        from angel_claw.config import settings
        settings.auth_mode = "shopyo"
        
        # Explicitly import models to ensure they are registered with SQLAlchemy
        import modules.agent.models
        
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
        user = User()
        user.email = "test@example.com"
        user.password = "password" # User model hashes this automatically in setter
        user.is_email_confirmed = True
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return {"id": user.id, "email": user.email}

def test_root_access(client, auth_user, app):
    # Login
    client.post("/auth/login", data={
        "email": "test@example.com",
        "password": "password"
    }, follow_redirects=True)
    response = client.get("/")
    assert response.status_code == 200

def test_seed_admin(client, app):
    # Run the seed command manually via app.cli
    from click.testing import CliRunner
    runner = app.test_cli_runner()
    result = runner.invoke(args=["shopyo-seed"])
    assert result.exit_code == 0
    
    # Verify user exists and has roles
    from shopyo_auth.models import User, Role
    with app.app_context():
        user = User.query.filter_by(email="admin@admin.com").first()
        assert user is not None
        assert user.is_admin is True
        role_names = [r.name for r in user.roles]
        assert "admin" in role_names
        assert "user" in role_names

def test_chat_endpoint(client, auth_user, app):
    # Mock AngelClawEngine.execute globally
    with patch("angel_claw.engine.AngelClawEngine.execute", new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = EngineResponse(content="Hello from mock!", tool_calls=[])
        
        # Manually login user using the real login endpoint
        login_response = client.post("/auth/login", data={
            "email": "test@example.com",
            "password": "password"
        }, follow_redirects=True)        
        # Check if login was successful by seeing if we can access the index
        index_response = client.get("/")
        assert index_response.status_code == 200
        
        chat_response = client.post("/chat", 
            data=json.dumps({"message": "Hi"}),
            content_type="application/json"
        )
        
        assert chat_response.status_code == 200
        data = chat_response.get_json()
        assert data["response"] == "Hello from mock!"
        assert "tool_calls" in data

def test_pair_token_endpoint(client, auth_user, app):
    # Login
    client.post("/auth/login", data={
        "email": "test@example.com",
        "password": "password"
    }, follow_redirects=True)
    
    response = client.post("/pair-token")
    if response.status_code != 200:
        print(response.get_json())
    assert response.status_code == 200
    data = response.get_json()
    assert "token" in data
    assert len(data["token"]) == 12
    assert data["token"].isdigit()

def test_mobile_command_is_limited_to_own_user(client, auth_user):
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "password"},
        follow_redirects=True,
    )
    forbidden = client.post(
        "/api/mobile/command/add",
        json={"user_id": "99999", "command": {"type": "click", "params": {}}},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/api/mobile/command/add",
        json={"command": {"type": "click", "params": {}}},
    )
    assert allowed.status_code == 200


def test_api_key_endpoint(client, auth_user, app):
    # Login
    client.post("/auth/login", data={
        "email": "test@example.com",
        "password": "password"
    }, follow_redirects=True)
    
    response = client.post("/api-key",
        data=json.dumps({"name": "Test Key"}),
        content_type="application/json"
    )
    if response.status_code != 200:
        print(response.get_json())
    assert response.status_code == 200
    data = response.get_json()
    # /api/api-key returns the raw key under "key"
    assert "key" in data
    assert data["key"].startswith("ac_v1_")

def test_registration_disabled_by_default(client, app):
    assert client.get("/auth/register").status_code == 404


def test_registration_template(client, app, monkeypatch):
    from angel_claw.config import settings

    monkeypatch.setattr(settings, "allow_registration", True)
    response = client.get("/auth/register")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Angel Claw" in html
    assert "Create your account" in html
    assert "register-card" in html

def test_login_template(client, app):
    response = client.get("/auth/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Angel Claw" in html
    assert "Login" in html


def test_scheduled_prompt_lands_in_tasks_and_messages(
    client, auth_user, app, monkeypatch, tmp_path
):
    """A future prompt is a Tasks row; its result is one Messages entry.

    Reminders are the exception: they stay in the Reminders tab and must not
    create an inbox message when they fire.
    """
    from datetime import datetime, timedelta
    from unittest.mock import AsyncMock

    from angel_claw.cron import Job, JobPayload, JobSchedule, cron_manager
    from angel_claw.models import EngineResponse
    from init import db
    from modules.agent.models import InternalMessage, Reminder

    class FakeEngine:
        async def execute(self, context, message):
            assert "table" in message.lower()
            return EngineResponse(
                content="Found a table for six at Test Bistro: https://example.com/book"
            )

    monkeypatch.setattr("angel_claw.engine.AngelClawEngine", FakeEngine)
    monkeypatch.setattr(cron_manager, "_send_proactive_message", AsyncMock())

    old_dir, old_jobs = cron_manager.persist_dir, cron_manager.jobs
    cron_manager.persist_dir = str(tmp_path)
    cron_manager.jobs = {}
    try:
        login = client.post(
            "/auth/login",
            data={"email": "test@example.com", "password": "password"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        with app.app_context():
            user_id = str(auth_user["id"])
            when = (datetime.now() + timedelta(minutes=5)).isoformat()
            job = Job(
                name="restaurant_table_check",
                schedule=JobSchedule(kind="at", value=when),
                payload=JobPayload(
                    kind="prompt",
                    content="Find a table for six at a restaurant tomorrow and report it.",
                ),
                session_id="Thread 1",
                user_id=user_id,
            )
            cron_manager.save_job(job)

            tasks = client.get("/cron/jobs").get_json()["jobs"]
            assert "restaurant_table_check" in {t["name"] for t in tasks}

            asyncio.run(
                cron_manager._execute_job(cron_manager.jobs["restaurant_table_check"])
            )
            messages = InternalMessage.query.filter_by(recipient_id=user_id).all()
            assert any("Test Bistro" in m.content for m in messages)
            assert any(m.content.startswith("⏰") for m in messages)

            # A reminder must stay out of Tasks and out of the inbox.
            reminder_name = f"reminder_{user_id}_{int(datetime.now().timestamp())}"
            reminder_job = Job(
                name=reminder_name,
                schedule=JobSchedule(kind="at", value=when),
                payload=JobPayload(
                    kind="message", content="🔔 REMINDER: table for six"
                ),
                session_id="Thread 1",
                user_id=user_id,
            )
            cron_manager.save_job(reminder_job)
            reminder = Reminder(
                user_id=user_id,
                message="table for six",
                remind_at=datetime.now() + timedelta(minutes=5),
                channel_type="web",
                channel_identifier="Thread 1",
                job_name=reminder_name,
            )
            db.session.add(reminder)
            db.session.commit()

            tasks = client.get("/cron/jobs").get_json()["jobs"]
            assert reminder_name not in {t["name"] for t in tasks}

            before = InternalMessage.query.filter_by(recipient_id=user_id).count()
            asyncio.run(
                cron_manager._execute_job(cron_manager.jobs[reminder_name])
            )
            db.session.refresh(reminder)
            assert reminder.is_sent is True
            assert InternalMessage.query.filter_by(recipient_id=user_id).count() == before
    finally:
        cron_manager.persist_dir = old_dir
        cron_manager.jobs = old_jobs
        cron_manager.scheduler.remove_all_jobs()
