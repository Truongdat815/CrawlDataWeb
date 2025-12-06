"""
UUID v7 Migration Script
Updates all ID generation in webnovel_scraper.py to use UUID v7
"""
import re

file_path = "src/webnovel_scraper.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Update _make_internal_id function to return UUID v7 directly
content = re.sub(
    r'def _make_internal_id\(self, prefix=\'id\'\):\s+return f"{prefix}_{uuid\.uuid4\(\)\.hex\[:12\]}"',
    'def _make_internal_id(self, prefix=\'id\'):\n        """Generate UUID v7 (time-sortable) ID"""\n        return str(uuid6.uuid7())',
    content,
    flags=re.MULTILINE
)

# Replace all _make_internal_id() calls with direct uuid6.uuid7()
content = re.sub(
    r'self\._make_internal_id\(self\._id_prefix_comment\)',
    'str(uuid6.uuid7())',
    content
)

content = re.sub(
    r'self\._make_internal_id\(self\._id_prefix_reply\)',
    'str(uuid6.uuid7())',
    content
)

content = re.sub(
    r'self\._make_internal_id\(self\._id_prefix_chapter\)',
    'str(uuid6.uuid7())',
    content
)

# Replace old UUID v4 patterns
content = re.sub(
    r'f"bk_{uuid\.uuid4\(\)\.hex\[:12\]}"',
    'str(uuid6.uuid7())',
    content
)

content = re.sub(
    r'f"ch_{uuid\.uuid4\(\)\.hex\[:12\]}"',
    'str(uuid6.uuid7())',
    content
)

# Save
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ UUID v7 migration completed!")
print("   - Updated _make_internal_id() function")
print("   - Replaced all uuid.uuid4() with uuid6.uuid7()")
print("   - Updated comment/reply/chapter ID generation")
