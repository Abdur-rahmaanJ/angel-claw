from datetime import datetime

from shopyo.api.models import PkModel
from init import db


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
