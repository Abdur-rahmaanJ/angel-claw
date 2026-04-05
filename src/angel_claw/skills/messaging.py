from typing import Optional, List
from datetime import datetime
from angel_claw.skills.manager import skill
from angel_claw.config import settings


@skill
async def send_internal_message(to_user: str, content: str, user_id: str) -> str:
    """
    Sends an internal system message/note to another user.
    - to_user: The email address identifying the recipient.
    - content: The message content.
    - user_id: The sender's ID (automatically injected).
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context():
        from shopyo_auth.models import User
        from modules.agent.models import InternalMessage
        from init import db

        recipient = User.get_by_email(to_user)
        if not recipient:
            return f"Error: User '{to_user}' not found."

        new_msg = InternalMessage(
            sender_id=user_id,
            recipient_id=str(recipient.id),
            recipient_email=to_user,
            content=content,
        )
        db.session.add(new_msg)
        db.session.commit()

        try:
            from angel_claw.cron import cron_manager

            sender = db.session.get(User, user_id)
            notification = f"📬 [Internal Message] From: {sender.email}\n\n{content}"
            await cron_manager._send_proactive_message(notification, str(recipient.id))
        except Exception:
            pass

        return f"✅ Message delivered to {to_user}."


@skill
def list_unread_messages(user_id: str, include_read: bool = True) -> List[dict]:
    """
    Lists internal messages for the current user.
    - include_read: If True, returns all messages. If False, returns only unread.
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context():
        from modules.agent.models import InternalMessage
        from shopyo_auth.models import User
        from init import db

        if include_read:
            messages = (
                InternalMessage.query.filter_by(recipient_id=user_id)
                .order_by(InternalMessage.created_at.desc())
                .all()
            )
        else:
            messages = (
                InternalMessage.query.filter_by(recipient_id=user_id, is_read=False)
                .order_by(InternalMessage.created_at.desc())
                .all()
            )

        results = []
        for msg in messages:
            sender = db.session.get(User, msg.sender_id)
            results.append(
                {
                    "id": msg.id,
                    "from": sender.email if sender else "Unknown",
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "is_read": msg.is_read,
                }
            )
        return results


@skill
def mark_messages_as_read(user_id: str) -> str:
    """
    Marks all unread messages as read for the current user.
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context():
        from modules.agent.models import InternalMessage
        from init import db

        unread = InternalMessage.query.filter_by(
            recipient_id=user_id, is_read=False
        ).all()
        for msg in unread:
            msg.is_read = True
        db.session.commit()
        return f"✅ Marked {len(unread)} messages as read."


@skill
def delete_internal_message(message_id: int, user_id: str) -> str:
    """
    Deletes an internal message by its ID.
    - message_id: The ID of the message to delete.
    - user_id: The current user ID (automatically injected).
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context():
        from modules.agent.models import InternalMessage
        from init import db

        msg = db.session.get(InternalMessage, message_id)
        if not msg:
            return f"Error: Message {message_id} not found."

        if str(msg.recipient_id) != str(user_id) and str(msg.sender_id) != str(user_id):
            return "Error: Permission denied."

        db.session.delete(msg)
        db.session.commit()
        return f"🗑️ Message deleted."


@skill
def mark_message_as_read(message_id: int, user_id: str) -> str:
    """
    Marks a single message as read.
    - message_id: The ID of the message to mark as read.
    - user_id: The current user ID (automatically injected).
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context():
        from modules.agent.models import InternalMessage
        from init import db

        msg = db.session.get(InternalMessage, message_id)
        if not msg:
            return f"Error: Message {message_id} not found."

        if str(msg.recipient_id) != str(user_id):
            return "Error: Permission denied."

        msg.is_read = True
        db.session.commit()
        return f"✅ Message marked as read."
