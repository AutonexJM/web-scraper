import json
import sys
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def is_date_fresh_inside_page(text):
    text = text.lower()
    if any(x in text for x in ["new", "nuevo", "just", "hours", "horas", "mins", "minutos"]): return True
    if any(x in text for x in ["1 day", "1 día", "1 dia", "ayer", "yesterday"]): return True
    
    # Check Current Month (Jan/Ene)
    now = datetime.now()
    months_map = { 1: ['jan', 'ene'], 2: ['feb'], 3: ['mar'], 4: ['apr', 'abr'], 5: ['may'], 6: ['jun'], 7: ['jul'], 8: ['aug', 'ago'], 9: ['sep', 'set'], 10: ['oct'], 11: ['nov'], 12: ['dec', 'dic'] }
    current_keys = months_map.get(now.month, [])
    
    for m in current_keys:
        if re.search(rf'{m}\s+\d{{1,2}}', text): return True
    return False

def hunt_for_salary(text):
    if not text: return "Not Disclosed", "N/A"
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
        
        # Increase default timeout to 60s
        context = browser.new_context()
        context.set_default_timeout(60000) 
        page = context.new_page()
        
        url = "https://www.weremoto.com/"
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            # FAST LOAD CHANGE: domcontentloaded instead of networkidle
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Wait a bit for JS elements (Manual safety wait)
            time.sleep(5)
            
            print(f"Log: Page Title: {page.title()}", file=sys.stderr)
            
            # Scroll
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            all_links = page.locator('a[href*="/job-posts/"]').all()
            print(f"Log: Found {len(all_links)} links. Processing...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Deep Scrape
                    detail_page = context.new_page()
                    try:
                        # FAST LOAD also for detail page
                        detail_page.goto(full_link, timeout=45000, wait_until="domcontentloaded")
                        
                        # Wait for body text to be populated
                        try: detail_page.wait_for_selector('body', timeout=5000)
                        except: pass

                        full_text = detail_page.locator('body').inner_text()[:3000]
                        
                        if not is_test:
                            if not is_date_fresh_inside_page(full_text):
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
                    except: pass
                    finally: detail_page.close()

                except: continue

        except Exception as e:
            print(f"Log: Critical Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
