# Central store for mobile commands to avoid circular imports
import uuid

# In production, this should be backed by a database
# Structure: { user_id: [ {id, type, params}, ... ] }
_command_queue = {}

def queue_mobile_command(user_id: str, command_type: str, params: dict):
    if user_id not in _command_queue:
        _command_queue[user_id] = []
    
    command = {
        "id": str(uuid.uuid4()),
        "type": command_type,
        "params": params
    }
    _command_queue[user_id].append(command)
    return command["id"]

def get_and_clear_commands(user_id: str):
    return _command_queue.pop(user_id, [])

# user_id -> list of capability descriptors the phone reported (live availability)
_capabilities = {}

def set_user_capabilities(user_id: str, capabilities: list):
    _capabilities[user_id] = capabilities or []
    print(f"[mobile_bridge] capabilities for {user_id}: {[c.get('id') for c in _capabilities[user_id]]}")

def get_user_capabilities(user_id: str) -> list:
    return _capabilities.get(user_id, [])
