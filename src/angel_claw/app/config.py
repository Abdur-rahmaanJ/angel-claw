"""
Specify main configs here

Other configs are specified in module's global.py in like
configs = {
   "development": {
       "CONFIG_VAR": "DEVVALUE"
   },
   "production": {
       "CONFIG_VAR": "PRODVALUE"
   },
   "testing": {
       "CONFIG_VAR": "TESTVALUE"
   }
}
"""

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger("angel-claw-app-config")


def _get_default_db_path():
    return f"sqlite:///{Path('~/.angelclaw/angelclaw.db').expanduser()}"


def _secret_key():
    """SECRET_KEY from the environment, or a persisted random one.

    A hardcoded fallback would let anyone forge session cookies and SSO
    tokens, so a missing key is generated once and kept private instead.
    """
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    data_root = Path(os.environ.get("USER_DATA_ROOT", "~/.angelclaw")).expanduser()
    key_file = data_root / "secret_key"
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_hex(32)
        key_file.write_text(key)
        os.chmod(key_file, 0o600)
        logger.warning(
            "SECRET_KEY not set; generated %s (set SECRET_KEY to keep it stable)",
            key_file,
        )
        return key
    except OSError as exc:  # pragma: no cover - read-only data dir
        logger.error("Could not persist SECRET_KEY (%s); using ephemeral key", exc)
        return secrets.token_hex(32)


base_path = os.path.dirname(os.path.abspath(__file__))


class BaseConfig:
    """Parent configuration class."""

    DEBUG = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FLASK_ADMIN_TEMPLATE_MODE = "bootstrap4"
    BASE_DIR = base_path
    STATIC = os.path.join(base_path, "static")
    UPLOADED_PATH_IMAGE = os.path.join(STATIC, "uploads", "images")
    UPLOADED_PATH_THUMB = os.path.join(STATIC, "uploads", "thumbs")

    # Seeding
    SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@admin.com")
    # No default password: app.py generates a random one for the first admin
    # account when this is unset and prints it once.
    SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
    SEED_SETTINGS = {
        "APP_NAME": "Angel Claw",
        "ACTIVE_FRONT_THEME": "blogus",
        "ACTIVE_BACK_THEME": "boogle",
        "CURRENCY": "USD",
    }

    SHOPYO_APPADMIN_URL = "/appadmin"
    SHOPYO_AUTH_URL = "/auth"
    SHOPYO_DASHBOARD_URL = "/dashboard"
    EMAIL_CONFIRMATION_DISABLED = True

    # Session / Persistent Login
    PERMANENT_SESSION_LIFETIME = 31536000  # 1 year in seconds
    REMEMBER_COOKIE_DURATION = 31536000  # 1 year in seconds
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True
    SESSION_PROTECTION = "basic"
    SHOPYO_AUTH_LOGIN_TEMPLATE = "agent/login.html"
    SHOPYO_AUTH_REGISTER_TEMPLATE = "agent/register.html"


class ProductionConfig(BaseConfig):
    """Configurations for production"""

    # built in flask configs
    ENV = "production"
    SECRET_KEY = _secret_key()

    # control email confirmation for user registration
    EMAIL_CONFIRMATION_DISABLED = True

    # flask-mailman configs
    MAIL_SERVER = "smtp.googlemail.com"
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # database configs
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("SQLALCHEMY_DATABASE_URI") or _get_default_db_path()
    )


class DevelopmentConfig(BaseConfig):
    """Configurations for development"""

    # built in flask configs
    ENV = "development"
    DEBUG = True
    LOGIN_DISABLED = False
    SECRET_KEY = "secret"

    # control email confirmation for user registration
    EMAIL_CONFIRMATION_DISABLED = True

    # flask-mailman configs
    MAIL_SERVER = "localhost"
    MAIL_PORT = 1025
    MAIL_USE_TLS = False
    MAIL_USE_SSL = False
    MAIL_USERNAME = ""
    MAIL_PASSWORD = ""
    MAIL_DEFAULT_SENDER = "ma@mail.com"

    # database configs
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("SQLALCHEMY_DATABASE_URI") or _get_default_db_path()
    )

    # unknown configs
    PASSWORD_SALT = "some pasword salt"


class TestingConfig(BaseConfig):
    """Configurations for testsing"""

    # built in flask configs
    ENV = "testing"
    TESTING = True
    DEBUG = True
    SERVER_NAME = "localhost.com"
    SECRET_KEY = "secret"
    PREFERRED_URL_SCHEME = "http"

    # flask WTF configs
    WTF_CSRF_ENABLED = False

    # control email confirmation for user registration
    EMAIL_CONFIRMATION_DISABLED = True

    # flask-mailman configs
    MAIL_BACKEND = "console"
    MAIL_USERNAME = "shopyofrom@test.com"
    MAIL_PASSWORD = "pass"
    MAIL_DEFAULT_SENDER = "shopyofrom@test.com"

    # flask sqlalchemy configs
    # NOTE: tests must never touch the real user DB (~/.angelclaw/angelclaw.db),
    # so TestingConfig defaults to the instance-local testing.db. The env var
    # still wins so test fixtures can point at per-test databases.
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI") or "sqlite:///testing.db"

    # flask bycrpt configs
    BCRYPT_LOG_ROUNDS = 4

    # unknown configs
    PASSWORD_SALT = "some pasword salt"
    LIVESERVER_PORT = 8943
    LIVESERVER_TIMEOUT = 10


app_config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
