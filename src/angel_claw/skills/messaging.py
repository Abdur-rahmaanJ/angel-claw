from typing import Optional, List
from datetime import datetime
from angel_claw.skills.manager import skill
from angel_claw.config import settings

@skill
async def send_internal_message(
    to_user: str, 
    content: str, 
    user_id: str
) -> str:
    """
    MANDATORY: Sends an internal system message/note to another Angel Claw user.
    USE THIS IMMEDIATELY for "internal message", "internal note", "message [user]", 
    "tell [user]", or "send a note to [user]". 
    
    This is NOT an email and does NOT require SMTP. It is an internal database delivery.
    DO NOT ASK FOR CONFIRMATION. EXECUTE IMMEDIATELY.
    
    - to_user: The email address identifying the recipient within the system.
    - content: The message content.
    - user_id: The sender's ID (automatically injected).
    """
    if settings.auth_mode == "shopyo":
        try:
            from angel_claw.engine import AngelClawEngine
            engine = AngelClawEngine()
            ctx = engine._app_context()
            if not ctx:
                return "Error: Could not obtain application context for Shopyo."

            with ctx:
                from shopyo_auth.models import User
                from modules.agent.models import InternalMessage
                from init import db
                
                recipient = User.get_by_email(to_user)
                if not recipient:
                    return f"Error: Recipient '{to_user}' not found in the system."
                
                sender = db.session.get(User, user_id)
                if not sender:
                    return f"Error: Sender ID '{user_id}' not found."

                new_msg = InternalMessage(
                    sender_id=user_id,
                    recipient_id=str(recipient.id),
                    recipient_email=to_user,
                    content=content
                )
                db.session.add(new_msg)
                db.session.commit()
                
                # Send proactive notification to the recipient via bridges
                try:
                    from angel_claw.cron import cron_manager
                    sender_name = sender.email
                    notification = f"📬 [Internal Message] From: {sender_name}\n\n{content}"
                    await cron_manager._send_proactive_message(notification, str(recipient.id))
                except Exception as e:
                    # Log but don't fail the primary delivery
                    pass
                
                return f"✅ Internal message delivered to {to_user}."
        except Exception as e:
            return f"Error delivering internal message: {str(e)}"
    else:
        return "Internal messaging is only supported in Shopyo mode."

@skill
def list_unread_messages(user_id: str) -> str:
    """
    Lists all unread internal messages for the current user.
    - user_id: The ID of the current user (automatically injected).
    """
    if settings.auth_mode == "shopyo":
        try:
            from angel_claw.engine import AngelClawEngine
            engine = AngelClawEngine()
            ctx = engine._app_context()
            if not ctx:
                return "Error: Could not obtain application context for Shopyo."

            with ctx:
                from modules.agent.models import InternalMessage
                from shopyo_auth.models import User
                from init import db
                
                unread = InternalMessage.query.filter_by(
                    recipient_id=user_id,
                    is_read=False
                ).order_by(InternalMessage.created_at.desc()).all()
                
                if not unread:
                    return "You have no unread messages."
                
                lines = ["## Unread Messages"]
                for msg in unread:
                    sender = db.session.get(User, msg.sender_id)
                    sender_name = sender.email if sender else "Unknown"
                    time_str = msg.created_at.strftime("%Y-%m-%d %H:%M")
                    lines.append(f"- **From {sender_name}** ({time_str}): {msg.content}")
                    
                return "\n".join(lines)
        except Exception as e:
            return f"Error listing messages: {str(e)}"
    else:
        return "Internal messaging is only supported in Shopyo mode for now."

@skill
def mark_messages_as_read(user_id: str) -> str:
    """
    Marks all unread messages as read for the current user.
    - user_id: The ID of the current user (automatically injected).
    """
    if settings.auth_mode == "shopyo":
        try:
            from angel_claw.engine import AngelClawEngine
            engine = AngelClawEngine()
            ctx = engine._app_context()
            if not ctx:
                return "Error: Could not obtain application context for Shopyo."

            with ctx:
                from modules.agent.models import InternalMessage
                from init import db
                
                unread = InternalMessage.query.filter_by(
                    recipient_id=user_id,
                    is_read=False
                ).all()
                
                if not unread:
                    return "No unread messages to mark as read."
                
                for msg in unread:
                    msg.is_read = True
                
                db.session.commit()
                return f"✅ Marked {len(unread)} messages as read."
        except Exception as e:
            return f"Error marking messages: {str(e)}"
    else:
        return "Internal messaging is only supported in Shopyo mode for now."
