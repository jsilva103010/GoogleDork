"""Tiny JSON-file persistence layer.

A real deployment would use Postgres, but for this project a single
lock-guarded JSON file is enough to survive restarts and keep the demo
self-contained (no database server to stand up). Every collection is a
dict keyed by id, mirroring how a real ORM table would be addressed.
"""

import json
import threading
from typing import Callable, TypeVar

from app import config
from app.models import (
    AdGroupState,
    Campaign,
    FirmProfile,
    KeywordState,
    OptimizationAction,
)

T = TypeVar("T")

_lock = threading.Lock()

_COLLECTIONS = {
    "firms": FirmProfile,
    "campaigns": Campaign,
    "ad_groups": AdGroupState,
    "keywords": KeywordState,
    "optimization_actions": OptimizationAction,
}


def _empty_db() -> dict:
    return {name: {} for name in _COLLECTIONS}


def _load() -> dict:
    if not config.DB_FILE.exists():
        return _empty_db()
    raw = json.loads(config.DB_FILE.read_text())
    db = _empty_db()
    db.update(raw)
    return db


def _save(db: dict) -> None:
    config.DB_FILE.write_text(json.dumps(db, indent=2, default=str))


def _with_db(fn: Callable[[dict], T]) -> T:
    with _lock:
        db = _load()
        result = fn(db)
        _save(db)
        return result


def put(collection: str, obj) -> None:
    def _do(db):
        db[collection][obj.id] = json.loads(obj.model_dump_json())

    _with_db(_do)


def get(collection: str, obj_id: str):
    model = _COLLECTIONS[collection]
    db = _load()
    raw = db[collection].get(obj_id)
    return model.model_validate(raw) if raw else None


def list_all(collection: str, **filters) -> list:
    model = _COLLECTIONS[collection]
    db = _load()
    items = [model.model_validate(raw) for raw in db[collection].values()]
    for key, value in filters.items():
        items = [item for item in items if getattr(item, key) == value]
    items.sort(key=lambda i: getattr(i, "created_at", 0))
    return items


def delete(collection: str, obj_id: str) -> None:
    def _do(db):
        db[collection].pop(obj_id, None)

    _with_db(_do)


def update(collection: str, obj_id: str, **changes) -> None:
    """Load, mutate a subset of fields, and save back — avoids read-modify-write races."""
    model = _COLLECTIONS[collection]

    def _do(db):
        raw = db[collection].get(obj_id)
        if raw is None:
            return
        obj = model.model_validate(raw)
        updated = obj.model_copy(update=changes)
        db[collection][obj_id] = json.loads(updated.model_dump_json())

    _with_db(_do)
