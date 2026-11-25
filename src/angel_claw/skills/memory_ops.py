import logging
from angel_claw.skills.manager import skill
from angel_claw.runtime.manager import runtime_manager
from asgiref.sync import async_to_sync

logger = logging.getLogger("angel-claw-skills-memory")


def _owner_email(user_id: str, email: str = None) -> str:
    """Use the caller's real identity so skills and the engine share one memory owner."""
    return email or f"user_{user_id}@angelclaw.local"


def _get_memos(session_id: str, user_id: str, email: str):
    from angel_claw.models import UserContext

    context = UserContext(
        user_id=user_id,
        email=email,
        roles=[],
        channel_type="web",
        channel_identifier=session_id,
    )
    runtime = async_to_sync(runtime_manager.get_runtime)(context)
    return runtime.get_memos(session_id)


@skill
def store_memory(
    content: str,
    semantic_type: str = "fact",
    session_id: str = None,
    user_id: str = None,
    email: str = None,
) -> str:
    """
    Saves important information to long-term memory.
    - content: The fact or preference to remember (e.g. 'User lives in Mauritius')
    - semantic_type: 'fact', 'preference', 'insight', or 'task'
    """
    from angel_recall import create_plaintext, SemanticType

    owner = _owner_email(user_id, email)
    memos = _get_memos(session_id, user_id, owner)

    try:
        st = SemanticType(semantic_type.lower())
    except ValueError:
        st = SemanticType.FACT

    cube = create_plaintext(text=content, semantic_type=st, owner=owner)
    cid = memos.api.create(cube, namespace=session_id or f"user_{owner}")
    if not cid:
        return "❌ Could not store memory."

    # Link the new memory to its nearest neighbours so graph traversal can
    # surface related facts later. Chroma provides the similarity ranking.
    try:
        related = memos.vault.semantic_search(content, n_results=4)
        for neighbour in related:
            if (
                neighbour.id != cid
                and neighbour.owner == owner
                and neighbour.semantic_type.value != "dialogue"
            ):
                memos.vault.link_memories(cid, neighbour.id, "related_to")
    except Exception:
        logger.warning("Could not link new memory %s into the graph", cid, exc_info=True)

    return f"✅ Memory stored successfully: {content} ({st.value})"


@skill
def search_memory(
    query: str, session_id: str = None, user_id: str = None, email: str = None
) -> str:
    """
    Searches all long-term memories for information.
    Use this to find past facts, preferences, or details.
    """
    owner = _owner_email(user_id, email)
    memos = _get_memos(session_id, user_id, owner)

    # Semantic retrieval across every namespace owned by this user, with
    # one-hop graph expansion handled by the operator.
    results = memos.operator.hybrid_retrieve(
        query=query, user=owner, namespace=None, n_results=5
    )

    if not results:
        return "No relevant memories found."

    snippets = [
        f"• [{c.semantic_type.value}] {memos.api._format_payload(c.payload, 300)}"
        for c in results
    ]
    return "Found in long-term memory:\n" + "\n".join(snippets)
