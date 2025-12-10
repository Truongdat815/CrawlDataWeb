# Batch Scraping System - Quick Start Guide

## Overview
This system allows you to mass-scrape multiple books from a Webnovel category.

## Prerequisites
1. **Fresh cookies**: Run `python setup_login.py` to refresh your `cookies.json` with valid login session
2. **Install dependencies**: `pip install playwright tqdm` (if not already installed)

---

## Step 1: Collect Book Links

Run the category link collector:

```powershell
python get_category_links.py
```

**What it does:**
- Opens browser in **VISUAL MODE** (you'll see it scrolling)
- Prompts you for:
  - Category URL (e.g., `https://www.webnovel.com/category/0_action`)
  - Target count (default: 50 books)
- Scrolls down to load books
- Saves links to `books_queue.txt`

**Expected output:**
```
📚 Found 50+ book links
💾 Saved to books_queue.txt
```

---

## Step 2: Batch Scrape Books

Run the batch scraper:

```powershell
python batch_runner.py
```

**What it does:**
- Reads `books_queue.txt`
- Initializes `WebnovelScraper` with:
  - `headless=True` (runs in background)
  - `block_resources=True` (fast mode - blocks images/fonts/css)
  - `output_dir='data/batch_output'` (saves to separate folder)
- **Automatically loads `cookies.json`** before scraping each book
- Shows progress bar (via tqdm)
- Saves each book as separate JSON in `data/batch_output/`

**Options:**
- Enable Fast Mode? (block images/css) → Recommended: **Y**
- Skip already scraped books? → Recommended: **Y**

**Expected output:**
```
🚀 BATCH SCRAPER - WEBNOVEL
📚 Total Books: 50
⚡ Fast Mode: Enabled
✅ Successful: 48/50
❌ Failed: 2/50
💾 Output: data/batch_output/
```

---

## Key Features

### 1. **Cookies Auto-Loading** ✅
- `WebnovelScraper.start()` automatically loads `cookies.json`
- Ensures you get authenticated content (including comments)

### 2. **Fast Mode** ⚡
- Blocks images, fonts, CSS, media
- 3-5x faster scraping
- Reduces bandwidth usage

### 3. **Progress Tracking** 📊
- Real-time progress bar (tqdm)
- Success/failure counters
- Error logging to `batch_error.log`

### 4. **Skip Existing Books** ⏭️
- Checks `data/batch_output/` for existing JSON files
- Skips already-scraped books
- Allows resuming interrupted batches

### 5. **Separate Output Directory** 📁
- Batch results saved to `data/batch_output/`
- Keeps batch scraping separate from single-book scraping
- Easy to organize and review

---

## File Structure

```
project/
├── get_category_links.py       # Step 1: Collect links
├── batch_runner.py             # Step 2: Batch scrape
├── books_queue.txt            # Queue of books to scrape
├── cookies.json               # Your login session (CRITICAL)
├── batch_error.log            # Error log (created if errors occur)
└── data/
    └── batch_output/          # JSON output for batch scraping
        ├── bk_xxxx_Book1.json
        ├── bk_yyyy_Book2.json
        └── ...
```

---

## Important Notes

### ⚠️ Cookies Expiration
- Webnovel hides comments from guests
- If you see books with **0 comments** but you know they have comments:
  1. Run `python setup_login.py` to refresh cookies
  2. Re-run the batch scraper

### ⚠️ Rate Limiting
- The scraper includes 2-second delays between books
- If you get blocked, increase delay in `batch_runner.py` (line ~115)

### ⚠️ Interrupting the Batch
- Press `Ctrl+C` to stop gracefully
- Progress is saved (completed books are in `data/batch_output/`)
- Re-run to resume (with "Skip Existing" enabled)

---

## Troubleshooting

### Problem: "No book URLs found in books_queue.txt"
**Solution:** Run Step 1 first (`python get_category_links.py`)

### Problem: Books have 0 comments
**Solution:** Refresh cookies with `python setup_login.py`

### Problem: Scraper is too slow
**Solution:** Enable Fast Mode when prompted (blocks images/css)

### Problem: Browser crashes or freezes
**Solution:** 
- Close other browser instances
- Reduce parallel processes
- Check available RAM

---

## Example Workflow

```powershell
# 1. Refresh login session
python setup_login.py
# → Login in browser, press Enter

# 2. Collect book links from category
python get_category_links.py
# → Enter category URL
# → Enter target count (50)
# → Watch browser scroll
# → Wait for "Saved to books_queue.txt"

# 3. Batch scrape all books
python batch_runner.py
# → Fast Mode: Y
# → Skip Existing: Y
# → Start? Y
# → Wait for completion (progress bar shows status)

# 4. Check results
ls data/batch_output/
# → Should have 50 JSON files
```

---

## Configuration Options

### Fast Mode (Block Resources)
- **Enabled**: Blocks images, fonts, CSS, media → 3-5x faster
- **Disabled**: Loads all resources → slower but more reliable

### Headless Mode
- **Enabled** (default in batch): No browser window, runs in background
- **Disabled** (category collector): Shows browser for debugging

### Output Directory
- **Default**: `data/json` (single-book scraping)
- **Batch**: `data/batch_output` (mass scraping)

---

## Next Steps After Batch Scraping

1. **Validate results**: Check `data/batch_output/` for JSON files
2. **Review errors**: Check `batch_error.log` for failed books
3. **Import to MongoDB**: Use `import_to_mongodb.py` (if needed)
4. **Re-scrape failures**: Copy failed URLs to new `books_queue.txt` and re-run

---

## Support

If you encounter issues:
1. Check `batch_error.log` for detailed error messages
2. Verify `cookies.json` is valid (run `setup_login.py`)
3. Test with a single book first: `python main.py`
4. Check internet connection and Webnovel accessibility

---

**Happy Scraping!** 🚀
