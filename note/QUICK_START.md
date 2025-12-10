# 🚀 QUICK START - FRIDAY DEADLINE EXECUTION

## ✅ SYSTEM STATUS: READY

All updates complete! Your system now supports the Full Final Schema with 9 collections.

---

## 📋 3-STEP EXECUTION PLAN

### **STEP 1: Get Book URLs** (2 minutes)
```powershell
python get_category_links.py
```
- Pick a category (e.g., Fantasy, Action)
- Wait for ~10 book URLs to load
- Press Ctrl+C to stop
- Result: `books_queue.txt` with URLs

---

### **STEP 2: Scrape 3 Books** (30-60 minutes)
```powershell
python batch_runner.py --limit 3
```

**What happens:**
- Scrapes **ALL chapters** from each book (no limits)
- Visual mode (best Cloudflare bypass)
- 10s delay between books
- Process isolation (no errors!)

**Expected time:** 10-20 minutes per book

**Monitor:** Watch browser windows open/close

---

### **STEP 3: Import to MongoDB** (2 minutes)
```powershell
python import_to_mongodb.py
```

**What happens:**
- Reads all JSON files from `data/json/`
- Transforms to Final Schema (9 collections)
- UUID v7 → BSON Binary conversion
- Imports to Team VPS MongoDB

**Expected output:**
```
✅ Stories: 3
✅ Chapters: ~150
✅ Chapter Contents: ~150
✅ Comments: ~50
✅ Reviews: ~20         ✨ NEW
✅ Rankings: 3          ✨ NEW
✅ Scores: 3            ✨ NEW
✅ Users: ~30
```

---

## 🎯 NEW COLLECTIONS EXPLAINED

### **Reviews** (Book reviews with ratings)
- Source: Book-level comments that have `score.overall`
- Fields: `rating`, `content`, `user_id`, `posted_at`

### **Rankings** (Power Rankings)
- Source: `power_ranking_position` + `power_ranking_title`
- Fields: `position`, `ranking_title`, `story_id`

### **Scores** (Rating Breakdown)
- Source: `ratings{}` object from scraper
- Fields: `overall_score`, `writing_quality`, `stability_of_updates`, etc.

---

## 📊 COMPLETE SCHEMA (9 Collections)

1. **websites** - Platform (Webnovel)
2. **users** - Authors + Commenters
3. **stories** - Novel metadata
4. **chapters** - Chapter metadata
5. **chapter_contents** - Chapter text
6. **comments** - User comments
7. **reviews** - User reviews with ratings ✨
8. **rankings** - Power rankings ✨
9. **scores** - Rating breakdown ✨

---

## 🔍 VERIFY IN MONGODB COMPASS

**Connection:**
```
mongodb://user:56915001@103.90.224.232:27017/my_database
```

**Database:** `my_database`

**Check:**
- All 9 collections exist
- `_id` fields are **Binary** type (not String)
- `story_id`, `user_id`, `chapter_id` are **Binary**

---

## ⚠️ TROUBLESHOOTING

### Browser crashes?
```powershell
# Kill chrome processes and restart
taskkill /F /IM chrome.exe
python batch_runner.py --limit 3
```

### MongoDB connection timeout?
- Check network/VPN
- Test in MongoDB Compass first

### No books_queue.txt?
- Run `python get_category_links.py` first

---

## 🎯 SUCCESS CRITERIA

After execution, you should have:
- ✅ 3 JSON files in `data/json/`
- ✅ 3 stories in MongoDB
- ✅ ~150 chapters
- ✅ All 9 collections populated
- ✅ UUID v7 Binary format
- ✅ No errors in import log

---

## 🚀 START NOW!

Run these 3 commands in order:

```powershell
python get_category_links.py
python batch_runner.py --limit 3
python import_to_mongodb.py
```

**Good luck! 🎉**
