from typing import Optional, List
from datetime import datetime
from collections import defaultdict, deque
import logging
import threading
import time
import traceback
from angel_claw.skills.manager import skill
from angel_claw.config import settings

logger = logging.getLogger("angel-claw-messaging")

# Any user may DM any other user; cap that so it cannot become a spam or
# phishing firehose.
CROSS_USER_MESSAGE_LIMIT = 20
CROSS_USER_MESSAGE_WINDOW_SECONDS = 3600
_send_times = defaultdict(deque)
_send_times_lock = threading.Lock()


def _allow_cross_user_send(sender_id: str) -> bool:
    now = time.time()
    with _send_times_lock:
        times = _send_times[sender_id]
        while times and now - times[0] > CROSS_USER_MESSAGE_WINDOW_SECONDS:
            times.popleft()
        if len(times) >= CROSS_USER_MESSAGE_LIMIT:
            return False
        times.append(now)
        return True


@skill
async def send_internal_message(to_user: str, content: str, user_id: str = None) -> str:
    """
    Sends an internal system message/note to another user.

    Parameters:
    - to_user: The email address of the recipient (e.g., "user@example.com")
    - content: The message text to send
    - user_id: (optional) The sender's ID - automatically provided by the system
    """
    logger.info(
        f"send_internal_message called: to_user={to_user}, user_id={user_id}, content={content[:50]}..."
    )

    if not user_id:
        return "Error: Could not determine sender. Please try again."
    if not to_user:
        return "Error: Recipient email is required."
    if not content:
        return "Error: Message content is required."

    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    try:
        with engine._app_context_manager._app_context():
            from shopyo_auth.models import User
            from modules.agent.models import InternalMessage
            from init import db

            recipient = User.get_by_email(to_user)
            if not recipient:
                return f"Error: User '{to_user}' not found."

            if str(recipient.id) != str(user_id) and not _allow_cross_user_send(
                str(user_id)
            ):
                return (
                    "Error: Too many messages to other users. "
                    "Try again later."
                )

            new_msg = InternalMessage(
                sender_id=user_id,
                recipient_id=str(recipient.id),
                recipient_email=to_user,
                content=content,
            )
            db.session.add(new_msg)
            db.session.commit()
            logger.info(
                f"Message committed to DB: sender={user_id}, recipient={recipient.id}"
            )

            try:
                from angel_claw.cron import cron_manager

                sender = db.session.get(User, user_id)
                notification = (
                    f"📬 [Internal Message] From: {sender.email}\n\n{content}"
                )
                await cron_manager._send_proactive_message(
                    notification, str(recipient.id)
                )
            except Exception as e:
                logger.warning(f"Could not send proactive notification: {e}")

            return f"✅ Message delivered to {to_user}."
    except Exception as e:
        logger.error(f"Error sending internal message: {e}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"


@skill
def list_unread_messages(user_id: str, include_read: bool = True) -> List[dict]:
    """
    Lists internal messages for the current user.
    - include_read: If True, returns all messages. If False, returns only unread.
    """
    from angel_claw.engine import AngelClawEngine

    engine = AngelClawEngine()

    with engine._app_context_manager._app_context():
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
                    "sender": sender.email if sender else "Unknown",
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

    with engine._app_context_manager._app_context():
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

    with engine._app_context_manager._app_context():
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

    with engine._app_context_manager._app_context():
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
