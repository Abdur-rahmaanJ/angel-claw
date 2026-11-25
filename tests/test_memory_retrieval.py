from types import SimpleNamespace

from angel_claw.engine.message_builder import MemoryRetriever


class FakeOperator:
    def __init__(self, cubes):
        self.cubes = cubes
        self.calls = []

    def hybrid_retrieve(self, **kwargs):
        self.calls.append(kwargs)
        return self.cubes


class FakeMemos:
    def __init__(self, cubes):
        self.operator = FakeOperator(cubes)
        self.api = SimpleNamespace(_format_payload=lambda payload, limit: str(payload)[:limit])


def _cube(text):
    from datetime import datetime

    return SimpleNamespace(
        payload=text,
        timestamp=datetime(2026, 1, 1),
        semantic_type=SimpleNamespace(value="fact"),
    )


def test_retrieve_searches_by_query_not_by_namespace_recency():
    cube = _cube("User lives in Mauritius")
    memos = FakeMemos([cube])
    context = SimpleNamespace(email="user@example.com")

    result = MemoryRetriever().retrieve(
        memos, context, "where do I live?", use_global=False
    )

    assert result == [cube]
    call = memos.operator.calls[0]
    assert call["query"] == "where do I live?"
    assert call["user"] == "user@example.com"
    assert call["namespace"] is None


def test_empty_query_does_not_inject_random_memories():
    memos = FakeMemos([_cube("Unrelated fact")])
    context = SimpleNamespace(email="user@example.com")

    assert MemoryRetriever().retrieve(memos, context, "") == []
    assert memos.operator.calls == []


def test_format_memory_context_reads_naturally():
    cube = _cube("User lives in Mauritius")
    cube.payload = "User lives in Mauritius"
    context = ""

    output = MemoryRetriever().format_memory_context([cube], FakeMemos([]))

    assert "Relevant Memory Context" in output
    assert "Mauritius" in output
