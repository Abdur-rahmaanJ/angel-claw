from datetime import datetime, UTC
from shopyo.api.models import PkModel
from init import db


class Channel(PkModel):
    __tablename__ = "channels"
    __table_args__ = (
        db.UniqueConstraint(
            "channel_type",
            "channel_identifier",
            name="uix_channel_type_identifier",
        ),
        {"extend_existing": True},
    )

    user_id = db.Column(db.String(100), nullable=False)
    channel_type = db.Column(db.String(50), nullable=False)  # web, telegram, cli, api
    channel_identifier = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean(), default=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    paired_at = db.Column(db.DateTime, default=lambda: datetime.now())
    last_seen_at = db.Column(db.DateTime, default=lambda: datetime.now())


class ApiKey(PkModel):
    __tablename__ = "api_keys"
    __table_args__ = {"extend_existing": True}

    user_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False)
    prefix = db.Column(db.String(10), nullable=False)
    scopes = db.Column(db.Text, nullable=True)  # comma-separated or JSON
    is_active = db.Column(db.Boolean(), default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    expires_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)


class PairingToken(db.Model):
    __tablename__ = "pairing_tokens"
    __table_args__ = {"extend_existing": True}

    token = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean(), default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


class InternalMessage(PkModel):
    __tablename__ = "internal_messages"
    __table_args__ = {"extend_existing": True}

    sender_id = db.Column(db.String(100), nullable=False)
    recipient_id = db.Column(db.String(100), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean(), default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


class UserSetting(PkModel):
    __tablename__ = "user_settings"
    __table_args__ = (
        db.UniqueConstraint("user_id", "key", name="uix_user_id_key"),
        {"extend_existing": True},
    )

    user_id = db.Column(db.String(100), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default="general")  # llm, scheduler, ui, etc
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )


class UserVaultSecret(PkModel):
    __tablename__ = "user_vault_secrets"
    __table_args__ = (
        db.UniqueConstraint("user_id", "secret_key", name="uix_user_secret_key"),
        {"extend_existing": True},
    )

    user_id = db.Column(db.String(100), nullable=False)
    secret_key = db.Column(db.String(100), nullable=False)
    secret_value_encrypted = db.Column(db.LargeBinary, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )


class UserCredit(PkModel):
    __tablename__ = "user_credits"
    __table_args__ = {"extend_existing": True}

    user_id = db.Column(db.String(100), nullable=False, unique=True)
    balance = db.Column(db.Integer, nullable=False, default=0)
    lifetime_spent = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    @staticmethod
    def get_or_create(user_id: str, initial: int = 0):
        credit = UserCredit.query.filter_by(user_id=user_id).first()
        if not credit:
            credit = UserCredit(user_id=user_id, balance=initial)
            db.session.add(credit)
            db.session.commit()
        return credit

    def add_credits(self, amount: int, reason: str = "manual", meta: dict = None):
        self.balance += amount
        transaction = CreditTransaction(
            user_id=self.user_id,
            action=reason,
            amount=amount,
            balance_after=self.balance,
            meta_json=meta,
        )
        db.session.add(transaction)
        db.session.commit()
        return True

    def deduct_credits(
        self, amount: int, action: str, meta: dict = None, allow_negative: bool = False
    ):
        if self.balance < amount and not allow_negative:
            return False, f"Insufficient credits: {self.balance} < {amount}"

        self.balance -= amount
        self.lifetime_spent += amount
        transaction = CreditTransaction(
            user_id=self.user_id,
            action=action,
            amount=-amount,
            balance_after=self.balance,
            meta_json=meta,
        )
        db.session.add(transaction)
        db.session.commit()
        return True, "Success"


class CreditTransaction(PkModel):
    __tablename__ = "credit_transactions"
    __table_args__ = {"extend_existing": True}

    user_id = db.Column(db.String(100), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    amount = db.Column(
        db.Integer, nullable=False
    )  # positive for credit, negative for debit
    balance_after = db.Column(db.Integer, nullable=False)
    meta_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())


class CreditAction(PkModel):
    __tablename__ = "credit_actions"
    __table_args__ = {"extend_existing": True}

    name = db.Column(
        db.String(100), nullable=False, unique=True
    )  # e.g., "chat_message", "api_call"
    cost = db.Column(db.Integer, nullable=False, default=1)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean(), default=True)

    @staticmethod
    def get_cost(action_name: str) -> int:
        action = CreditAction.query.filter_by(name=action_name, is_active=True).first()
        return action.cost if action else 1
