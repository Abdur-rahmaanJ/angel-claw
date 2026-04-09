# Engine Test Strategy

## New File Structure

```
src/angel_claw/engine/
├── __init__.py          # 39 lines - exports
├── api_keys.py          # 134 lines - API key management
├── app_context.py       # 80 lines - Flask app context management
├── config.py            # 10 lines - constants
├── core.py              # 337 lines - main AngelClawEngine class
├── credits.py           # 127 lines - credit service
├── executor.py          # 438 lines - LLM execution logic
├── history.py           # 103 lines - chat history service
├── memory.py            # 60 lines - memory management service
├── message_builder.py   # 122 lines - message construction
├── pairing.py           # 139 lines - channel pairing
└── todos.py             # 63 lines - todo management
```

## Test Structure

```
tests/
└── engine/
    ├── __init__.py
    ├── test_credits.py
    ├── test_history.py
    ├── test_memory.py
    ├── test_todos.py
    ├── test_api_keys.py
    ├── test_pairing.py
    ├── test_message_builder.py
    ├── test_executor.py
    ├── test_app_context.py
    └── conftest.py
```

## Unit Test Recommendations

### High Priority (Easy to test, critical logic)

1. **credits.py** - `CreditService`
   - `calculate_token_cost()` - pure function
   - `check_credits()` - mock DB, test enabled/disabled
   - `deduct_credits()` - mock DB

2. **message_builder.py** - `MessageBuilder`, `MemoryRetriever`
   - `build_system_prompt()` - string formatting
   - `extract_recursion_depth()` - regex parsing
   - `sanitize_memory()` - string replacement
   - `format_memory_context()` - list comprehension

3. **todos.py** - `TodoService`
   - `list_todos()` - mock todo_loader

### Medium Priority (Mockable I/O)

4. **history.py** - `HistoryService`
   - `get_history()` - mock runtime_manager
   - `get_sessions()` - mock PersistentHistory
   - `delete_session()` - mock PersistentHistory

5. **memory.py** - `MemoryService`
   - `get_memories()` - mock runtime
   - `delete_memory()` - mock runtime

6. **app_context.py** - `AppContextManager`
   - `set_app()` - direct test
   - `_app_context()` - mock Flask

### Lower Priority (Heavy integration)

7. **executor.py** - `LlmExecutor`
   - Requires mocking litellm, cache
   - Test caching logic separately

8. **api_keys.py** - `ApiKeyService`
   - Full integration with DB
   - Test via integration tests

9. **pairing.py** - `PairingService`
   - Full integration with DB
   - Test via integration tests

## Test Strategy

### 1. Pure Function Tests
Test functions that have no side effects:
- `CreditService.calculate_token_cost()`
- `MessageBuilder.build_*`
- `MessageBuilder.extract_recursion_depth()`
- `MemoryRetriever.sanitize_memory()`

### 2. Protocol-Based Testing
Use Protocol classes for dependency injection:
```python
# Test with mock
def test_credits_check(mocker):
    mock_settings = mocker.Mock()
    mock_settings.credits_enabled = True
    
    service = CreditService(mock_settings)
    # ... assertions
```

### 3. Integration Tests
For DB-dependent code, use actual test database:
```python
@pytest.fixture
def test_db():
    # Setup test DB
    yield db
    # Teardown
```

### 4. Mocking Strategy
- Use `unittest.mock` for runtime_manager, cache, settings
- Use `pytest-mock` for fixture-based mocking
- Mock litellm at the `litellm.acompletion` level

## Example Test

```python
# tests/engine/test_message_builder.py
import pytest
from angel_claw.engine.message_builder import MessageBuilder, MemoryRetriever

class TestMessageBuilder:
    def test_extract_recursion_depth_found(self):
        builder = MessageBuilder(mock_settings)
        assert builder.extract_recursion_depth("test [RECURSION_DEPTH: 2]") == 2
    
    def test_extract_recursion_depth_not_found(self):
        builder = MessageBuilder(mock_settings)
        assert builder.extract_recursion_depth("test message") == 0
    
    def test_sanitize_memory(self):
        retriever = MemoryRetriever()
        result = retriever.sanitize_memory("---test---")
        assert result == " - test - "
```

## Running Tests

```bash
# Run engine tests only
pytest tests/engine/ -v

# Run with coverage
pytest tests/engine/ --cov=angel_claw.engine --cov-report=html
```

## Notes

- All services use factory functions (`create_*`) enabling easy DI
- Protocols defined in each module for interface testing
- Original `engine.py` is now a compatibility wrapper redirecting to `engine/`
