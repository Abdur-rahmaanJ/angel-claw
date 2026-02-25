import pytest
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from angel_claw.skills.todo import (
    add_todo,
    list_todos,
    complete_todo,
    delete_todo,
    clear_completed_todos,
    update_todo,
)


@pytest.fixture(autouse=True)
def setup_todo_test(monkeypatch):
    test_dir = "./.angelclaw_test_todos"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    monkeypatch.setattr("angel_claw.skills.todo._get_todos_dir", lambda: test_dir)
    yield
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


def test_add_todo():
    res = add_todo(content="Test todo", priority="high")
    assert "Added todo" in res
    assert "Test todo" in res


def test_add_todo_with_due_date():
    res = add_todo(
        content="Test with due date", due_date="2025-12-31", priority="medium"
    )
    assert "Added todo" in res
    list_res = list_todos()
    assert "2025-12-31" in list_res


def test_list_todos():
    add_todo(content="First todo")
    add_todo(content="Second todo")

    res = list_todos()
    assert "First todo" in res
    assert "Second todo" in res


def test_list_pending_todos():
    add_todo(content="Todo 1")
    add_todo(content="Todo 2")
    complete_todo(todo_id=1)

    res = list_todos(status="pending")
    assert "Todo 2" in res
    assert "Todo 1" not in res or "✅" in res


def test_complete_todo():
    add_todo(content="Complete me")

    res = complete_todo(todo_id=1)
    assert "Completed" in res

    res = list_todos(status="completed")
    assert "Complete me" in res


def test_delete_todo():
    add_todo(content="Delete me")

    res = delete_todo(todo_id=1)
    assert "Deleted" in res

    res = list_todos()
    assert "Delete me" not in res


def test_update_todo():
    add_todo(content="Original content")

    res = update_todo(todo_id=1, content="Updated content", priority="high")
    assert "Updated" in res

    res = list_todos()
    assert "Updated content" in res
    assert "HIGH" in res


def test_clear_completed_todos():
    add_todo(content="Todo 1")
    add_todo(content="Todo 2")
    complete_todo(todo_id=1)

    res = clear_completed_todos()
    assert "Cleared" in res

    res = list_todos()
    assert "Todo 1" not in res
    assert "Todo 2" in res


def test_session_isolation():
    add_todo(content="Session 1 todo", session_id="session1")
    add_todo(content="Session 2 todo", session_id="session2")

    res1 = list_todos(session_id="session1")
    assert "Session 1 todo" in res1
    assert "Session 2 todo" not in res1

    res2 = list_todos(session_id="session2")
    assert "Session 2 todo" in res2
    assert "Session 1 todo" not in res2
