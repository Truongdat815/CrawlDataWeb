# 🚀 SYSTEM OVERHAUL - COMPLETE EXECUTION GUIDE

## ✅ ALL UPDATES COMPLETED

### 🎯 What's Been Updated:

1. **✅ Dependencies Installed**
   - uuid6 (UUID v7 generation)
   - pymongo (MongoDB driver)
   - python-dotenv (environment variables)

2. **✅ Config Updated** (`src/config.py`)
   - Team VPS MongoDB: `mongodb://user:56915001@103.90.224.232:27017/my_database`
   - Final Schema Collections: stories, chapters, chapter_contents, comments, users, websites

3. **✅ Batch Runner Updated** (`batch_runner.py`)
   - Default: Scrape ALL chapters (no limit)
   - Process isolation (no async errors)
   - Resume capability (checks platform_id)

4. **✅ Single Book Runner Updated** (`single_book_runner.py`)
   - Supports `--chapters None` for all chapters
   - Optimal Cloudflare bypass settings

5. **✅ Import Script REWRITTEN** (`import_to_mongodb.py`)
   - Complete Final Schema transformation
   - UUID v7 BSON Binary for all IDs
   - Proper collection separation
   - Field mapping and null handling
   - Resume-safe (checks platform_id before insert)

---

## 📋 EXECUTION PLAN (Tonight)

### Step 1: Get Book URLs (5-10 books)
```powershell
python get_category_links.py
```
**What to do:**
- Enter a category URL (e.g., https://www.webnovel.com/category/0_action)
- Wait for scrolling to load ~10 books
- URLs will be saved to `books_queue.txt`

---

### Step 2: Scrape 3 Complete Books
```powershell
python batch_runner.py --limit 3
```

**What happens:**
- Scrapes 3 books from `books_queue.txt`
- Each book runs in a separate process (no async errors!)
- Scrapes ALL chapters (no limit)
- Visual mode (best Cloudflare bypass)
- Saves to `data/json/`
- **Time estimate:** 15-30 minutes per book (depending on chapter count)

**Monitor:**
- Watch browser open/close for each book
- Check terminal for progress
- Errors logged to `batch_errors.log`

---

### Step 3: Transform & Import to Team MongoDB
```powershell
python import_to_mongodb.py
```

**What happens:**
- Reads all JSON files from `data/json/`
- Transforms to Final Schema structure:
  - **websites**: Platform info (Webnovel)
  - **users**: Authors and commenters
  - **stories**: Novel metadata (UUID v7 BSON)
  - **chapters**: Chapter metadata
  - **chapter_contents**: Chapter text (separate collection)
  - **comments**: All comments and replies
- Converts all IDs to UUID v7 BSON Binary
- Maps fields (nulls where data unavailable)
- Upserts based on platform_id (safe to re-run)

**Expected Output:**
```
📊 Total Imported:
   ✅ Stories: 3
   ✅ Chapters: ~150 (depends on books)
   ✅ Chapter Contents: ~150
   ✅ Comments: ~100+
   ✅ Users: ~50+
```

---

### Step 4: Verify in MongoDB Compass

**Connection String:**
```
mongodb://user:56915001@103.90.224.232:27017/my_database
```

**Database:** `my_database`

**Collections to Check:**
- `websites` → Should have 1 doc (Webnovel)
- `users` → Authors + commenters
- `stories` → 3 documents (your scraped books)
- `chapters` → All chapters from 3 books
- `chapter_contents` → Text content
- `comments` → All comments and replies

**Verify UUID Format:**
- Click on a story document
- Check `_id` field → Should show `Binary` type (not String!)
- Check `story_id` in chapters → Should also be `Binary`

---

## 🔍 FINAL SCHEMA FIELD MAPPING

### Stories Collection:
```javascript
{
  _id: Binary(UUID v7),
  platform_id: "wn_123456789",  // Original Webnovel ID
  website_id: Binary(UUID v7),
  story_name: "Book Title",
  story_url: "https://...",
  user_id: Binary(UUID v7),  // Author
  description: "...",
  cover_image_url: "...",
  status: "Ongoing" | "Completed",
  category: "Fantasy",
  tags: ["Adventure", "Magic"],
  total_views: 1234567,
  total_chapters: 150,
  power_ranking_position: 3,
  power_ranking_title: "Originals' Power Ranking",
  overall_rating: 4.5,
  total_ratings: 1000,
  writing_quality: 4.5,
  stability_of_updates: 4.0,
  story_development: 4.5,
  character_design: 4.5,
  world_background: 4.5,
  created_at: ISODate(...),
  updated_at: ISODate(...),
  // Fields not in Webnovel (null)
  language: null,
  is_completed: true/false,
  last_chapter_published_at: null
}
```

### Chapters Collection:
```javascript
{
  _id: Binary(UUID v7),
  platform_id: "wn_ch_...",
  story_id: Binary(UUID v7),  // Links to story
  order: 1,
  title: "Chapter 1: The Beginning",
  chapter_url: "https://...",
  published_at: ISODate(...),
  created_at: ISODate(...),
  // Fields not in Webnovel
  view_count: null,
  is_locked: true/false  // Detected by content length
}
```

### Chapter Contents Collection:
```javascript
{
  _id: Binary(UUID v7),
  chapter_id: Binary(UUID v7),  // Links to chapter
  content_text: "Full chapter text...",
  word_count: 2500,
  created_at: ISODate(...)
}
```

### Comments Collection:
```javascript
{
  _id: Binary(UUID v7),
  platform_id: "wn_cmt_...",
  story_id: Binary(UUID v7),
  chapter_id: Binary(UUID v7) | null,  // null for book-level comments
  user_id: Binary(UUID v7),
  parent_comment_id: Binary(UUID v7) | null,  // null for top-level, set for replies
  content: "Comment text",
  posted_at: ISODate(...),
  score: 5.0,
  created_at: ISODate(...),
  // Fields not in Webnovel
  like_count: null,
  is_edited: false
}
```

---

## ⚠️ IMPORTANT NOTES

1. **Visual Mode (No Headless):**
   - Headless mode gets blocked by Cloudflare
   - Let the browser window open for each book
   - Don't minimize or click during scraping

2. **Internet Connection:**
   - Stable connection required
   - If timeout, script will retry
   - Check `batch_errors.log` for failures

3. **MongoDB Connection:**
   - Ensure VPN/network allows connection to 103.90.224.232
   - Test connection in MongoDB Compass first

4. **Resume Capability:**
   - If scraping stops, just re-run `batch_runner.py`
   - Already-scraped books will be skipped (checks JSON files)
   - Import script also checks platform_id (safe to re-run)

5. **UUID v7 BSON:**
   - All IDs are Binary type (not String)
   - Sortable by time (v7 feature)
   - Optimal MongoDB performance

---

## 🎯 SUCCESS CRITERIA

After completion, you should have:

- [x] 3 JSON files in `data/json/` (complete book data)
- [x] 3 stories in MongoDB `stories` collection
- [x] ~150 chapters in `chapters` collection
- [x] ~150 contents in `chapter_contents` collection
- [x] ~100+ comments in `comments` collection
- [x] ~50+ users in `users` collection
- [x] 1 website in `websites` collection (Webnovel)
- [x] All `_id` fields are Binary type (UUID v7)
- [x] No duplicate stories (platform_id is unique)
- [x] Proper foreign key relationships (story_id, chapter_id, user_id, etc.)

---

## 🚨 TROUBLESHOOTING

### Issue: "No books_queue.txt found"
**Solution:** Run `python get_category_links.py` first

### Issue: "MongoDB connection timeout"
**Solution:** Check network/firewall, test in MongoDB Compass

### Issue: "Browser crashes or hangs"
**Solution:** Kill chrome.exe processes, restart batch_runner

### Issue: "Only 2 comments found (expected more)"
**Solution:** Check `data/debug/*.html` files, verify cookies.json exists

### Issue: "Import script shows 'platform_id already exists'"
**Solution:** This is normal (resume-safe), story was already imported

---

## 📞 READY TO START?

Run these commands in order:

```powershell
# 1. Get URLs
python get_category_links.py

# 2. Scrape 3 books (full chapters)
python batch_runner.py --limit 3

# 3. Import to Team MongoDB (Final Schema)
python import_to_mongodb.py

# 4. Verify in MongoDB Compass
# Connection: mongodb://user:56915001@103.90.224.232:27017/my_database
```

**Good luck! 🚀**
