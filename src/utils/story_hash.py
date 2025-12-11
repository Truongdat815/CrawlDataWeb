from bs4 import BeautifulSoup
# Utility: Extract clean text from Wattpad chapter HTML
def extract_text_from_wattpad_html(html: str) -> str:
    """
    Extracts only the readable text from Wattpad chapter HTML, removing images and formatting tags.
    Returns joined text from all <p> tags except those containing only images.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove all <img> tags
        for img in soup.find_all('img'):
            img.decompose()
        # Get text from <p> tags
        texts = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
        return '\n'.join(texts)
    except Exception as e:
        _safe_print(f"⚠️ Error extracting text from HTML: {e}")
        return html
"""
Utility for generating and persisting a story-level hash based on
the first N characters of the first chapter's text.

Provides:
- compute_story_hash_from_text(text, length=500)
- update_story_hash_from_chapter_content(mongo_db, content_doc, length=500, force=False)

The hash is a SHA-256 hex digest of a normalized (NFKC) and
whitespace-collapsed snippet of the chapter text (first `length` chars).
"""
from hashlib import sha256
import unicodedata
import re
from collections import Counter


def _safe_print(*args, **kwargs):
    try:
        from ..scrapers.base import safe_print as _sp
        return _sp(*args, **kwargs)
    except Exception:
        # Fallback to built-in print if scraper base isn't importable yet
        print(*args, **kwargs)


def _simhash_from_features(features, bits=64):
    """Compute a simhash (int) from iterable of string features.

    Uses SHA-256 to derive a stable digest per feature and reduces to `bits`.
    """
    v = [0] * bits
    counts = Counter(features)
    for feat, weight in counts.items():
        h = int.from_bytes(sha256(feat.encode('utf-8')).digest(), 'big')
        # reduce to `bits` width by taking lower bits
        for i in range(bits):
            bit = (h >> i) & 1
            v[i] += weight if bit else -weight
    # build final int
    result = 0
    for i in range(bits):
        if v[i] > 0:
            result |= (1 << i)
    return result


def compute_story_hash_from_text(text: str, words: int = 500) -> str | None:
    """Compute a 64-bit simhash hex string from the first `words` words of `text`.

    Steps:
    - Normalize unicode (NFKC) and lowercase
    - Extract word tokens, take the first `words`
    - Remove all punctuation and spaces by joining tokens into one string
    - Produce character 4-grams from the joined string as features
    - Compute 64-bit simhash and return as 16-char hex string
    """
    try:
        if not text:
            return None
        # Normalize and lowercase
        normalized = unicodedata.normalize('NFKC', text)
        normalized = normalized.lower()

        # Tokenize by word characters (removes punctuation). This yields words only.
        tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
        if not tokens:
            return None

        # Take first `words` tokens
        selected = tokens[:words]

        # Remove spaces and punctuation by joining tokens (no separators)
        collapsed = ''.join(selected)

        # If collapsed is short, use whole string as single feature
        features = []
        if len(collapsed) < 4:
            features = [collapsed]
        else:
            # character 4-grams
            n = 4
            features = [collapsed[i:i+n] for i in range(0, len(collapsed) - n + 1)]

        sim_int = _simhash_from_features(features, bits=64)
        return format(sim_int, '016x')
    except Exception as e:
        _safe_print(f"⚠️  Error computing story simhash: {e}")
        return None


def hamming_distance(hex1: str, hex2: str) -> int:
    """Return Hamming distance between two 64-bit simhash hex strings."""
    try:
        if not hex1 or not hex2:
            return 64
        i1 = int(hex1, 16)
        i2 = int(hex2, 16)
        x = i1 ^ i2
        # count bits
        return x.bit_count()
    except Exception as e:
        _safe_print(f"⚠️ Error computing hamming distance: {e}")
        return 64


def simhash_similarity(hex1: str, hex2: str) -> float:
    """Return similarity score in [0.0, 1.0] computed as 1 - (hamming/64)."""
    try:
        hd = hamming_distance(hex1, hex2)
        return max(0.0, 1.0 - (hd / 64.0))
    except Exception as e:
        _safe_print(f"⚠️ Error computing simhash similarity: {e}")
        return 0.0


def is_similar(hex1: str, hex2: str, max_distance: int = 3) -> bool:
    """Return True if two simhash hex strings are within `max_distance` bits (Hamming)."""
    try:
        return hamming_distance(hex1, hex2) <= int(max_distance)
    except Exception:
        return False


def update_story_hash_from_chapter_content(mongo_db, content_doc: dict, length: int = 500, force: bool = False) -> str | None:
    """Update the parent story document with a `storyHash` computed from `content_doc['content']`.

    Args:
        mongo_db: pymongo Database object (same as used throughout the project)
        content_doc: dict saved to `chapter_contents` collection (must include `chapterId` and `content`)
        length: number of words to use for the simhash (default 500)
        force: if True, overwrite existing `storyHash` on the story document

    Returns:
        The computed simhash hex string on success, or None on failure / no-op.
    """
    try:
        if mongo_db is None or content_doc is None:
            return None

        # chapterId in chapter_contents may be string numeric, or contentId may be like "<id>_content"
        raw_chapter_id = content_doc.get("chapterId") or ""
        chapter_id = str(raw_chapter_id)
        content_text = content_doc.get("content") or ""
        if not chapter_id or not content_text:
            return None

        chapters_col = mongo_db["chapters"]
        stories_col = mongo_db["stories"]
        chapter_doc = None

        # Build candidate IDs to try (keep as strings; we'll try numeric form at query time)
        candidates = [chapter_id]
        if chapter_id.endswith("_content"):
            candidates.append(chapter_id[:-8])
        # Deduplicate preserve order
        seen = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        for cand in candidates:
            chapter_doc = None
            # try platform id / chapterId as string first
            try:
                chapter_doc = chapters_col.find_one({"webChapterId": cand}) or chapters_col.find_one({"chapterId": cand})
            except Exception:
                chapter_doc = None

            # if not found and cand is numeric, try numeric form
            if not chapter_doc and str(cand).isdigit():
                try:
                    chapter_doc = chapters_col.find_one({"webChapterId": int(cand)}) or chapters_col.find_one({"chapterId": int(cand)})
                except Exception:
                    chapter_doc = None

            if chapter_doc:
                break

        if not chapter_doc:
            _safe_print(f"   ℹ️ Không tìm thấy chapter metadata cho chapterId={chapter_id}; storyHash skip")
            return None

        story_id = chapter_doc.get("storyId")
        if not story_id:
            _safe_print(f"   ℹ️ Chapter {chapter_id} không có field storyId; skip storyHash")
            return None

        story_doc = stories_col.find_one({"storyId": story_id})
        if not story_doc:
            _safe_print(f"   ℹ️ Không tìm thấy story document for storyId={story_id}; cannot set storyHash")
            return None

        if story_doc.get("storyHash") and not force:
            _safe_print(f"   ℹ️ storyHash already exists for storyId={story_id}")
            return story_doc.get("storyHash")

        # Use the content provided in content_doc (no order==0 preference)
        target_text = content_text
        if not target_text:
            return None

        h = compute_story_hash_from_text(target_text, words=length)
        if not h:
            return None

        stories_col.update_one({"storyId": story_id}, {"$set": {"storyHash": h}})
        _safe_print(f"   ✅ storyHash set for storyId={story_id}: {h[:12]}...")
        return h
    except Exception as e:
        _safe_print(f"   ⚠️ Lỗi khi cập nhật storyHash: {e}")
        return None


def _cli_update_missing_hashes(mongo_db=None, uri=None, db_name=None, dry_run=False):
    """CLI helper: scan `chapter_contents` and call update_story_hash_from_chapter_content.

    If `mongo_db` is provided, it will be used directly. Otherwise `uri` and
    `db_name` must be provided to create a `pymongo.MongoClient`.
    Returns (updated_count, skipped_count).
    """
    try:
        from pymongo import MongoClient
    except Exception:
        _safe_print("⚠️ pymongo not available; cannot run CLI updater")
        return 0, 0

    if mongo_db is None:
        if uri is None or db_name is None:
            _safe_print("⚠️ Missing MongoDB configuration for CLI updater")
            return 0, 0
        client = MongoClient(uri)
        mongo_db = client[db_name]

    chapter_col = mongo_db.get_collection('chapter_contents')
    if chapter_col is None:
        _safe_print("⚠️ No `chapter_contents` collection found. Aborting.")
        return 0, 0

    total = chapter_col.count_documents({})
    _safe_print(f"Scanning {total} chapter content documents...")

    updated = 0
    skipped = 0

    for doc in chapter_col.find({}):
        try:
            if dry_run:
                # Attempt compute only (do not write)
                h = compute_story_hash_from_text(doc.get('content') or '', words=500)
                if h:
                    _safe_print(f"[dry] would set storyHash for contentId={doc.get('contentId')} -> {h[:12]}...")
                    updated += 1
                else:
                    skipped += 1
            else:
                res = update_story_hash_from_chapter_content(mongo_db, doc, length=500, force=False)
                if res:
                    updated += 1
                    _safe_print(f"Updated storyHash for contentId={doc.get('contentId')} -> {res[:12]}...")
                else:
                    skipped += 1
        except Exception as e:
            _safe_print(f"Error processing contentId={doc.get('contentId')}: {e}")

    _safe_print(f"Done. Updated: {updated}, Skipped/No-op: {skipped}")
    return updated, skipped


if __name__ == '__main__':
    # Allow running this file directly as a utility. It will read DB config from
    # `src.config` when available.
    try:
        from src import config as _cfg
    except Exception:
        _cfg = None

    mongo_uri = getattr(_cfg, 'MONGODB_URI', None) if _cfg is not None else None
    mongo_db_name = getattr(_cfg, 'MONGODB_DB_NAME', None) if _cfg is not None else None

    if not mongo_uri or not mongo_db_name:
        _safe_print("⚠️ Missing MongoDB configuration in `src.config`. Set `MONGODB_URI` and `MONGODB_DB_NAME` and retry.")
    else:
        _cli_update_missing_hashes(uri=mongo_uri, db_name=mongo_db_name, dry_run=False)
