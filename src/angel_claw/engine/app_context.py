import logging
import os
import sys
import threading
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("angel-claw-engine-appctx")

_cached_app = None
_app_lock = threading.Lock()


class AppContextManager:
    def __init__(self, settings):
        self._settings = settings

    @property
    def cached_app(self):
        return _cached_app

    def set_app(self, app):
        global _cached_app
        with _app_lock:
            _cached_app = app

    @contextmanager
    def _app_context(self):
        if self._settings.auth_mode == "shopyo":
            try:
                from flask import has_app_context, current_app

                if has_app_context():
                    logger.debug("Using existing Flask app context")
                    yield current_app.app_context()
                    return
            except ImportError:
                pass

            with _app_lock:
                if _cached_app:
                    logger.debug("Using cached Flask app")
                    yield _cached_app.app_context()
                    return

                logger.info(
                    "Engine: No app context available and no cached app. Creating one."
                )
                try:
                    import importlib.resources

                    pkg_root = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..")
                    )
                    if pkg_root not in sys.path:
                        sys.path.insert(0, pkg_root)

                    app_dir = importlib.resources.files("angel_claw").joinpath("app")
                    app_path_str = str(app_dir)
                    if app_path_str not in sys.path:
                        sys.path.insert(0, app_path_str)

                    from app import create_app

                    config_name = os.environ.get("FLASK_ENV", "production")
                    _cached_app = create_app(config_name)
                    yield _cached_app.app_context()
                except Exception as e:
                    logger.error(f"Engine: Failed to create fallback app context: {e}")
                    import traceback

                    logger.error(traceback.format_exc())
                    yield None
        else:
            yield None


def create_app_context_manager(settings) -> AppContextManager:
    return AppContextManager(settings)
