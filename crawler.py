import os
import json
import re
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("BASE_URL", "https://conduit.bondaracademy.com")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
SCREENSHOTS_DIR = os.path.join(ARTIFACTS_DIR, "screenshots")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def slugify(route_path):
    """Converts route path into a filesystem-safe string for screenshot filenames."""
    text = re.sub(r'[^\w\-_]', '_', route_path)
    return text.strip('_') or 'root'

def crawl_application(base_url, max_pages=15):
    """
    Crawls live app routes, captures DOM elements, screenshots, 
    and interaction transitions, then saves structured JSON artifacts.
    """
    visited_routes = set()
    queue = ["/"]
    base_domain = urlparse(base_url).netloc
    
    crawled_data = {
        "base_url": base_url,
        "screens": [],
        "transitions": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        while queue and len(visited_routes) < max_pages:
            current_route = queue.pop(0)
            if current_route in visited_routes:
                continue

            visited_routes.add(current_route)
            target_url = urljoin(base_url, current_route)
            print(f"[Crawler] Exploring Route: {current_route} ({target_url})")

            try:
                page.goto(target_url, timeout=10000)
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"[Crawler Error] Failed to load {target_url}: {e}")
                continue

            # 1. Capture Screenshot Artifact
            route_slug = slugify(current_route)
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{route_slug}.png")
            page.screenshot(path=screenshot_path, full_page=True)

            # 2. Extract Structured Interactive DOM Elements
            dom_elements = page.evaluate("""() => {
                const items = [];
                const selector = 'button, a, input, select, textarea, form';
                document.querySelectorAll(selector).forEach((el, index) => {
                    items.push({
                        element_id: el.id || `${el.tagName.toLowerCase()}_${index}`,
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || null,
                        name: el.getAttribute('name') || null,
                        text: (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').substring(0, 60),
                        href: el.getAttribute('href') || null,
                        selector: el.id ? `#${el.id}` : (el.name ? `[name="${el.name}"]` : el.tagName.toLowerCase())
                    });
                });
                return items;
            }""")

            # 3. Discover Interactions and Queue Internal Transition Routes
            for elem in dom_elements:
                href = elem.get("href")
                if href and not href.startswith("mailto:") and not href.startswith("javascript:"):
                    parsed_href = urlparse(href)
                    
                    # Process relative internal links or same-domain links
                    if not parsed_href.netloc or parsed_href.netloc == base_domain:
                        target_route = parsed_href.path or "/"
                        
                        if target_route not in visited_routes and target_route not in queue:
                            queue.append(target_route)
                        
                        # Record Interaction Transition Relationship
                        crawled_data["transitions"].append({
                            "from_route": current_route,
                            "to_route": target_route,
                            "triggered_by": elem["selector"],
                            "trigger_text": elem["text"] or elem["tag"]
                        })

            # 4. Save Screen Artifact Record
            crawled_data["screens"].append({
                "route": current_route,
                "title": page.title(),
                "screenshot_file": f"screenshots/{route_slug}.png",
                "elements_count": len(dom_elements),
                "elements": dom_elements
            })

        browser.close()

    # Export structured artifacts JSON
    artifacts_json = os.path.join(ARTIFACTS_DIR, "crawler_artifacts.json")
    with open(artifacts_json, "w", encoding="utf-8") as f:
        json.dump(crawled_data, f, indent=2)

    print("\n================ CRAWL COMPLETE ================")
    print(f"Total Screens Scanned:     {len(crawled_data['screens'])}")
    print(f"Transitions Captured:      {len(crawled_data['transitions'])}")
    print(f"Artifact JSON Location:    {artifacts_json}")
    print("=================================================")
    return crawled_data

if __name__ == "__main__":
    crawl_application(BASE_URL)