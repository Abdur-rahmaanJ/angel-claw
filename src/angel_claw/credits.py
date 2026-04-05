import logging
from typing import Optional, Dict, Any
from init import db
from angel_claw.app.modules.agent.models import (
    UserCredit,
    CreditAction,
)

logger = logging.getLogger("angel-claw-credits")

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


def credits_enabled() -> bool:
    """Check if credits system is enabled."""
    try:
        from angel_claw.config.settings import settings

        return getattr(settings, "credits_enabled", True)
    except Exception:
        return True


def init_default_actions():
    """Initialize default credit actions in the database."""
    for action in DEFAULT_ACTIONS:
        existing = CreditAction.query.filter_by(name=action["name"]).first()
        if not existing:
            credit_action = CreditAction(
                name=action["name"],
                cost=action["cost"],
                description=action["description"],
                is_active=True,
            )
            db.session.add(credit_action)
    db.session.commit()


def get_action_cost(action_name: str) -> int:
    """Get the cost of a specific action."""
    return CreditAction.get_cost(action_name)


def deduct_credits(
    user_id: str,
    action: str,
    metadata: Optional[Dict] = None,
    allow_negative: bool = False,
) -> tuple[bool, str]:
    """
    Deduct credits for a given action.
    Uses model methods for logic and atomicity (via session management).
    """
    try:
        cost = get_action_cost(action)
        # Use with_for_update for atomicity
        credit = (
            db.session.query(UserCredit)
            .filter_by(user_id=user_id)
            .with_for_update()
            .first()
        )

        if not credit:
            return False, "User credits not found"

        success, msg = credit.deduct_credits(
            cost, action, meta=metadata, allow_negative=allow_negative
        )
        if success:
            logger.info(
                f"Credits deducted: user={user_id}, amount={cost}, action={action}, new_balance={credit.balance}"
            )
        return success, msg

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Credit deduction failed: user={user_id}, action={action}, error={e}"
        )
        return False, f"Credit deduction failed: {str(e)}"


def add_credits(
    user_id: str, amount: int, reason: str = "manual", metadata: Optional[Dict] = None
) -> tuple[bool, str]:
    """
    Add credits to a user's account.
    """
    try:
        credit = UserCredit.get_or_create(user_id)
        credit.add_credits(amount, reason, meta=metadata)
        logger.info(
            f"Credits added: user={user_id}, amount={amount}, reason={reason}, new_balance={credit.balance}"
        )
        return True, "Success"
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Credit addition failed: user={user_id}, amount={amount}, error={e}"
        )
        return False, f"Credit addition failed: {str(e)}"


def get_balance(user_id: str) -> int:
    """Get current credit balance for a user."""
    credit = UserCredit.query.filter_by(user_id=user_id).first()
    return credit.balance if credit else 0


def check_sufficient_credits(user_id: str, action: str) -> tuple[bool, int]:
    """
    Check if user has enough credits for an action.
    Returns (has_sufficient, current_balance)
    """
    cost = get_action_cost(action)
    balance = get_balance(user_id)
    return balance >= cost, balance


def get_user_stats(user_id: str) -> Dict[str, Any]:
    """Get credit statistics for a user, initializing them if they don't exist."""
    from angel_claw.app.modules.agent.models import CreditTransaction
    from angel_claw.config.settings import settings

    credit = UserCredit.query.filter_by(user_id=user_id).first()
    if not credit:
        initial = getattr(settings, "initial_free_credits", 100)
        credit = UserCredit.get_or_create(user_id, initial=initial)

    transactions_count = CreditTransaction.query.filter_by(user_id=user_id).count()

    return {
        "balance": credit.balance,
        "lifetime_spent": credit.lifetime_spent,
        "transactions_count": transactions_count,
        "updated_at": credit.updated_at.isoformat() if credit.updated_at else None,
    }
