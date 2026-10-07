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
    """
    if not user_id:
        return "Error: user_id is required to set a reminder."

    try:
        import re
        from datetime import timedelta
        
        # Use simple logic for 'in X minutes'
        match = re.search(r'in\s+(\d+)\s+(min|minute|minutes)', time_str.lower())
        if match:
            minutes = int(match.group(1))
            remind_at = datetime.now() + timedelta(minutes=minutes)
        else:
            # Fallback to dateutil for absolute times
            remind_at = parser.parse(time_str, fuzzy=True)
            
        # Round to nearest minute for comparison
        remind_at = remind_at.replace(second=0, microsecond=0)
        
        if remind_at < datetime.now().replace(second=0, microsecond=0):
            # If it's in the past and only time was provided, maybe it's for tomorrow
            if remind_at.date() == datetime.now().date():
                remind_at += timedelta(days=1)
            else:
                return f"Error: The time '{time_str}' (parsed as {remind_at}) is in the past."
    except Exception as e:
        return f"Error parsing time '{time_str}': {str(e)}"

    # Determine channel type
    channel_type = "web"
    if session_id.isdigit() or len(session_id) > 5 and session_id[0].isdigit():
        channel_type = "telegram"
    elif "web" in session_id.lower() or "thread" in session_id.lower():
        channel_type = "web"

    # 1. Prevent Duplicates
    try:
        from angel_claw.config import settings
        from angel_claw.engine.app_context import create_app_context_manager
        
        ctx_manager = create_app_context_manager(settings)
        with ctx_manager._app_context():
            from modules.agent.models import Reminder
            # Check if a similar reminder exists in the next 60 seconds
            existing = Reminder.query.filter(
                Reminder.user_id == user_id,
                Reminder.message == message,
                Reminder.is_sent == False,
                Reminder.remind_at >= remind_at,
                Reminder.remind_at < remind_at + timedelta(seconds=60)
            ).first()
            if existing:
                return f"⚠️ A reminder for '{message}' already exists at {existing.remind_at.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as e:
        logger.error(f"Error checking for existing reminder: {e}")

    # 2. Create Cron Job
    job_name = f"reminder_{user_id}_{remind_at.timestamp()}"
    
    payload_content = message
    if channel_type == "web":
        payload_content = f"🔔 REMINDER: {message}"

    job = Job(
        name=job_name,
        schedule=JobSchedule(kind="at", value=remind_at.isoformat()),
        payload=JobPayload(kind="message", content=payload_content),
        session_id=session_id,
        user_id=user_id
    )
    
    async_to_sync(cron_manager.save_job_async)(job)

    # 3. Store in DB
    try:
        with ctx_manager._app_context():
            from init import db
            from modules.agent.models import Reminder
            
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
            logger.info(f"Reminder saved to DB: {message}")
    except Exception as e:
        logger.error(f"Error saving reminder to DB: {e}", exc_info=True)

    return f"✅ Reminder set: '{message}' for {remind_at.strftime('%Y-%m-%d %H:%M:%S')}"

@skill
def list_reminders(user_id: Optional[str] = None) -> str:
    """Lists all upcoming reminders for the user."""
    if not user_id:
        # Fallback to check if we can get user from session if user_id not provided
        try:
            from flask import current_user
            if current_user and current_user.is_authenticated:
                user_id = str(current_user.id)
        except: pass
        
    if not user_id:
        return "Error: user_id is required."

    try:
        from angel_claw.config import settings
        from angel_claw.engine.app_context import create_app_context_manager
        
        ctx_manager = create_app_context_manager(settings)
        
        with ctx_manager._app_context():
            from modules.agent.models import Reminder
            reminders = Reminder.query.filter_by(user_id=user_id, is_sent=False).order_by(Reminder.remind_at).all()
            if not reminders:
                return "You have no upcoming reminders."
            
            lines = ["## Your Upcoming Reminders:"]
            for r in reminders:
                lines.append(f"- {r.remind_at.strftime('%Y-%m-%d %H:%M')}: {r.message}")
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error listing reminders: {e}", exc_info=True)
    
    return "Error: Could not retrieve reminders from database."
