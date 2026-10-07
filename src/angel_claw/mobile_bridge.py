# Central store for mobile commands to avoid circular imports
import uuid

# In production, this should be backed by a database
# Structure: { user_id: [ {id, type, params}, ... ] }
_command_queue = {}

def queue_mobile_command(user_id: str, command_type: str, params: dict, session_id: str = None):
    if user_id not in _command_queue:
        _command_queue[user_id] = []
    
    command = {
        "id": str(uuid.uuid4()),
        "type": command_type,
        "params": params
    }
    _command_queue[user_id].append(command)
    # Remember where the command came from so a device result can be fed
    # back into the same conversation (kept after the queue entry is popped).
    _command_meta[command["id"]] = {"session_id": session_id, "type": command_type}
    return command["id"]

def get_and_clear_commands(user_id: str):
    return _command_queue.pop(user_id, [])

# command_id -> {session_id, type}; survives get_and_clear_commands
_command_meta = {}

def pop_command_meta(command_id: str):
    return _command_meta.pop(command_id, None)

# user_id -> list of capability descriptors the phone reported (live availability)
_capabilities = {}

def set_user_capabilities(user_id: str, capabilities: list):
    _capabilities[user_id] = capabilities or []
    print(f"[mobile_bridge] capabilities for {user_id}: {[c.get('id') for c in _capabilities[user_id]]}")

def get_user_capabilities(user_id: str) -> list:
    return _capabilities.get(user_id, [])

# user_id -> device facts the phone reported (model, android, screen, tz, battery...)
_device_info = {}

def set_user_device_info(user_id: str, info: dict):
    _device_info[user_id] = info or {}

def get_user_device_info(user_id: str) -> dict:
    return _device_info.get(user_id, {})
