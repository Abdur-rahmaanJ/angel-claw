import logging
import hashlib
import secrets
from datetime import datetime, UTC
from typing import Optional, Protocol
from ..models import UserContext

logger = logging.getLogger("angel-claw-engine-apikeys")


class ApiKeyServiceProtocol(Protocol):
    """Protocol for API key service - enables dependency injection."""

    def create_api_key(self, context: UserContext, name: str) -> str: ...

    def revoke_api_key(self, context: UserContext, key_id: str): ...

    def validate_api_key(self, raw_key: str) -> Optional[UserContext]: ...


class ApiKeyService:
    """API key service for managing API keys with DI support."""

    def __init__(self, settings, app_context_manager):
        self._settings = settings
        self._app_context_manager = app_context_manager

    def create_api_key(self, context: UserContext, name: str) -> str:
        """Create a new API key for a user."""
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError("API Key creation only supported in Shopyo mode")

        with self._app_context_manager._app_context() as ctx:
            if not ctx:
                raise RuntimeError("Could not load app context")

            from modules.agent.models import ApiKey
            from init import db

            prefix = secrets.token_hex(4)
            random_part = secrets.token_urlsafe(32)
            raw_key = f"ac_v1_{prefix}_{random_part}"

            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

            api_key = ApiKey(
                user_id=context.user_id, name=name, key_hash=key_hash, prefix=prefix
            )
            db.session.add(api_key)
            db.session.commit()
            return raw_key

    def revoke_api_key(self, context: UserContext, key_id: str):
        """Revoke an API key."""
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError(
                "API Key revocation only supported in Shopyo mode"
            )

        with self._app_context_manager._app_context():
            try:
                from modules.agent.models import ApiKey
                from init import db

                api_key = ApiKey.query.filter_by(
                    id=key_id, user_id=context.user_id
                ).first()
                if api_key:
                    api_key.is_active = False
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error revoking API key: {e}")

    def validate_api_key(self, raw_key: str) -> Optional[UserContext]:
        """Validate an API key and return user context if valid."""
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError(
                "API Key validation only supported in Shopyo mode"
            )

        with self._app_context_manager._app_context() as ctx:
            if not ctx:
                return None

            import hashlib
            from modules.agent.models import ApiKey
            from shopyo_auth.models import User
            from init import db

            parts = raw_key.split("_")
            if len(parts) < 4:
                return None
            prefix = parts[2]

            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

            api_key = ApiKey.query.filter_by(
                prefix=prefix, key_hash=key_hash, is_active=True
            ).first()

            if api_key:
                user = User.query.get(api_key.user_id)
                if user:
                    api_key.last_used_at = datetime.now(UTC)
                    db.session.commit()

                    return UserContext(
                        user_id=str(user.id),
                        email=user.email,
                        roles=[r.name for r in user.roles]
                        if hasattr(user, "roles")
                        else [],
                        channel_type="api",
                        channel_identifier="api-key",
                        is_admin=getattr(user, "is_admin", False),
                    )
            return None


def create_api_key_service(settings, app_context_manager) -> ApiKeyService:
    return ApiKeyService(settings, app_context_manager)
