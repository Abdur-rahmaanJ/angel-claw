# Central store for mobile commands to avoid circular imports
# File-backed so state is shared across gunicorn worker processes.
import fcntl
import json
import os
import uuid

from .config import settings

_STORE_DIR = os.path.join(settings.memory_persist_dir, "mobile_bridge")


def _lock_path(name: str) -> str:
    return os.path.join(_STORE_DIR, f"{name}.lock")


def _store_path(name: str) -> str:
    return os.path.join(_STORE_DIR, f"{name}.json")


def _with_store(name: str, mutate):
    """Read-modify-write a JSON store under an exclusive cross-process lock."""
    os.makedirs(_STORE_DIR, exist_ok=True)
    with open(_lock_path(name), "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            try:
                with open(_store_path(name), "r") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            result = mutate(data)
            tmp_path = _store_path(name) + f".tmp.{os.getpid()}"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, _store_path(name))
            return result
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _read_store(name: str) -> dict:
    try:
        with open(_store_path(name), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def queue_mobile_command(user_id: str, command_type: str, params: dict, session_id: str = None):
    command = {
        "id": str(uuid.uuid4()),
        "type": command_type,
        "params": params
    }

    def mutate(data):
        data.setdefault(user_id, []).append(command)
        # Remember where the command came from so a device result can be fed
        # back into the same conversation (kept after the queue entry is popped).
        data.setdefault("_meta", {})[command["id"]] = {"session_id": session_id, "type": command_type}
        return command["id"]

    return _with_store("queue", mutate)


def get_and_clear_commands(user_id: str):
    def mutate(data):
        return data.pop(user_id, [])

    return _with_store("queue", mutate)


def pop_command_meta(command_id: str):
    def mutate(data):
        return data.get("_meta", {}).pop(command_id, None)

    return _with_store("queue", mutate)


def set_user_capabilities(user_id: str, capabilities: list):
    caps = capabilities or []

    def mutate(data):
        data[user_id] = caps
        return None

    _with_store("capabilities", mutate)
    print(f"[mobile_bridge] capabilities for {user_id}: {[c.get('id') for c in caps]}")


def get_user_capabilities(user_id: str) -> list:
    return _read_store("capabilities").get(user_id, [])


def set_user_device_info(user_id: str, info: dict):
    def mutate(data):
        data[user_id] = info or {}
        return None

    _with_store("device_info", mutate)


def get_user_device_info(user_id: str) -> dict:
    return _read_store("device_info").get(user_id, {})
