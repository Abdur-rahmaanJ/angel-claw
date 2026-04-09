import logging
from typing import List, Protocol
from ..models import UserContext, Todo

logger = logging.getLogger("angel-claw-engine-todos")


class TodoServiceProtocol(Protocol):
    """Protocol for todo service - enables dependency injection."""

    def list_todos(self, context: UserContext) -> List[Todo]: ...

    def create_todo(
        self, context: UserContext, content: str, priority: str = "medium"
    ) -> Todo: ...

    def complete_todo(self, context: UserContext, todo_id: str): ...

    def delete_todo(self, context: UserContext, todo_id: str): ...


class TodoService:
    """Todo service for managing user todos with DI support."""

    def __init__(self, todo_loader=None):
        """
        Args:
            todo_loader: Callable that loads todos. If None, imports from angel_claw.skills.todo.
        """
        self._todo_loader = todo_loader

    def _get_todo_loader(self):
        if self._todo_loader:
            return self._todo_loader
        from angel_claw.skills.todo import _load_todos

        return _load_todos

    def list_todos(self, context: UserContext) -> List[Todo]:
        """List all todos for a user."""
        todos_data = self._get_todo_loader()(
            context.channel_identifier, user_id=context.user_id
        )

        todos = []
        for t in todos_data:
            todos.append(
                Todo(
                    id=str(t.get("id")),
                    content=t.get("content"),
                    completed=t.get("completed", False),
                    priority=t.get("priority", "medium"),
                    due_date=t.get("due_date"),
                    created_at=t.get("created_at"),
                    completed_at=t.get("completed_at"),
                )
            )
        return todos


def create_todo_service(todo_loader=None) -> TodoService:
    """Factory function to create a TodoService."""
    return TodoService(todo_loader)
