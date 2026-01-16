"""
Factory to provide search engine and database implementations depending on settings.
If environment USE_FAKE_DB is set, return the fake in-memory implementations.
Otherwise fall back to the project's real classes.
"""
from typing import Any
import os

_USE_FAKE = os.getenv("USE_FAKE_DB", os.getenv("TEST_MODE", "0")).lower() in ("1", "true", "yes")

if _USE_FAKE:
    from src.fake_search_engine import create_fake_search_engine as _create_search
    from src.fake_database import create_fake_database as _create_db
else:
    # Lazy imports for real implementations
    try:
        from src.search_engine import SearchEngine as _SearchEngine
    except Exception:
        _SearchEngine = None
    try:
        from src.vector_db import VectorDB as _VectorDB
    except Exception:
        _VectorDB = None
    def _create_search():
        if _SearchEngine is None:
            raise RuntimeError("Real SearchEngine not available in this environment")
        return _SearchEngine()
    def _create_db():
        return None

_search_instance = None
_db_instance = None

def get_search_engine() -> Any:
    global _search_instance
    if _search_instance is None:
        _search_instance = _create_search()
    return _search_instance

def get_database() -> Any:
    global _db_instance
    if _db_instance is None:
        _db_instance = _create_db()
    return _db_instance
