"""Test bootstrap.

1. Makes the embedded Shopyo app importable (the app lives in
   ``src/angel_claw/app`` and is imported as top-level ``app`` / ``init`` /
   ``modules`` at runtime, so that directory has to be on ``sys.path``).
2. Forces test runs onto throwaway databases.  ``TestingConfig`` falls back to
   ``SQLALCHEMY_DATABASE_URI`` when set, so pointing it at a temp file here
   guarantees no test can ever reach the real user DB
   (``~/.angelclaw/angelclaw.db``) unless a fixture deliberately overrides it.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT / "src" / "angel_claw" / "app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_REAL_USER_DB = os.path.realpath(os.path.expanduser("~/.angelclaw/angelclaw.db"))
_TEST_DB = os.path.realpath(
    os.path.join(tempfile.gettempdir(), f"angelclaw_pytest_{uuid.uuid4().hex}.db")
)
assert not _TEST_DB.startswith(os.path.dirname(_REAL_USER_DB)), (
    f"refusing to point tests at the real user DB dir: {_TEST_DB}"
)
os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_TEST_DB}"


def pytest_sessionfinish(session, exitstatus):
    try:
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)
    except OSError:
        pass
