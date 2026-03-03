import os
import json
from typing import Optional, List
from angel_claw.skills.manager import skill
from angel_claw.config import settings


from angel_claw.utils import get_user_root

def _get_todos_dir(user_id: Optional[str] = None) -> str:
    """Get the directory for storing todos."""
    if user_id:
        user_root = get_user_root(user_id)
        todos_dir = user_root / "todos"
    else:
        # Backward compatibility
        base_dir = os.path.join(os.getcwd(), ".angelclaw")
        todos_dir = Path(os.path.join(base_dir, "todos"))
        
    if not todos_dir.exists():
        todos_dir.mkdir(parents=True, exist_ok=True)
    return str(todos_dir)


def _get_todos_file(session_id: str, user_id: Optional[str] = None) -> str:
    """Get the todos file path for a session."""
    return os.path.join(_get_todos_dir(user_id), f"{session_id}.json")


def _load_todos(session_id: str, user_id: Optional[str] = None) -> List[dict]:
    """Load todos for a session."""
    filepath = _get_todos_file(session_id, user_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_todos(session_id: str, todos: List[dict], user_id: Optional[str] = None):
    """Save todos for a session."""
    filepath = _get_todos_file(session_id, user_id)
    with open(filepath, "w") as f:
        json.dump(todos, f, indent=2)


@skill
def add_todo(
    content: str,
    due_date: Optional[str] = None,
    priority: str = "medium",
    session_id: str = "cli-default",
    user_id: Optional[str] = None,
) -> str:
    """
    Adds a new todo item.
    - content: The todo description
    - due_date: Optional due date (YYYY-MM-DD)
    - priority: 'low', 'medium', or 'high'
    - session_id: The session this todo belongs to
    - user_id: The user this todo belongs to
    """
    todos = _load_todos(session_id, user_id)

    todo = {
        "id": len(todos) + 1,
        "content": content,
        "due_date": due_date,
        "priority": priority,
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }

    todos.append(todo)
    _save_todos(session_id, todos, user_id)

    return f"✅ Added todo: '{content}' (Priority: {priority})"


@skill
def list_todos(status: str = "all", session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    """
    Lists items.
    - status: 'all', 'pending', or 'completed'
    - session_id: The session to list todos for
    - user_id: The user to list todos for
    """
    todos = _load_todos(session_id, user_id)


    if not todos:
        return "No todos found."

    filtered = todos
    if status == "pending":
        filtered = [t for t in todos if not t.get("completed")]
    elif status == "completed":
        filtered = [t for t in todos if t.get("completed")]

    if not filtered:
        return f"No {status} todos found."

    lines = [f"## Todos ({status}) for {session_id}"]
    for todo in filtered:
        check = "✅" if todo.get("completed") else "⬜"
        priority = todo.get("priority", "medium")
        due = f" (Due: {todo.get('due_date')})" if todo.get("due_date") else ""
        lines.append(
            f"{check} [{priority.upper()}] {todo['id']}. {todo['content']}{due}"
        )

    return "\n".join(lines)


@skill
def complete_todo(todo_id: int, session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    """
    Marks a todo as completed.
    - todo_id: The ID of the todo to complete
    - session_id: The session the todo belongs to
    - user_id: The user the todo belongs to
    """
    todos = _load_todos(session_id, user_id)

    for todo in todos:
        if todo["id"] == todo_id:
            todo["completed"] = True
            todo["completed_at"] = datetime.now().isoformat()
            _save_todos(session_id, todos, user_id)
            return f"✅ Completed: '{todo['content']}'"

    return f"Error: Todo {todo_id} not found."


@skill
def delete_todo(todo_id: int, session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    """
    Deletes a todo item.
    - todo_id: The ID of the todo to delete
    - session_id: The session the todo belongs to
    - user_id: The user the todo belongs to
    """
    todos = _load_todos(session_id, user_id)

    original_count = len(todos)
    todos = [t for t in todos if t["id"] != todo_id]

    if len(todos) == original_count:
        return f"Error: Todo {todo_id} not found."

    # Re-index IDs
    for i, todo in enumerate(todos, 1):
        todo["id"] = i

    _save_todos(session_id, todos, user_id)
    return f"🗑️ Deleted todo {todo_id}."


@skill
def clear_completed_todos(session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    """
    Clears all completed todos.
    - session_id: The session to clear todos for
    - user_id: The user to clear todos for
    """
    todos = _load_todos(session_id, user_id)

    remaining = [t for t in todos if not t.get("completed")]
    cleared = len(todos) - len(remaining)

    # Re-index IDs
    for i, todo in enumerate(remaining, 1):
        todo["id"] = i

    _save_todos(session_id, remaining, user_id)
    return f"🗑️ Cleared {cleared} completed todos."


@skill
def update_todo(
    todo_id: int,
    content: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    session_id: str = "cli-default",
    user_id: Optional[str] = None,
) -> str:
    """
    Updates a todo item.
    - todo_id: The ID of the todo to update
    - content: New content (optional)
    - due_date: New due date (optional, use 'remove' to clear)
    - priority: New priority - 'low', 'medium', or 'high' (optional)
    - session_id: The session the todo belongs to
    - user_id: The user the todo belongs to
    """
    todos = _load_todos(session_id, user_id)

    for todo in todos:
        if todo["id"] == todo_id:
            if content:
                todo["content"] = content
            if due_date is not None:
                todo["due_date"] = None if due_date == "remove" else due_date
            if priority in ["low", "medium", "high"]:
                todo["priority"] = priority

            _save_todos(session_id, todos, user_id)
            return f"✅ Updated todo {todo_id}: '{todo['content']}'"

    return f"Error: Todo {todo_id} not found."



from datetime import datetime
