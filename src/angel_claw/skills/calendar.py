import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
from angel_claw.skills.manager import skill
from angel_claw.config import settings


def _get_calendar_dir() -> str:
    """Get the directory for storing calendar events."""
    base_dir = os.path.join(os.getcwd(), ".angelclaw")
    cal_dir = os.path.join(base_dir, "calendar")
    if not os.path.exists(cal_dir):
        os.makedirs(cal_dir)
    return cal_dir


def _get_calendar_file(session_id: str) -> str:
    """Get the calendar file path for a session."""
    return os.path.join(_get_calendar_dir(), f"{session_id}.json")


def _load_events(session_id: str) -> List[dict]:
    """Load events for a session."""
    filepath = _get_calendar_file(session_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_events(session_id: str, events: List[dict]):
    """Save events for a session."""
    filepath = _get_calendar_file(session_id)
    with open(filepath, "w") as f:
        json.dump(events, f, indent=2)


def _parse_datetime(date_str: str, time_str: Optional[str] = None) -> datetime:
    """Parse date/time string into datetime object."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]

    full_str = f"{date_str} {time_str}" if time_str else date_str

    for fmt in formats:
        try:
            return datetime.strptime(full_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Could not parse date: {date_str} {time_str}")


def _format_datetime(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M")


@skill
def create_calendar_event(
    title: str,
    date: str,
    time: Optional[str] = None,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
    session_id: str = "cli-default",
) -> str:
    """
    Creates a calendar event.
    - title: Event title
    - date: Date (YYYY-MM-DD or DD/MM/YYYY)
    - time: Time (HH:MM, optional)
    - duration_minutes: Duration in minutes (default 60)
    - description: Event description
    - location: Event location
    - session_id: The session this event belongs to
    """
    try:
        start_dt = _parse_datetime(date, time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
    except ValueError as e:
        return f"Error: Invalid date/time format. Use YYYY-MM-DD or DD/MM/YYYY. {e}"

    events = _load_events(session_id)

    event = {
        "id": len(events) + 1,
        "title": title,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "description": description,
        "location": location,
        "created_at": datetime.now().isoformat(),
    }

    events.append(event)
    _save_events(session_id, events)

    return f"✅ Event created: '{title}' on {_format_datetime(start_dt)} - {_format_datetime(end_dt)}"


@skill
def list_calendar_events(days: int = 7, session_id: str = "cli-default") -> str:
    """
    Lists upcoming calendar events.
    - days: Number of days to look ahead (default 7)
    - session_id: The session to list events for
    """
    events = _load_events(session_id)

    if not events:
        return "No events found."

    now = datetime.now()
    future = now + timedelta(days=days)

    upcoming = []
    for event in events:
        try:
            event_start = datetime.fromisoformat(event["start"])
            if now <= event_start <= future:
                upcoming.append((event_start, event))
        except (KeyError, ValueError):
            continue

    if not upcoming:
        return f"No events in the next {days} days."

    upcoming.sort()

    lines = [f"## Upcoming Events (next {days} days)\n"]
    for event_start, event in upcoming:
        end_str = ""
        try:
            end_dt = datetime.fromisoformat(event["end"])
            end_str = f" - {_format_datetime(end_dt)}"
        except (KeyError, ValueError):
            pass

        location = f" 📍 {event['location']}" if event.get("location") else ""
        lines.append(
            f"📅 **{event_start.strftime('%a, %b %d')}** at {_format_datetime(event_start)}{end_str}"
        )
        lines.append(f"   {event['title']}{location}")
        if event.get("description"):
            lines.append(f"   {event['description']}")
        lines.append("")

    return "\n".join(lines)


@skill
def delete_calendar_event(event_id: int, session_id: str = "cli-default") -> str:
    """
    Deletes a calendar event.
    - event_id: The ID of the event to delete
    - session_id: The session the event belongs to
    """
    events = _load_events(session_id)

    original_count = len(events)
    events = [e for e in events if e["id"] != event_id]

    if len(events) == original_count:
        return f"Error: Event {event_id} not found."

    # Re-index IDs
    for i, event in enumerate(events, 1):
        event["id"] = i

    _save_events(session_id, events)
    return f"🗑️ Deleted event {event_id}."


@skill
def update_calendar_event(
    event_id: int,
    title: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    session_id: str = "cli-default",
) -> str:
    """
    Updates a calendar event.
    - event_id: The ID of the event to update
    - title: New title
    - date: New date
    - time: New time
    - duration_minutes: New duration
    - description: New description
    - location: New location
    - session_id: The session the event belongs to
    """
    events = _load_events(session_id)

    for event in events:
        if event["id"] == event_id:
            if title:
                event["title"] = title
            if description is not None:
                event["description"] = description
            if location is not None:
                event["location"] = location
            if date or time:
                try:
                    current_start = datetime.fromisoformat(event["start"])
                    new_date = date or current_start.strftime("%Y-%m-%d")
                    new_time = time or current_start.strftime("%H:%M")
                    new_start = _parse_datetime(new_date, new_time)
                    event["start"] = new_start.isoformat()

                    duration = duration_minutes or 60
                    event["end"] = (new_start + timedelta(minutes=duration)).isoformat()
                except ValueError as e:
                    return f"Error: Invalid date/time format. {e}"
            elif duration_minutes:
                try:
                    start_dt = datetime.fromisoformat(event["start"])
                    event["end"] = (
                        start_dt + timedelta(minutes=duration_minutes)
                    ).isoformat()
                except (KeyError, ValueError):
                    pass

            _save_events(session_id, events)
            return f"✅ Updated event {event_id}: '{event['title']}'"

    return f"Error: Event {event_id} not found."


@skill
def check_availability(
    date: str,
    time: Optional[str] = None,
    duration_minutes: int = 60,
    session_id: str = "cli-default",
) -> str:
    """
    Checks if a time slot is available.
    - date: Date to check (YYYY-MM-DD)
    - time: Time to check (HH:MM)
    - duration_minutes: Duration to check for
    - session_id: The session to check
    """
    try:
        check_start = _parse_datetime(date, time)
        check_end = check_start + timedelta(minutes=duration_minutes)
    except ValueError as e:
        return f"Error: Invalid date/time format. {e}"

    events = _load_events(session_id)

    conflicts = []
    for event in events:
        try:
            event_start = datetime.fromisoformat(event["start"])
            event_end = datetime.fromisoformat(event["end"])

            # Check for overlap
            if check_start < event_end and check_end > event_start:
                conflicts.append(event)
        except (KeyError, ValueError):
            continue

    if conflicts:
        lines = [f"⚠️ Time slot conflicts with existing events:"]
        for event in conflicts:
            lines.append(
                f"  - {event['title']} ({event['start'][:16]} - {event['end'][:16]})"
            )
        return "\n".join(lines)

    return f"✅ Time slot {_format_datetime(check_start)} - {_format_datetime(check_end)} is available."


@skill
def get_today_events(session_id: str = "cli-default") -> str:
    """
    Gets today's events.
    - session_id: The session to get events for
    """
    events = _load_events(session_id)

    if not events:
        return "No events today."

    today = datetime.now().date()

    today_events = []
    for event in events:
        try:
            event_date = datetime.fromisoformat(event["start"]).date()
            if event_date == today:
                today_events.append(event)
        except (KeyError, ValueError):
            continue

    if not today_events:
        return "No events today."

    today_events.sort(key=lambda e: e["start"])

    lines = ["## Today's Events\n"]
    for event in today_events:
        start_dt = datetime.fromisoformat(event["start"])
        end_dt = datetime.fromisoformat(event["end"])
        lines.append(
            f"🕐 {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}: {event['title']}"
        )
        if event.get("location"):
            lines.append(f"   📍 {event['location']}")

    return "\n".join(lines)
