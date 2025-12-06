"""
Batch Runner - Process Isolation Strategy
Launches single_book_runner.py as a subprocess for each book to avoid:
- Playwright async loop conflicts
- Memory leaks
- Cloudflare fingerprint tracking
- Browser session pollution

Usage:
    python batch_runner.py [--limit N] [--chapters N] [--force] [--headless] [--fast]
"""
import os
import time
import re
import sys
import argparse
import subprocess
from pathlib import Path


def extract_book_id(url):
    """Extract numeric book ID from URL"""
    match = re.search(r'_(\d+)$', url)
    if match:
        return match.group(1)
    match = re.search(r'(\d{6,})', url)
    return match.group(1) if match else None


def already_scraped(book_id):
    """Check if book already exists in data/json/"""
    if not book_id:
        return False
    
    json_dir = Path('data/json')
    if not json_dir.exists():
        return False
    
    # Look for any JSON file containing this book ID
    for json_file in json_dir.glob('*.json'):
        if book_id in json_file.name:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Batch scrape Webnovel books using process isolation')
    parser.add_argument('--limit', type=int, default=3, help='Number of books to scrape (default: 3)')
    parser.add_argument('--chapters', type=int, default=None, help='Max chapters per book (default: None = ALL chapters)')
    parser.add_argument('--force', action='store_true', help='Re-scrape existing books')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode (NOT recommended - Cloudflare blocks this)')
    parser.add_argument('--fast', action='store_true', help='Enable fast mode (block resources)')
    parser.add_argument('--sleep', type=float, default=10.0, help='Seconds to sleep between books (default: 10)')
    parser.add_argument('--shutdown', action='store_true', help='Shutdown computer after batch completes')
    parser.add_argument('--sleep-pc', action='store_true', help='Sleep computer after batch completes')
    args = parser.parse_args()
    
    print("="*70)
    print("🏭 BATCH RUNNER - PROCESS ISOLATION MODE")
    print("="*70)
    print(f"⚙️  Configuration:")
    print(f"   📚 Books to process: {args.limit}")
    print(f"   📄 Chapters per book: {args.chapters}")
    print(f"   👁️  Headless: {args.headless} {'⚠️  (NOT RECOMMENDED - Cloudflare blocks)' if args.headless else '✅ (Best for Cloudflare)'}")
    print(f"   ⚡ Fast mode: {args.fast}")
    print(f"   ♻️  Force re-scrape: {args.force}")
    print(f"   💤 Sleep between books: {args.sleep}s")
    print("="*70)
    print()

    queue_file = Path("books_queue.txt")
    if not queue_file.exists():
        print("❌ File 'books_queue.txt' not found. Run get_category_links.py first.")
        return 1

    # Read queue
    urls = [line.strip() for line in queue_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    
    if not urls:
        print("❌ Queue file is empty.")
        return 1

    # Apply limit
    urls_to_process = urls[:args.limit]
    
    print(f"📋 Queue loaded: {len(urls)} total URLs")
    print(f"📋 Will process: {len(urls_to_process)} books")
    print()

    # Ensure data/json exists
    Path('data/json').mkdir(parents=True, exist_ok=True)

    # Process each book in a fresh subprocess
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, url in enumerate(urls_to_process, 1):
        print(f"\n{'='*70}")
        print(f"📚 BOOK {i}/{len(urls_to_process)}")
        print(f"{'='*70}")
        print(f"   URL: {url}")

        # Extract book ID for skip check
        book_id = extract_book_id(url)
        if book_id:
            print(f"   Book ID: {book_id}")

        # Skip if already scraped (unless --force)
        if not args.force and book_id and already_scraped(book_id):
            print(f"   ⏩ SKIPPED: Already scraped (use --force to re-scrape)")
            skip_count += 1
            continue

        # Build subprocess command
        cmd = [
            sys.executable,  # Use same Python interpreter
            "single_book_runner.py",
            url
        ]
        
        # Only add --chapters if specified (None means scrape all)
        if args.chapters is not None:
            cmd.extend(["--chapters", str(args.chapters)])
        
        if args.headless:
            cmd.append("--headless")
        if args.fast:
            cmd.append("--fast")

        print(f"\n   🚀 Launching subprocess: {' '.join(cmd)}")
        print(f"   ⏰ Started at: {time.strftime('%H:%M:%S')}")

        try:
            # Run subprocess - this creates a completely fresh Python process
            result = subprocess.run(
                cmd,
                check=True,  # Raise exception if exit code != 0
                capture_output=False,  # Show output in real-time
                text=True
            )
            
            print(f"\n   ✅ SUCCESS: Book scraped successfully")
            success_count += 1

        except subprocess.CalledProcessError as e:
            print(f"\n   ❌ ERROR: Subprocess exited with code {e.returncode}")
            error_count += 1
            
            # Log error
            with open("batch_errors.log", "a", encoding="utf-8") as log:
                log.write(f"\n{'='*70}\n")
                log.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log.write(f"URL: {url}\n")
                log.write(f"Exit Code: {e.returncode}\n")
                log.write(f"{'='*70}\n")

        except KeyboardInterrupt:
            print(f"\n\n⚠️  INTERRUPTED by user (Ctrl+C)")
            print(f"\n📊 Partial Results:")
            print(f"   ✅ Successful: {success_count}")
            print(f"   ⏩ Skipped: {skip_count}")
            print(f"   ❌ Errors: {error_count}")
            return 130  # Standard exit code for Ctrl+C

        except Exception as e:
            print(f"\n   ❌ UNEXPECTED ERROR: {e}")
            error_count += 1

        # Sleep between books (except after last one)
        if i < len(urls_to_process):
            print(f"\n   💤 Sleeping {args.sleep}s before next book...")
            time.sleep(args.sleep)

    # Final summary
    print(f"\n\n{'='*70}")
    print("🎉 BATCH RUN COMPLETE")
    print("="*70)
    print(f"📊 Final Results:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ⏩ Skipped: {skip_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📚 Total processed: {success_count + skip_count + error_count}/{len(urls_to_process)}")
    print("="*70)

    # Power Management - Handle shutdown/sleep after batch completion
    if args.shutdown or args.sleep_pc:
        # Prioritize shutdown if both are specified
        if args.shutdown:
            print(f"\n⚠️  Job finished! SHUTTING DOWN in 60s. Press Ctrl+C to cancel.")
            action = "shutdown"
            command = "shutdown /s /t 0"
        else:
            print(f"\n⚠️  Job finished! GOING TO SLEEP in 60s. Press Ctrl+C to cancel.")
            action = "sleep"
            command = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
        
        try:
            # Countdown with dots for visual feedback
            for remaining in range(60, 0, -1):
                print(f"\r   ⏳ {action.upper()} in {remaining}s...", end='', flush=True)
                time.sleep(1)
            
            print(f"\n\n🔌 Executing {action}...")
            os.system(command)
            
        except KeyboardInterrupt:
            print(f"\n\n✋ {action.upper()} CANCELLED by user.")
            return 0 if error_count == 0 else 1

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
