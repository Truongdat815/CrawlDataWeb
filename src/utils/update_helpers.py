"""Helper utilities for update_stories script.

Centralize small helpers so scripts don't duplicate logic.
"""
import os
import json
from typing import List
from src import config


def load_ids_from_args(args) -> List[str]:
    ids = []
    if getattr(args, 'ids', None):
        parts = [p.strip() for p in args.ids.split(",") if p.strip()]
        ids.extend(parts)
    if getattr(args, 'from_file', None) and args.from_file:
        if not os.path.exists(args.from_file):
            raise FileNotFoundError(args.from_file)
        with open(args.from_file, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s:
                    ids.append(s)
    # Normalize unique preserving order
    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            out.append(i)
            seen.add(i)
    return out


def clear_checkpoints_for(ids: List[str]):
    # Checkpoint file support removed. This helper is deprecated and will no-op.
    return 0


def get_story_summary_dir() -> str:
    """Return path to story summary directory (data/story_checkpoints)."""
    # Checkpoint file support removed — return a path under data/story_checkpoints for compatibility
    summary_dir = os.path.join(os.path.dirname(config.CHECKPOINT_FILE), "story_checkpoints")
    try:
        os.makedirs(summary_dir, exist_ok=True)
    except Exception:
        pass
    return summary_dir
