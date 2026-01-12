import json
import sys
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def is_strictly_fresh(text):
    """
    STRICT 24-48 Hour Filter.
    Accepts: "Hours ago", "1 day ago", "Today", "Yesterday", and specific dates (Jan 12, Jan 11).
    Rejects: "2 days", "Dec", older dates.
    """
    text = text.lower()
    
    # 1. Relative Time Keywords (Hours/Mins)
    if any(x in text for x in ["new", "nuevo", "just", "hours", "horas", "mins", "minutos"]):
        return True
    
    # 2. "1 Day" / Yesterday Keywords
    # Note: We exclude "2 days", "3 days" explicitly just to be safe, though regex handles numbers.
    if any(x in text for x in ["1 day", "1 día", "1 dia", "ayer", "yesterday", "hoy", "today"]):
        return True
        
    # 3. Specific Date Check (Target: TODAY and YESTERDAY only)
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    # Months mapping
    months_en = {1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'aug', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec'}
    months_es = {1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic'}
    
    # Create strings like "jan 12", "ene 12", "jan 11", "ene 11"
    target_dates = []
    
    # Add Today
    target_dates.append(f"{months_en[now.month]} {now.day}")
    target_dates.append(f"{months_es[now.month]} {now.day}")
    
    # Add Yesterday
    target_dates.append(f"{months_en[yesterday.month]} {yesterday.day}")
    target_dates.append(f"{months_es[yesterday.month]} {yesterday.day}")
    
    # Check if any target date is in the text
    for date_str in target_dates:
        # Regex to match exact date pattern (e.g. "Jan 12") to avoid partial matches
        if re.search(rf'{date_str}\b', text):
            return True
            
    return False

def hunt_for_salary(text):
    if not text: return "Not Disclosed", "N/A"
    # Regex to capture salary patterns
    pattern = r'((?:USD\s?|\$)\s?\d[\d,.]*[kK]?(?:\s*-\s*(?:USD\s?|\$)\s?\d[\d,.]*[kK]?)?(?:\s*\/\s*(?:mo|hr|h|month|year|annum|mes|hora|año))?)'
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        salary_str = match.group(1).strip()
        lower = salary_str.lower()
        stype = "Monthly"
        if any(x in lower for x in ['/hr', '/h', 'hour']): stype = "Hourly"
        elif any(x in lower for x in ['/mo', 'month', 'mes']): stype = "Monthly"
        elif any(x in lower for x in ['k', 'year']): stype = "Yearly"
        elif re.search(r'\$\s?\d{1,2}(?:\.\d+)?\s*$', salary_str): stype = "Hourly"
        return salary_str, stype
    return "Not Disclosed", "N/A"

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        
        # --- TURBO MODE: BLOCK IMAGES ---
        context = browser.new_context()
        def block_heavy(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                route.abort()
            else:
                route.continue_()
        context.route("**/*", block_heavy)
        # --------------------------------
        
        page = context.new_page()
        
        url = "https://www.weremoto.com/" 
        print(f"Log: Visiting {url} (Turbo Strict)...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Get Links
            all_links = page.locator('a[href*="/job-posts/"]').all()
            print(f"Log: Found {len(all_links)} links. Filtering strict...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # List View Freshness Check (Initial Pass)
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        # If list view explicitly says "2 days", skip immediately to save time
                        if "2 days" in card_text.lower() or "2 dias" in card_text.lower() or "week" in card_text.lower():
                            continue

                    # Deep Scrape
                    detail_page = context.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000, wait_until="domcontentloaded")
                        
                        # Wait for minimal content
                        try: detail_page.wait_for_selector('h1', timeout=3000); 
                        except: pass

                        full_text = detail_page.locator('body').inner_text()[:3000]
                        
                        # --- STRICT FILTER INSIDE ---
                        if not is_test:
                            if not is_strictly_fresh(full_text):
                                detail_page.close()
                                continue

                        salary, stype = hunt_for_salary(full_text)
                        
                        h1 = "N/A"
                        if detail_page.locator('h1').count():
                            h1 = detail_page.locator('h1').first.inner_text().strip()

                        comp = "See Description"
                        try: comp = detail_page.locator('h1 ~ p, h1 ~ div, .company-name').first.inner_text().strip()
                        except: pass

                        title = h1
                        role_match = re.search(r'(?:Role|Rol|Puesto)\s*[:\-\—]\s*(.+)', full_text, re.IGNORECASE)
                        if role_match: title = role_match.group(1).strip()

                        desc = full_text[:2500]
                        if detail_page.locator('div.job-description').count():
                            desc = detail_page.locator('div.job-description').first.inner_text()[:3000]

                        tags_str = "N/A"
                        try:
                            badges = detail_page.locator('span[class*="badge"]').all_inner_texts()
                            tags_str = ", ".join([b.strip() for b in badges if b.strip()])
                        except: pass

                        data.append({
                            "Date Posted": get_todays_date(),
                            "Job Title": title,
                            "Company Name": comp,
                            "Salary": salary,
                            "Salary Type": stype,
                            "Location": "Latin America (Remote)",
                            "Job Description": desc,
                            "Required Skills": tags_str,
                            "external_apply_link": full_link,
                            "Source": "WeRemoto"
                        })
                        count += 1
                        print(f"Log: Scraped {count}: {title}", file=sys.stderr)
                    except: pass
                    finally: detail_page.close()

                except: continue

        except Exception as e:
            print(f"Log: Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
