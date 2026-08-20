import os
import json
import re
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
SCREENSHOTS_DIR = os.path.join(ARTIFACTS_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Configuration
BASE_URL = "https://conduit.bondaracademy.com"
LOGIN_CREDENTIALS = {
    "email": "testuser@example.com",  # Update with valid test credentials if available
    "password": "Password123!"
}

# Routes to discover
ROUTES_TO_CRAWL = ["/login", "/register", "/editor", "/settings", "/"]

def sanitize_filename(route_path):
    clean = re.sub(r'[^a-zA-Z0-9]', '_', route_path).strip('_')
    return clean if clean else "root"

def crawl_application():
    screens = []
    transitions = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print(f"[Crawler] Starting authenticated crawl on {BASE_URL}...")

        # --- AUTHENTICATION STEP ---
        try:
            page.goto(f"{BASE_URL}/login", timeout=10000)
            page.wait_for_selector("input[type='email']", timeout=5000)
            page.fill("input[type='email']", LOGIN_CREDENTIALS["email"])
            page.fill("input[type='password']", LOGIN_CREDENTIALS["password"])
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)
            print("[Crawler] Authenticated session established.")
        except Exception as e:
            print(f"[Crawler] Warning: Auto-login failed/bypassed ({e}). Proceeding as guest.")

        # --- CRAWL ROUTES ---
        for route in ROUTES_TO_CRAWL:
            target_url = f"{BASE_URL}{route}" if route != "/" else BASE_URL
            print(f"[Crawler] Visiting route: {route}")
            
            try:
                page.goto(target_url, wait_until="networkidle", timeout=10000)
                file_slug = sanitize_filename(route)
                screenshot_filename = f"{file_slug}.png"
                screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
                
                # Capture visual artifact
                page.screenshot(path=screenshot_path)

                # Extract DOM interactive elements
                elements = []
                dom_elements = page.query_selector_all("button, a, input, select, textarea")
                for idx, elem in enumerate(dom_elements):
                    try:
                        tag = elem.evaluate("el => el.tagName.toLowerCase()")
                        text = elem.inner_text().strip() or elem.get_attribute("placeholder") or ""
                        elem_id = elem.get_attribute("id") or f"{tag}_{idx}"
                        selector = f"{tag}#{elem_id}" if elem.get_attribute("id") else f"{tag}:has-text('{text[:15]}')"
                        
                        elements.append({
                            "element_id": elem_id,
                            "selector": selector,
                            "tag": tag,
                            "text": text[:30],
                            "type": "interactive"
                        })
                    except Exception:
                        continue

                screens.append({
                    "route": route,
                    "title": page.title() or route,
                    "screenshot": f"artifacts/screenshots/{screenshot_filename}",
                    "elements": elements
                })

            except Exception as err:
                print(f"[Crawler] Error crawling {route}: {err}")

        browser.close()

    # Save artifacts
    artifacts_data = {
        "screens": screens,
        "transitions": transitions
    }
    
    output_path = os.path.join(ARTIFACTS_DIR, "crawler_artifacts.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifacts_data, f, indent=2)

    print(f"[Crawler] Successfully saved {len(screens)} screen artifacts to {output_path}")

if __name__ == "__main__":
    crawl_application()