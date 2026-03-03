from datetime import datetime, UTC
from shopyo.api.models import PkModel
from init import db

class Channel(PkModel):
    __tablename__ = "channels"
    
    user_id = db.Column(db.String(100), nullable=False)
    channel_type = db.Column(db.String(50), nullable=False) # web, telegram, cli, api
    channel_identifier = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean(), default=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    paired_at = db.Column(db.DateTime, default=lambda: datetime.now())
    last_seen_at = db.Column(db.DateTime, default=lambda: datetime.now())

    __table_args__ = (db.UniqueConstraint("channel_type", "channel_identifier", name="uix_channel_type_identifier"),)

class ApiKey(PkModel):
    __tablename__ = "api_keys"
    
    user_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False)
    prefix = db.Column(db.String(10), nullable=False)
    scopes = db.Column(db.Text, nullable=True) # comma-separated or JSON
    is_active = db.Column(db.Boolean(), default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    expires_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

class PairingToken(db.Model):
    __tablename__ = "pairing_tokens"
    
    token = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean(), default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

class InternalMessage(PkModel):
    __tablename__ = "internal_messages"
    
    sender_id = db.Column(db.String(100), nullable=False)
    recipient_id = db.Column(db.String(100), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean(), default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
