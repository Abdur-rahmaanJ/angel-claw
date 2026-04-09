import logging
from typing import Optional, Dict, Any, Protocol

logger = logging.getLogger("angel-claw-engine-credits")

DEFAULT_ACTIONS = [
    {"name": "chat_message", "cost": 1, "description": "Processing a chat message"},
    {"name": "api_call", "cost": 1, "description": "General API call"},
    {"name": "tool_execution", "cost": 2, "description": "Executing a tool"},
    {"name": "workflow_run", "cost": 5, "description": "Running a complete workflow"},
    {
        "name": "telegram_message",
        "cost": 1,
        "description": "Telegram message processed",
    },
    {
        "name": "whatsapp_message",
        "cost": 1,
        "description": "WhatsApp message processed",
    },
]


class CreditServiceProtocol(Protocol):
    """Protocol for credit service - enables dependency injection."""

    def is_enabled(self) -> bool: ...

    async def check_credits(self, user_id: str, action: str) -> tuple[bool, str]: ...

    def deduct_credits(
        self,
        user_id: str,
        action: str,
        metadata: Optional[Dict] = None,
        amount: Optional[int] = None,
    ) -> bool: ...

    def get_balance(self, user_id: str) -> int: ...

    def calculate_token_cost(self, tokens: int) -> int: ...


class CreditService:
    """Credit service with dependency injection support."""

    def __init__(self, settings, db_session_provider=None):
        """
        Args:
            settings: Settings object for configuration
            db_session_provider: Callable that returns a DB session.
                               If None, uses the init.db from angel_claw package.
        """
        self._settings = settings
        self._db_session_provider = db_session_provider

    def _get_db(self):
        if self._db_session_provider:
            return self._db_session_provider()
        from angel_claw.app.init import db

        return db

    def is_enabled(self) -> bool:
        return getattr(self._settings, "credits_enabled", True)

    def _get_action_cost(self, action_name: str) -> int:
        from angel_claw.credits import get_action_cost

        try:
            return get_action_cost(action_name)
        except Exception:
            for action in DEFAULT_ACTIONS:
                if action["name"] == action_name:
                    return action["cost"]
            return 1

    async def check_credits(self, user_id: str, action: str) -> tuple[bool, str]:
        """Check if user has sufficient credits for an action."""
        from angel_claw.credits import check_sufficient_credits as check

        if not self.is_enabled():
            return True, ""

        has_sufficient, balance = check(user_id, action)
        if not has_sufficient:
            cost = self._get_action_cost(action)
            return (
                False,
                f"[SYSTEM: Insufficient credits ({balance}). Please purchase more to continue.]",
            )
        return True, ""

    def deduct_credits(
        self,
        user_id: str,
        action: str,
        metadata: Optional[Dict] = None,
        amount: Optional[int] = None,
    ) -> bool:
        """Deduct credits for a completed action."""
        from angel_claw.credits import deduct_credits as deduct

        if not self.is_enabled():
            return True

        success, msg = deduct(user_id, action, amount=amount, metadata=metadata)
        if not success:
            logger.warning(f"Credit deduction failed for user {user_id}: {msg}")
        return success

    def get_balance(self, user_id: str) -> int:
        """Get current credit balance."""
        from angel_claw.credits import get_balance

        return get_balance(user_id)

    def calculate_token_cost(self, tokens: int) -> int:
        """Calculate credit cost based on token usage."""
        if tokens <= 0:
            return 0
        return (tokens + 999) // 1000


def create_credit_service(settings) -> CreditService:
    """Factory function to create a CreditService."""
    return CreditService(settings)
