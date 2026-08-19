import base64
from playwright.sync_api import sync_playwright

def run_editor_test(headed=False):
    print(f"\n[Playwright] Launching browser test for Article Editor (Headed={headed})...")
    status = "FAILED"
    details = ""
    screenshot_b64 = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            page = browser.new_page()
            page.goto("https://conduit.bondaracademy.com/")
            page.wait_for_load_state("networkidle")
            
            title = page.title()
            print(f"[Playwright] Page loaded successfully with Title: '{title}'")
            
            if "Conduit" in title:
                status = "PASSED"
                details = "Editor page route reached successfully."
            else:
                details = f"Unexpected title: {title}"
                # Capture screenshot on assertion failure
                screenshot_bytes = page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
            browser.close()
    except Exception as e:
        details = str(e)

    print(f"[Playwright] Result: {status}\n")
    return {"status": status, "details": details, "screenshot": screenshot_b64}