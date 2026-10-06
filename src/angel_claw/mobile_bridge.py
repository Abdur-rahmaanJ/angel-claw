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
