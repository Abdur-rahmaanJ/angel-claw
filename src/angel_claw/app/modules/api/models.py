from datetime import datetime

from shopyo.api.models import PkModel
from init import db


class ScheduledTask(PkModel):
    """A user-facing task that runs an agent prompt at a chosen time."""

    __tablename__ = "scheduled_tasks"
    __table_args__ = {"extend_existing": True}

    user_id = db.Column(db.String(100), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="")
    prompt = db.Column(db.Text, nullable=False)
    session_id = db.Column(db.String(100), nullable=False, default="task")
    run_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="scheduled", index=True
    )
    job_name = db.Column(db.String(120), nullable=True, unique=True)
    result = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)


class UsageEvent(PkModel):
    """A usage event reported by an integrated app (e.g. ask-moris searches)."""

    __tablename__ = "usage_events"
    __table_args__ = {"extend_existing": True}

    # subject = the end user (an AngelClaw user id, or "" if anonymous)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(255))
    app = db.Column(db.String(100), nullable=False)
    event = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    # the API key owner that reported the event
    reported_by = db.Column(db.String(100))
    meta_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
