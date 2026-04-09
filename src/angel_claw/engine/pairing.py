import logging
import secrets
from datetime import datetime, UTC, timedelta
from typing import Optional, Protocol
from ..models import UserContext

logger = logging.getLogger("angel-claw-engine-pairing")


class PairingServiceProtocol(Protocol):
    """Protocol for pairing service - enables dependency injection."""

    def pair_channel(
        self, context: UserContext, channel_type: str, identifier: str
    ): ...

    def generate_pair_token(self, context: UserContext) -> str: ...

    def validate_pair_token(self, token: str) -> Optional[str]: ...


class PairingService:
    """Pairing service for managing channel pairing and tokens with DI support."""

    def __init__(self, settings, app_context_manager):
        self._settings = settings
        self._app_context_manager = app_context_manager

    def pair_channel(self, context: UserContext, channel_type: str, identifier: str):
        """Pair a channel with a user."""
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError("Channel pairing only supported in Shopyo mode")

        with self._app_context_manager._app_context():
            try:
                from modules.agent.models import Channel
                from init import db

                channel = Channel.query.filter_by(
                    channel_type=channel_type, channel_identifier=identifier
                ).first()

                if not channel:
                    channel = Channel(
                        user_id=context.user_id,
                        channel_type=channel_type,
                        channel_identifier=identifier,
                        is_active=True,
                    )
                    db.session.add(channel)
                else:
                    channel.user_id = context.user_id
                    channel.last_seen_at = datetime.now(UTC)
                    channel.is_active = True

                db.session.commit()
            except Exception as e:
                logger.error(f"Error pairing channel: {e}")

    def generate_pair_token(self, context: UserContext) -> str:
        """Generate a pairing token for a user."""
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError(
                "Pairing token generation only supported in Shopyo mode"
            )

        with self._app_context_manager._app_context() as ctx:
            if ctx is None:
                raise RuntimeError("Could not load app context")

            from modules.agent.models import PairingToken
            from init import db

            token = "".join([str(secrets.randbelow(10)) for _ in range(8)])

            pairing_token = PairingToken(
                token=token,
                user_id=context.user_id,
                expires_at=datetime.now() + timedelta(minutes=10),
            )
            db.session.add(pairing_token)
            db.session.commit()
            return token

    def validate_pair_token(self, token: str) -> Optional[str]:
        """Validate a pairing token and return user_id if valid."""
        logger.info(f"Engine: Validating token {token}")
        if self._settings.auth_mode != "shopyo":
            raise NotImplementedError(
                "Pairing token validation only supported in Shopyo mode"
            )

        with self._app_context_manager._app_context() as ctx:
            if not ctx:
                logger.error("Engine: Could not get app context for token validation")
                return None

            from modules.agent.models import PairingToken
            from init import db

            logger.info(f"Engine: Searching for token {token} in DB")
            pairing_token = PairingToken.query.filter_by(
                token=token, consumed=False
            ).first()

            if pairing_token:
                logger.info(
                    f"Engine: Found token. Expires at: {pairing_token.expires_at}"
                )
                if pairing_token.expires_at > datetime.now():
                    user_id = pairing_token.user_id
                    pairing_token.consumed = True
                    db.session.commit()
                    logger.info(f"Engine: Token valid for user {user_id}")
                    return user_id
                else:
                    logger.warning("Engine: Token expired")
            else:
                logger.warning("Engine: Token not found or already consumed")
            return None


def create_pairing_service(settings, app_context_manager) -> PairingService:
    return PairingService(settings, app_context_manager)
