import os
import re
from pathlib import Path
from .config import settings


def safe_filename_part(value: str, fallback: str = "default") -> str:
    """Make a chat session id safe to use as a file name.

    Session ids come from clients, so strip path separators, leading dots and
    anything that could climb out of the per-user directory.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", str(value or ""))
    cleaned = cleaned.strip(" .")
    return cleaned or fallback

def get_user_root(user_id: str) -> Path:
    """Get the root directory for a specific user's data."""
    root = Path(settings.user_data_root).expanduser()
    user_dir = root / "users" / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        user_dir.chmod(0o700)
    except OSError:
        pass
    return user_dir
