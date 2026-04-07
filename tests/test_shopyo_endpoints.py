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
def app():
    from app import create_app
    import uuid
    import os
    db_file = f"testing_{uuid.uuid4().hex}.db"
    db_path = f"sqlite:///{db_file}"
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
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
    assert len(data["token"]) == 8

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
    assert "api_key" in data
    assert data["api_key"].startswith("ac_v1_")

def test_registration_template(client, app):
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
