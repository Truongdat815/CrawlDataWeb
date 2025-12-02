from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import os
import time
from urllib.parse import urljoin


def render_with_playwright(url, storage_state_path=None, timeout=120000, screenshot_path=None, har_path=None, debug_dir='data/debug'):
    os.makedirs(debug_dir, exist_ok=True)
    html_out = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_args = {}
            if storage_state_path and os.path.exists(storage_state_path):
                context_args['storage_state'] = storage_state_path
            # HAR recording if requested
            if har_path:
                context_args['record_har_path'] = har_path

            context = browser.new_context(**context_args)
            page = context.new_page()
            try:
                page.goto(url, timeout=timeout, wait_until='networkidle')
            except PWTimeoutError:
                # continue even if networkidle times out
                pass
            except Exception:
                pass

            # small interactions to reveal TOC
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            selectors = [
                "button:has-text('Contents')",
                "a:has-text('Contents')",
                "#catalogBtn",
                ".chapter-list-toggle",
                ".j_catalog",
                "button:has-text('Table of Contents')",
                "a:has-text('Table of Contents')",
            ]
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        try:
                            el.scroll_into_view_if_needed()
                            el.click()
                            page.wait_for_timeout(1200)
                            # additional scroll
                            page.evaluate("window.scrollBy(0, 400)")
                            page.wait_for_timeout(800)
                        except Exception:
                            continue
                except Exception:
                    continue

            # Save HTML
            try:
                html_out = page.content()
                if screenshot_path:
                    try:
                        page.screenshot(path=screenshot_path, full_page=True)
                    except Exception:
                        pass
                # If HAR was recorded, context.closed will write it
            except Exception:
                html_out = None

            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    except Exception:
        return None

    return html_out
