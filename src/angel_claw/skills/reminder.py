import logging
from datetime import datetime
from typing import Optional, List
from dateutil import parser
from asgiref.sync import async_to_sync

from angel_claw.skills.manager import skill
from angel_claw.cron import cron_manager, Job, JobSchedule, JobPayload
from angel_claw.models import UserContext

logger = logging.getLogger("angel-claw-skill-reminder")

@skill
def add_reminder(message: str, time_str: str, session_id: str = "web-default", user_id: Optional[str] = None) -> str:
    """
    Adds a reminder for the user.
    Args:
        message: The reminder message.
        time_str: When to remind (e.g., "in 5 minutes", "tomorrow at 3pm", "2026-04-21 15:00:00").
        session_id: The session/channel identifier.
        user_id: The user ID.
    """
    if not user_id:
        return "Error: user_id is required to set a reminder."

    try:
        # Try to parse the time_str
        # Note: dateutil.parser is good for absolute times. 
        # For relative times like "in 5 minutes", we might need more logic or just assume ISO/absolute for now
        # given the LLM usually converts relative to absolute if instructed.
        remind_at = parser.parse(time_str, fuzzy=True)
        if remind_at < datetime.now():
            # If it's in the past and only time was provided, maybe it's for tomorrow
            if remind_at.date() == datetime.now().date():
                from datetime import timedelta
                remind_at += timedelta(days=1)
            else:
                return f"Error: The time '{time_str}' (parsed as {remind_at}) is in the past."
    except Exception as e:
        return f"Error parsing time '{time_str}': {str(e)}"

    # Determine channel type from session_id or context
    # In our bridges, session_id for telegram is numeric chat_id. 
    # For web it usually contains "web" or "Thread".
    channel_type = "web"
    if session_id.isdigit() or len(session_id) > 5 and session_id[0].isdigit():
        channel_type = "telegram"
    elif "web" in session_id.lower() or "thread" in session_id.lower():
        channel_type = "web"

    # 1. Create Cron Job
    job_name = f"reminder_{user_id}_{datetime.now().timestamp()}"
    
    payload_content = message
    if channel_type == "web":
        # For web, we might want to prefix or wrap it so the UI knows it's a reminder
        payload_content = f"🔔 REMINDER: {message}"

    job = Job(
        name=job_name,
        schedule=JobSchedule(kind="at", value=remind_at.isoformat()),
        payload=JobPayload(kind="message", content=payload_content),
        session_id=session_id,
        user_id=user_id
    )
    
    async_to_sync(cron_manager.save_job_async)(job)

    # 2. Store in DB for UI visibility
    try:
        from init import db
        from modules.agent.models import Reminder
        
        # We need an app context to use the DB
        from flask import current_app
        if current_app:
            reminder = Reminder(
                user_id=user_id,
                message=message,
                remind_at=remind_at,
                channel_type=channel_type,
                channel_identifier=session_id,
                job_name=job_name
            )
            db.session.add(reminder)
            db.session.commit()
    except Exception as e:
        logger.error(f"Error saving reminder to DB: {e}")
        # We still scheduled the cron job, so it will work, just not show in UI list until refreshed/fixed

    return f"✅ Reminder set: '{message}' for {remind_at.strftime('%Y-%m-%d %H:%M:%S')}"

@skill
def list_reminders(user_id: Optional[str] = None) -> str:
    """Lists all upcoming reminders for the user."""
    if not user_id:
        return "Error: user_id is required."

    try:
        from modules.agent.models import Reminder
        from flask import current_app
        if current_app:
            reminders = Reminder.query.filter_by(user_id=user_id, is_sent=False).order_by(Reminder.remind_at).all()
            if not reminders:
                return "You have no upcoming reminders."
            
            lines = ["## Your Upcoming Reminders:"]
            for r in reminders:
                lines.append(f"- {r.remind_at.strftime('%Y-%m-%d %H:%M')}: {r.message}")
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
    
    return "Error: Could not retrieve reminders from database."
