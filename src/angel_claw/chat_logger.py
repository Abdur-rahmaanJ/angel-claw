import os
from datetime import datetime, timedelta
from pathlib import Path
from .utils import get_user_root


class ChatLogger:
    def __init__(self, base_path: str = None):
        self._base_path_override = base_path

    def _get_chat_file_path(self, user_id: str, date: datetime = None) -> Path:
        date = date or datetime.now()
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")

        if self._base_path_override:
            base_path = Path(self._base_path_override)
        else:
            base_path = get_user_root(user_id) / "chats"

        file_path = base_path / year / month / f"{day}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return file_path

    def log(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        date: datetime = None,
    ):
        date = date or datetime.now()
        timestamp = date.strftime("%Y-%m-%d %H:%M:%S")
        file_path = self._get_chat_file_path(user_id, date)

        content = f"""## {timestamp} | Session: {session_id}

**User:** {user_message}

**Assistant:** {assistant_message}

---
"""

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

    def get_chats_for_date(self, user_id: str, date: datetime = None) -> str:
        date = date or datetime.now()
        file_path = self._get_chat_file_path(user_id, date)

        if not file_path.exists():
            return f"No chat logs found for {date.strftime('%Y-%m-%d')}."

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_chats_for_date_range(
        self, user_id: str, start_date: datetime, end_date: datetime = None
    ) -> str:
        if end_date is None:
            end_date = datetime.now()

        all_logs = []
        current = start_date.replace(hour=0, minute=0, second=0)

        while current <= end_date:
            file_path = self._get_chat_file_path(user_id, current)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    all_logs.append(f.read())
            current += timedelta(days=1)

        if not all_logs:
            return f"No chat logs found between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}."

        return "\n\n".join(all_logs)


chat_logger = ChatLogger()
