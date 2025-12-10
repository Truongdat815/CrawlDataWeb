# Chapter Comments Bug Fixes - Summary

## Issues Identified

### Bug A: Wrong Username
**Problem:** The `user_name` field contained the **comment content** instead of the actual username.

**Example from corrupted JSON:**
```json
{
  "user_name": "Thanks for the chapter",  // ❌ WRONG - This is the content!
  "content": "Thanks for the chapter"
}
```

**Root Cause:** The CSS selector was too generic and grabbed the content div instead of the username element.

### Bug B: Missing Replies
**Problem:** The `replies` array was always empty `[]`, even for comments with visible replies.

**Root Cause:** The scraper was not clicking the "View Reply" button to expand nested comments.

---

## Fixes Applied to `webnovel_scraper.py`

### Fix 1: Username Extraction (`_parse_single_chapter_comment`)

**Strategy (Priority Order):**

1. **Try `data-ejs` attribute first** (Most Reliable)
   - Extract from JSON: `ejs_data.get('userName')`
   - Also get `userId` if available

2. **Try profile link in header** (Specific Selector)
   - `.m-comment-hd a[href*='/profile/']` (header area only)
   - Get `title` attribute first, fallback to `innerText`
   - Extract user ID from `href`

3. **Try `.g_txt_over` class** (Webnovel Specific)
   - Validate it's a username (not content):
     - Length < 50 characters
     - No newlines

**Key Changes:**
- ✅ Prioritize `data-ejs` over DOM selectors
- ✅ Use specific selectors (`.m-comment-hd a`) instead of generic (`a`)
- ✅ Validate extracted text (length, no newlines)
- ✅ Extract user ID from profile link

---

### Fix 2: Reply Extraction (`_parse_single_chapter_comment`)

**Strategy:**

1. **Find Reply Button**
   - Search for buttons with text containing "repl", "view", "reply"
   - Check for reply count in text (e.g., "View 3 replies")
   - Try selectors: `.j_reply_btn`, `a:has-text('repl')`, etc.

2. **Click to Expand**
   - Scroll button into view
   - Click the button
   - Wait 1.5 seconds for animation

3. **Find Reply Container**
   - Look for: `.reply-list`, `.replies`, `[class*='reply-list']`
   - Find individual items: `.reply-item`, `[class*='reply-item']`

4. **Parse Each Reply**
   - Call `_parse_single_reply()` for each item
   - Add to `replies` array

**Key Changes:**
- ✅ Implemented button clicking logic
- ✅ Added wait time for reply expansion
- ✅ Search for reply container first, then items
- ✅ Added debug logging for reply extraction

---

### Fix 3: Reply Parsing (`_parse_single_reply`)

**Improvements:**
- ✅ Try `data-ejs` first for username
- ✅ Validate username (length < 50, no newlines)
- ✅ Extract user ID from profile link
- ✅ Better content extraction (avoid username duplication)
- ✅ Return full structure with `comment_id`, `parent_id`, `user_id`

**New Reply Structure:**
```json
{
  "comment_id": "rep_xxxx",
  "parent_id": "cmt_yyyy",
  "user_id": "wn_zzzz",
  "user_name": "ActualUsername",
  "time": "1mth",
  "content": "Actual reply content",
  "replies": []
}
```

---

## Refetch Script: `refetch_chapter_comments.py`

### Purpose
Re-scrape all chapter comments for a book using the FIXED logic and overwrite corrupted data.

### Features
- ✅ Loads existing JSON file
- ✅ Uses authenticated cookies (`cookies.json`)
- ✅ Re-scrapes each chapter sequentially
- ✅ Overwrites old `comments` arrays
- ✅ **Saves after each chapter** (incremental progress)
- ✅ Creates backup (`.backup` file)
- ✅ Shows progress and stats

### Usage

```powershell
# Step 1: Ensure you have fresh cookies
python setup_login.py

# Step 2: Run refetch script
python refetch_chapter_comments.py "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json"
```

### Safety Features
- **Atomic Writes:** Uses temp file + rename to prevent corruption
- **Backup:** Creates `.backup` file before overwriting
- **Incremental Save:** Saves after each chapter (resume-friendly)
- **Keyboard Interrupt:** Saves current progress on Ctrl+C

### Output

```
🔄 REFETCH CHAPTER COMMENTS
================================================================================
File: data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json
================================================================================

📖 Book: Avatar TLAB: Tai Lung
📚 Total Chapters: 51
✅ Found cookies.json (will use for authentication)

Re-scrape comments for 51 chapters? [Y/n]: y

================================================================================
🚀 Starting refetch process...
================================================================================

[1/51] Chapter 1 - A New Beginning
   URL: https://www.webnovel.com/book/...
   Old comments: 15
   🌐 Loading chapter page...
   💬 Scraping comments...
   ✅ New comments: 18
   💬 Total replies: 5
   💾 Saving progress...
   ✅ Saved

[2/51] Chapter 2 - Fire and Fury
   ...

================================================================================
📊 REFETCH COMPLETE
================================================================================
✅ Successful: 51/51
❌ Failed: 0/51
💬 Total comments collected: 432
💾 Updated file: data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json
🔙 Original backup: data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json.backup
================================================================================
```

---

## Testing the Fixes

### Before Running Refetch
1. **Check current data:**
   ```powershell
   Get-Content "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json" | Select-String -Pattern '"user_name":' -Context 0,1 | Select-Object -First 5
   ```
   
   **Expected (Corrupted):**
   ```json
   "user_name": "Thanks for the chapter",
   "content": "Thanks for the chapter",
   ```

### After Running Refetch
1. **Check fixed data:**
   ```powershell
   Get-Content "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json" | Select-String -Pattern '"user_name":' -Context 0,1 | Select-Object -First 5
   ```
   
   **Expected (Fixed):**
   ```json
   "user_name": "ActualUsername123",
   "content": "Thanks for the chapter",
   ```

2. **Check for replies:**
   ```powershell
   Get-Content "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json" | Select-String -Pattern '"replies": \[' -Context 1,0 | Select-Object -First 5
   ```
   
   **Expected:** Some comments should now have non-empty replies arrays.

---

## Validation Checklist

After refetch, verify:

- [ ] `user_name` contains actual usernames (not content)
- [ ] `user_name` != `content` (should be different)
- [ ] Usernames are short (< 50 chars, no newlines)
- [ ] Some comments have `replies` arrays with items
- [ ] Reply structure includes `parent_id` reference
- [ ] Backup file exists (`.backup`)
- [ ] Chapter count unchanged (51 chapters)
- [ ] No data loss (compare backup vs new file)

---

## Rollback Instructions

If the refetch corrupts data:

```powershell
# Restore from backup
Copy-Item "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json.backup" "data\json\bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json" -Force
```

---

## Next Steps

1. **Test on one chapter first** (modify script to process only chapter 1)
2. **Verify output** (check username and replies)
3. **Run full refetch** for all 51 chapters
4. **Validate results** using checklist above
5. **Delete backup** once confirmed working

---

## Common Issues

### Issue: Still getting wrong usernames
**Solution:** 
- Check HTML structure with browser DevTools
- Update selectors in `_parse_single_chapter_comment`
- Try different priority order for username extraction

### Issue: Replies still empty
**Solution:**
- Check if reply button exists on page
- Verify button selector (`.j_reply_btn`, etc.)
- Check if login is required (refresh `cookies.json`)
- Increase wait time after clicking (change `time.sleep(1.5)` to `3`)

### Issue: Script crashes mid-refetch
**Solution:**
- Press Ctrl+C to save progress
- Check saved file (progress is preserved)
- Re-run script (it will resume from start but skip completed chapters if you implement skip logic)

---

## Performance Notes

- **Duration:** ~5-10 seconds per chapter
- **Total Time:** ~5-10 minutes for 51 chapters
- **Network:** ~500KB per chapter (with images blocked)
- **Storage:** Backup adds ~2MB disk usage

---

**Status:** ✅ Ready to test!
