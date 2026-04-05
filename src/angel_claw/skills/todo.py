import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from angel_claw.skills.manager import skill
from angel_claw.config import settings
from angel_claw.utils import get_user_root

def _get_todos_dir(user_id: Optional[str] = None) -> str:
    if user_id:
        user_root = get_user_root(user_id)
        todos_dir = user_root / "todos"
    else:
        base_dir = os.path.join(os.getcwd(), ".angelclaw")
        todos_dir = Path(os.path.join(base_dir, "todos"))
    if not todos_dir.exists():
        todos_dir.mkdir(parents=True, exist_ok=True)
    return str(todos_dir)

def _get_todos_file(session_id: str, user_id: Optional[str] = None) -> str:
    return os.path.join(_get_todos_dir(user_id), f"{session_id}.json")

def _load_todos(session_id: str, user_id: Optional[str] = None) -> List[dict]:
    filepath = _get_todos_file(session_id, user_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []

def _save_todos(session_id: str, todos: List[dict], user_id: Optional[str] = None):
    filepath = _get_todos_file(session_id, user_id)
    with open(filepath, "w") as f:
        json.dump(todos, f, indent=2)

@skill
def add_todo(content: str, due_date: Optional[str] = None, priority: str = "medium", session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
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
        p = todo.get("priority", "medium").upper()
        due = f" (Due: {todo.get('due_date')})" if todo.get("due_date") else ""
        lines.append(f"{check} [{p}] {todo['id']}. {todo['content']}{due}")
    return "\n".join(lines)

@skill
def complete_todo(todo_id: int, session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    todos = _load_todos(session_id, user_id)
    for todo in todos:
        if todo["id"] == todo_id:
            todo["completed"] = True
            todo["completed_at"] = datetime.now().isoformat()
            _save_todos(session_id, todos, user_id)
            return f"✅ Completed todo {todo_id}: '{todo['content']}'"
    return f"Error: Todo {todo_id} not found."

@skill
def delete_todo(todo_id: int, session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    todos = _load_todos(session_id, user_id)
    original_count = len(todos)
    todos = [t for t in todos if t["id"] != todo_id]
    if len(todos) == original_count:
        return f"Error: Todo {todo_id} not found."
    for i, todo in enumerate(todos, 1):
        todo["id"] = i
    _save_todos(session_id, todos, user_id)
    return f"🗑️ Deleted todo {todo_id}."

@skill
def update_todo(todo_id: int, content: Optional[str] = None, due_date: Optional[str] = None, priority: Optional[str] = None, session_id: str = "cli-default", user_id: Optional[str] = None) -> str:
    todos = _load_todos(session_id, user_id)
    for todo in todos:
        if todo["id"] == todo_id:
            if content: todo["content"] = content
            if due_date is not None: todo["due_date"] = None if due_date == "remove" else due_date
            if priority in ["low", "medium", "high"]: todo["priority"] = priority
            _save_todos(session_id, todos, user_id)
            return f"✅ Updated todo {todo_id} successfully."
    return f"Error: Todo {todo_id} not found."
