from typing import Optional
from angel_claw.skills.manager import skill
from angel_claw.runtime.manager import runtime_manager
from asgiref.sync import async_to_sync

@skill
def store_memory(content: str, semantic_type: str = "fact", session_id: str = None, user_id: str = None) -> str:
    """
    Saves important information to long-term memory.
    - content: The fact or preference to remember (e.g. 'User lives in Mauritius')
    - semantic_type: 'fact', 'preference', 'insight', or 'task'
    """
    from angel_claw.models import UserContext
    # We need a context to get the runtime
    # Note: user_id and session_id are injected by the engine
    context = UserContext(
        user_id=user_id,
        email=f"user_{user_id}@angelclaw.local", # Placeholder, engine usually provides better
        roles=[],
        channel_type="web",
        channel_identifier=session_id
    )
    
    runtime = async_to_sync(runtime_manager.get_runtime)(context)
    memos = runtime.get_memos(session_id)
    
    # Use the smart process method with a forced 'store' operation
    # or use the vault directly. Using process is better as it handles distillation triggers.
    from angel_recall import create_plaintext, SemanticType
    
    try:
        st = SemanticType(semantic_type.lower())
    except ValueError:
        st = SemanticType.FACT
        
    cube = create_plaintext(text=content, semantic_type=st, owner=context.email)
    memos.api.create(cube, namespace=session_id)
    
    return f"✅ Memory stored successfully: {content} ({st.value})"

@skill
def search_memory(query: str, session_id: str = None, user_id: str = None) -> str:
    """
    Searches all long-term memories for information.
    Use this to find past facts, preferences, or details.
    """
    from angel_claw.models import UserContext
    context = UserContext(
        user_id=user_id,
        email=f"user_{user_id}@angelclaw.local",
        roles=[],
        channel_type="web",
        channel_identifier=session_id
    )
    
    runtime = async_to_sync(runtime_manager.get_runtime)(context)
    memos = runtime.get_memos(session_id)
    
    # Search globally across all namespaces for the user
    results = memos.operator.hybrid_retrieve(query=query, user=context.email, namespace=None, n_results=5)
    
    if not results:
        return "No relevant memories found."
        
    snippets = []
    for c in results:
        snippets.append(f"• [{c.semantic_type.value}] {c.payload}")
        
    return "Found in long-term memory:\n" + "\n".join(snippets)
