import pytest
import os
import shutil
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from angel_claw.skills.calendar import (
    create_calendar_event,
    list_calendar_events,
    delete_calendar_event,
    update_calendar_event,
    check_availability,
    get_today_events,
)


def get_future_date(days_ahead: int = 1) -> str:
    """Get a future date string."""
    future = datetime.now() + timedelta(days=days_ahead)
    return future.strftime("%Y-%m-%d")


@pytest.fixture(autouse=True)
def setup_calendar_test(monkeypatch):
    test_dir = "./.angelclaw_test_calendar"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    monkeypatch.setattr(
        "angel_claw.skills.calendar._get_calendar_dir", lambda: test_dir
    )
    yield
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


def test_create_calendar_event():
    future_date = get_future_date(1)
    res = create_calendar_event(
        title="Test Meeting", date=future_date, time="14:00", duration_minutes=60
    )
    assert "Event created" in res
    assert "Test Meeting" in res


def test_create_event_with_description():
    future_date = get_future_date(1)
    res = create_calendar_event(
        title="Dentist",
        date=future_date,
        time="10:00",
        duration_minutes=30,
        description="Annual checkup",
        location="123 Dental St",
    )
    assert "Event created" in res


def test_list_calendar_events():
    future_date1 = get_future_date(1)
    future_date2 = get_future_date(2)
    create_calendar_event(title="Event 1", date=future_date1, time="10:00")
    create_calendar_event(title="Event 2", date=future_date2, time="11:00")

    res = list_calendar_events(days=7)
    assert "Event 1" in res
    assert "Event 2" in res


def test_delete_calendar_event():
    future_date = get_future_date(1)
    create_calendar_event(title="To Delete", date=future_date)

    res = delete_calendar_event(event_id=1)
    assert "Deleted" in res

    res = list_calendar_events(days=7)
    assert "To Delete" not in res


def test_update_calendar_event():
    future_date = get_future_date(1)
    create_calendar_event(title="Original", date=future_date, time="10:00")

    res = update_calendar_event(event_id=1, title="Updated", time="14:00")
    assert "Updated" in res

    res = list_calendar_events(days=7)
    assert "Updated" in res
    assert "Original" not in res


def test_check_availability_free():
    future_date = get_future_date(1)
    create_calendar_event(
        title="Existing", date=future_date, time="10:00", duration_minutes=60
    )

    res = check_availability(date=future_date, time="14:00", duration_minutes=60)
    assert "available" in res


def test_check_availability_conflict():
    future_date = get_future_date(1)
    create_calendar_event(
        title="Existing", date=future_date, time="10:00", duration_minutes=60
    )

    res = check_availability(date=future_date, time="10:00", duration_minutes=60)
    assert "conflicts" in res


def test_session_isolation():
    future_date = get_future_date(1)
    create_calendar_event(
        title="Session 1 Event", date=future_date, session_id="session1"
    )
    create_calendar_event(
        title="Session 2 Event", date=future_date, session_id="session2"
    )

    res1 = list_calendar_events(days=7, session_id="session1")
    assert "Session 1 Event" in res1
    assert "Session 2 Event" not in res1

    res2 = list_calendar_events(days=7, session_id="session2")
    assert "Session 2 Event" in res2
    assert "Session 1 Event" not in res2
