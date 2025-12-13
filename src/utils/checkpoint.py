import os
import json
from datetime import datetime
from typing import Optional, Any


CHECKPOINT_DIR = os.path.join(os.getcwd(), 'data', 'checkpoints')


def _ensure_dir():
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def _path_for(kind: str, resource_id: str) -> str:
    _ensure_dir()
    safe = str(resource_id).replace('/', '_')
    return os.path.join(CHECKPOINT_DIR, f"{kind}_{safe}.json")


def load_checkpoint(resource_id: str, kind: str = 'comments') -> Optional[dict]:
    """Load checkpoint for given kind (comments|chapters|content)."""
    p = _path_for(kind, resource_id)
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def save_checkpoint(resource_id: str, kind: str = 'comments', payload: Optional[Any] = None, next_cursor=None, finished=False, extra: dict | None = None):
    """Save a checkpoint for resource_id of `kind`.

    - For `comments`: payload is unused (we store cursor/finished).
    - For `chapters`: payload can be the list of parts (to cache the chapter list).
    - For `content`: payload is optional metadata about content fetch status.
    """
    p = _path_for(kind, resource_id)
    data: dict = {
        kind[:-1] + 'Id' if kind.endswith('s') else kind + 'Id': str(resource_id),
        'next_cursor': next_cursor,
        'finished': bool(finished),
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }
    if payload is not None:
        data['payload'] = payload
    if extra:
        data.update(extra)
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def remove_checkpoint(resource_id: str, kind: str = 'comments'):
    p = _path_for(kind, resource_id)
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
