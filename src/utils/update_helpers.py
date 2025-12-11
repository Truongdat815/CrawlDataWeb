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
    from .chapter_checkpoint import get_chapter_checkpoint_manager
    mgr = get_chapter_checkpoint_manager()
    removed = 0
    for sid in ids:
        try:
            mgr.clear_checkpoint(sid)
            # also remove story summary if exists
            summary_dir = os.path.join(os.path.dirname(config.CHECKPOINT_FILE), "story_checkpoints")
            summary_path = os.path.join(summary_dir, f"story_{sid}.json")
            if os.path.exists(summary_path):
                os.remove(summary_path)
            removed += 1
        except Exception:
            pass
    return removed


def get_story_summary_dir() -> str:
    """Return path to story summary directory (data/story_checkpoints)."""
    summary_dir = os.path.join(os.path.dirname(config.CHECKPOINT_FILE), "story_checkpoints")
    try:
        os.makedirs(summary_dir, exist_ok=True)
    except Exception:
        pass
    return summary_dir
