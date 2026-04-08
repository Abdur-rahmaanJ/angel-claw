import sqlite3
import json
import os
import logging
from pathlib import Path
from typing import List, Optional, Any, Dict
from datetime import datetime, UTC
from cryptography.fernet import Fernet
import hashlib
import base64

from ..models import Message, Role, UserContext

logger = logging.getLogger("angel-claw-persistence")


class PersistentHistory:
    """Persistent history for a single user (SQLite file or Shared SQLAlchemy DB)."""

    def __init__(self, context: UserContext):
        self.context = context
        from ..utils import get_user_root
        from ..config import settings

        self.db_uri = settings.history_database_uri
        if self.db_uri:
            self._is_shared = True
        else:
            self.root = get_user_root(context.user_id)
            self.db_path = self.root / "history.db"
            self._is_shared = False

        self._init_db()

    def _init_db(self):
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS history (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        session_id TEXT,
                        role TEXT,
                        content TEXT,
                        name TEXT,
                        tool_calls TEXT,
                        tool_call_id TEXT,
                        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                )
                conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS idx_session_user ON history(user_id, session_id)"
                    )
                )
                conn.commit()
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        role TEXT,
                        content TEXT,
                        name TEXT,
                        tool_calls TEXT,
                        tool_call_id TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)"
                )

    def add_message(self, session_id: str, message: Message):
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO history (user_id, session_id, role, content, name, tool_calls, tool_call_id, timestamp) VALUES (:u, :s, :r, :c, :n, :tc, :tcid, :ts)"
                    ),
                    {
                        "u": self.context.user_id,
                        "s": session_id,
                        "r": message.role.value,
                        "c": message.content,
                        "n": message.name,
                        "tc": json.dumps(message.tool_calls)
                        if message.tool_calls
                        else None,
                        "tcid": message.tool_call_id,
                        "ts": datetime.now(UTC),
                    },
                )
                conn.commit()
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, name, tool_calls, tool_call_id, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        message.role.value,
                        message.content,
                        message.name,
                        json.dumps(message.tool_calls) if message.tool_calls else None,
                        message.tool_call_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )

    def get_history(self, session_id: str, limit: int = 50) -> List[Message]:
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                cursor = conn.execute(
                    sqlalchemy.text(
                        "SELECT role, content, name, tool_calls, tool_call_id FROM history WHERE user_id = :u AND session_id = :s ORDER BY timestamp DESC LIMIT :l"
                    ),
                    {"u": self.context.user_id, "s": session_id, "l": limit},
                )
                rows = cursor.fetchall()
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT role, content, name, tool_calls, tool_call_id FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                )
                rows = cursor.fetchall()

        messages = []
        for row in reversed(rows):
            messages.append(
                Message(
                    role=Role(row[0]),
                    content=row[1],
                    name=row[2],
                    tool_calls=json.loads(row[3]) if row[3] else None,
                    tool_call_id=row[4],
                )
            )
        return messages

    def clear_history(self, session_id: str):
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        "DELETE FROM history WHERE user_id = :u AND session_id = :s"
                    ),
                    {"u": self.context.user_id, "s": session_id},
                )
                conn.commit()
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

    def get_sessions(self) -> List[Dict[str, str]]:
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                # Use a subquery to find the first user message for each session
                cursor = conn.execute(
                    sqlalchemy.text("""
                        SELECT m.session_id, m.content
                        FROM history m
                        JOIN (
                            SELECT session_id, MIN(timestamp) as min_ts
                            FROM history
                            WHERE user_id = :u AND role = 'user'
                            GROUP BY session_id
                        ) first_msgs ON m.session_id = first_msgs.session_id AND m.timestamp = first_msgs.min_ts
                        WHERE m.user_id = :u
                        ORDER BY m.timestamp DESC
                    """),
                    {"u": self.context.user_id},
                )
                rows = cursor.fetchall()
        else:
            with sqlite3.connect(self.db_path) as conn:
                # Standard SQLite way to get the first row per group
                cursor = conn.execute("""
                    SELECT session_id, content FROM messages 
                    WHERE role = 'user' 
                    GROUP BY session_id 
                    HAVING timestamp = MIN(timestamp)
                    ORDER BY timestamp DESC
                """)
                rows = cursor.fetchall()
        return [{"id": row[0], "preview": row[1]} for row in rows]

    def delete_session(self, session_id: str):
        self.clear_history(session_id)

    def rename_session(self, old_id: str, new_name: str):
        if self._is_shared:
            import sqlalchemy

            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        "UPDATE history SET session_id = :new WHERE session_id = :old AND user_id = :uid"
                    ),
                    {"new": new_name, "old": old_id, "uid": self.context.user_id},
                )
                conn.commit()
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE messages SET session_id = ? WHERE session_id = ?",
                    (new_name, old_id),
                )
                conn.commit()


class UserVault:
    """Encrypted key-value store for user secrets."""

    def __init__(self, context: UserContext):
        self.context = context
        from ..utils import get_user_root

        self.root = get_user_root(context.user_id)
        self.vault_path = self.root / "vault.json.enc"
        self._key = self._derive_key()
        self._fernet = Fernet(self._key)
        self._data: Dict[str, str] = self._load()

    def _derive_key(self) -> bytes:
        # In a real Amazon environment, we'd use KMS.
        # For Angel Claw, we derive a key from the user_id and a global pepper.
        # This prevents local disk exposure from revealing secrets without the platform key.
        from ..config import settings

        salt = os.environ.get("ANGEL_CLAW_VAULT_SALT", "default-salt-change-me")
        key_material = f"{self.context.user_id}:{salt}".encode()
        digest = hashlib.sha256(key_material).digest()
        return base64.urlsafe_b64encode(digest)

    def _load(self) -> Dict[str, str]:
        if not self.vault_path.exists():
            return {}
        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
                decrypted_data = self._fernet.decrypt(encrypted_data)
                return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Error loading vault for {self.context.user_id}: {e}")
            return {}

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            raw_data = json.dumps(self._data).encode()
            encrypted_data = self._fernet.encrypt(raw_data)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted_data)
        except Exception as e:
            logger.error(f"Error saving vault for {self.context.user_id}: {e}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._data.get(key, default)

    def set(self, key: str, value: str):
        self._data[key] = value
        self._save()

    def delete(self, key: str):
        if key in self._data:
            del self._data[key]
            self._save()

    def list_keys(self) -> List[str]:
        return list(self._data.keys())
