"""Playwright smoke test for the Podcast Generator Streamlit dashboard."""
import time
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/podcast_ui"

import os
os.makedirs(SCREENSHOTS, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    # ── 1. Load ────────────────────────────────────────────────────────────
    page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
    time.sleep(4)
    page.screenshot(path=f"{SCREENSHOTS}/01_initial.png")
    print("✓ Dashboard loaded")

    # ── 2. Fill topic ──────────────────────────────────────────────────────
    topic_box = page.locator("input[aria-label='What should the podcast be about?']")
    topic_box.click()
    topic_box.fill("The history of the internet")
    time.sleep(1)
    page.screenshot(path=f"{SCREENSHOTS}/02_topic_entered.png")
    print("✓ Topic entered")

    # ── 3. Select short ───────────────────────────────────────────────────
    page.locator("label", has_text="short").click()
    time.sleep(0.5)
    page.screenshot(path=f"{SCREENSHOTS}/03_short_selected.png")
    print("✓ Duration: short")

    # ── 4. Submit ─────────────────────────────────────────────────────────
    page.locator("button", has_text="Generate Podcast").click()
    time.sleep(6)
    page.screenshot(path=f"{SCREENSHOTS}/04_after_submit.png")
    print("✓ Submitted — waiting for card")

    # ── 5. Wait for podcast card ───────────────────────────────────────────
    # Streamlit reruns after submit; look for any status text in the dashboard
    for attempt in range(15):
        content = page.content()
        if "The history of the internet" in content:
            page.screenshot(path=f"{SCREENSHOTS}/05_card_visible.png")
            print(f"✓ Podcast card appeared (attempt {attempt+1})")
            break
        time.sleep(2)
    else:
        page.screenshot(path=f"{SCREENSHOTS}/05_no_card.png")
        print("✗ Card never appeared — check screenshot 05_no_card.png")
        browser.close()
        raise SystemExit(1)

    # ── 6. Poll until status progresses ───────────────────────────────────
    print("  Polling for status change (up to 90s)…")
    for i in range(30):
        time.sleep(3)
        content = page.content()
        if "Ready" in content or "Failed" in content:
            page.screenshot(path=f"{SCREENSHOTS}/06_terminal.png")
            status = "DONE" if "Ready" in content else "FAILED"
            print(f"✓ Status reached terminal state: {status}")
            break
        if "Crawling" in content:
            print(f"  [{i*3}s] Crawling…")
            page.screenshot(path=f"{SCREENSHOTS}/06_{i:02d}_crawling.png")
        elif "Generating" in content:
            print(f"  [{i*3}s] Generating…")
            page.screenshot(path=f"{SCREENSHOTS}/06_{i:02d}_generating.png")
    else:
        page.screenshot(path=f"{SCREENSHOTS}/06_timeout.png")
        print("⚠ Did not reach DONE within 90s — check for slow pipeline")

    # ── 7. Check for Listen button if done ────────────────────────────────
    if "Ready" in page.content():
        listen = page.locator("a", has_text="Listen")
        if listen.count() > 0:
            page.screenshot(path=f"{SCREENSHOTS}/07_listen_visible.png")
            print("✓ Listen button is visible")
        else:
            print("⚠ Status is Ready but no Listen button found")

    page.screenshot(path=f"{SCREENSHOTS}/08_final.png")
    print(f"\nAll screenshots saved to {SCREENSHOTS}/")
    browser.close()
