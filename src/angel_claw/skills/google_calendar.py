import os
import json
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional
from angel_claw.skills.manager import skill
from angel_claw.config import settings

logger = logging.getLogger("angel-claw-gcal")

_google_service = None


def _get_service_account_path() -> str:
    """Get path for service account JSON key."""
    base_dir = os.path.join(os.getcwd(), ".angelclaw")
    return os.path.join(base_dir, "service_account.json")


def _load_service_account():
    """Load service account credentials."""
    # Check file first
    sa_path = _get_service_account_path()
    if os.path.exists(sa_path):
        with open(sa_path, "r") as f:
            return json.load(f)

    # Check env variable (base64 encoded or raw JSON)
    if settings.google_client_id:  # reusing this field for service account JSON
        try:
            return json.loads(settings.google_client_id)
        except json.JSONDecodeError:
            pass

    return None


def _get_google_service():
    """Get or create Google Calendar service using Service Account."""
    global _google_service

    if _google_service:
        return _google_service, None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        sa_creds = _load_service_account()

        if not sa_creds:
            return (
                None,
                "Service Account not configured. Add service account JSON to .env or place service_account.json in .angelclaw/",
            )

        # Create credentials from service account
        credentials = service_account.Credentials.from_service_account_info(
            sa_creds, scopes=["https://www.googleapis.com/auth/calendar.events"]
        )

        _google_service = build("calendar", "v3", credentials=credentials)
        return _google_service, None

    except ImportError:
        return (
            None,
            "google-api-python-client not installed. Run: pip install google-api-python-client google-auth",
        )
    except Exception as e:
        logger.error(f"Google Calendar error: {e}")
        return None, f"Error: {str(e)}"


@skill
def gcal_create_event(
    title: str,
    date: str,
    time: Optional[str] = None,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
) -> str:
    """
    Creates a Google Calendar event.
    - title: Event title
    - date: Date (YYYY-MM-DD or natural like "tomorrow", "next Monday")
    - time: Time (HH:MM, optional)
    - duration_minutes: Duration in minutes (default 60)
    - description: Event description
    - location: Event location
    """
    service, error = _get_google_service()

    if error:
        return f"Error: {error}"

    # Parse date/time
    try:
        from dateutil import parser as dateparser

        datetime_str = f"{date} {time}" if time else date
        start_dt = dateparser.parse(datetime_str)

        if start_dt.tzinfo:
            start_dt = start_dt.replace(tzinfo=None)

        end_dt = start_dt + timedelta(minutes=duration_minutes)

    except Exception as e:
        return f"Error parsing date/time: {e}"

    event = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "UTC",
        },
    }

    try:
        event = service.events().insert(calendarId="primary", body=event).execute()

        return f"✅ Event created: '{title}' on {start_dt.strftime('%Y-%m-%d %H:%M')}\n🔗 {event.get('htmlLink', '')}"

    except Exception as e:
        return f"Error creating event: {e}"


@skill
def gcal_list_events(days: int = 7) -> str:
    """
    Lists upcoming Google Calendar events.
    - days: Number of days to look ahead (default 7)
    """
    service, error = _get_google_service()

    if error:
        return f"Error: {error}"

    now = datetime.now(UTC)
    end_time = now + timedelta(days=days)

    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat() + "Z",
                timeMax=end_time.isoformat() + "Z",
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return f"No events in the next {days} days."

        lines = [f"## Upcoming Google Calendar Events (next {days} days)\n"]

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "No title")
            location = event.get("location", "")

            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                date_str = start_dt.strftime("%a, %b %d at %H:%M")
            except:
                date_str = start

            lines.append(f"📅 **{date_str}**: {summary}")
            if location:
                lines.append(f"   📍 {location}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing events: {e}"


@skill
def gcal_delete_event(event_id: str) -> str:
    """
    Deletes a Google Calendar event.
    - event_id: The event ID to delete
    """
    service, error = _get_google_service()

    if error:
        return f"Error: {error}"

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()

        return f"✅ Event deleted: {event_id}"

    except Exception as e:
        return f"Error deleting event: {e}"


@skill
def gcal_check_status() -> str:
    """
    Checks Google Calendar status.
    """
    sa_path = _get_service_account_path()
    sa_creds = _load_service_account()

    if not sa_creds and not (sa_path and os.path.exists(sa_path)):
        return (
            "❌ Service Account not configured. Add service_account.json to .angelclaw/"
        )

    service, error = _get_google_service()
    if error:
        return f"❌ Error: {error}"

    return "✅ Google Calendar connected!"


@skill
def gcal_get_my_email() -> str:
    """
    Gets the Google account email being used.
    """
    service, error = _get_google_service()

    if error:
        return f"Error: {error}"

    try:
        cal = service.calendarList().get(calendarId="primary").execute()
        return f"Using calendar: {cal.get('summary', 'Unknown')}"
    except Exception as e:
        return f"Error: {e}"
