import os
from datetime import datetime, timedelta
from pathlib import Path


class ChatLogger:
    def __init__(self, base_path: str = None):
        self._base_path_override = base_path

    @property
    def base_path(self) -> str:
        if self._base_path_override:
            return self._base_path_override
        return os.path.join(os.getcwd(), ".angelclaw", "chats")

    def _get_chat_file_path(self, date: datetime = None) -> Path:
        date = date or datetime.now()
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")

        file_path = Path(self.base_path) / year / month / f"{day}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return file_path

    def log(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        date: datetime = None,
    ):
        date = date or datetime.now()
        timestamp = date.strftime("%Y-%m-%d %H:%M:%S")
        file_path = self._get_chat_file_path(date)

        content = f"""## {timestamp} | Session: {session_id}

**User:** {user_message}

**Assistant:** {assistant_message}

---
"""

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

    def get_chats_for_date(self, date: datetime = None) -> str:
        date = date or datetime.now()
        file_path = self._get_chat_file_path(date)

        if not file_path.exists():
            return f"No chat logs found for {date.strftime('%Y-%m-%d')}."

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_chats_for_date_range(
        self, start_date: datetime, end_date: datetime = None
    ) -> str:
        if end_date is None:
            end_date = datetime.now()

        all_logs = []
        current = start_date.replace(hour=0, minute=0, second=0)

        while current <= end_date:
            file_path = self._get_chat_file_path(current)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    all_logs.append(f.read())
            current += timedelta(days=1)

        if not all_logs:
            return f"No chat logs found between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}."

        return "\n\n".join(all_logs)


chat_logger = ChatLogger()
