from typing import Dict, List, Optional
from ..utils.checkpoint import load_checkpoint, save_checkpoint


def compare_and_find_decreased(saved: Dict[str, int], current: Dict[str, int]) -> List[str]:
    decreased = []
    for k, saved_v in saved.items():
        cur_v = int(current.get(k, 0))
        if cur_v < int(saved_v or 0):
            decreased.append(k)
    return decreased


def build_overall(totals: Dict[str, int]) -> int:
    return sum(int(v or 0) for v in totals.values())

