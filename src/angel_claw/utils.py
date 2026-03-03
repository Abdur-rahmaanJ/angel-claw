import os
from pathlib import Path
from .config import settings

def get_user_root(user_id: str) -> Path:
    """Get the root directory for a specific user's data."""
    root = Path(settings.user_data_root).expanduser()
    user_dir = root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir
