import json
import sys
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def is_fresh_job(text):
    text = text.lower()
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    return False

def hunt_for_salary(text):
    """
    Scans text for salary patterns and determines type (Hourly, Monthly, Yearly).
    Supports English and Spanish indicators.
    """
    if not text: return "Not Disclosed", "N/A"
    
    # 1. HANAPIN ANG PERA
    # Matches: $100, $100k, $5-$10, USD 2000
    # Capture group includes the unit if present (e.g., /hr, /mes)
    pattern = r'((?:USD\s?|\$)\s?\d[\d,.]*[kK]?(?:\s*-\s*(?:USD\s?|\$)\s?\d[\d,.]*[kK]?)?(?:\s*\/\s*(?:mo|hr|h|month|year|annum|mes|hora|año))?)'
    
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        salary_str = match.group(1).strip()
        lower_str = salary_str.lower()
        
        # 2. DETERMINE TYPE (English & Spanish support)
        salary_type = "Monthly" # Default fallback for WeRemoto
        
        # Hourly Check
        if any(x in lower_str for x in ['/hr', '/h', 'hour', 'hora']):
            salary_type = "Hourly"
        
        # Monthly Check
        elif any(x in lower_str for x in ['/mo', 'month', 'mes', 'mensual']):
            salary_type = "Monthly"
            
        # Yearly Check
        elif any(x in lower_str for x in ['/yr', 'year', 'annum', 'año', 'anual']):
            salary_type = "Yearly"
            
        # Smart Guessing based on value if unit is missing
        elif 'k' in lower_str: # e.g. $50k
            salary_type = "Yearly"
        elif re.search(r'\$\s?\d{1,2}(?:\.\d+)?\s*$', salary_str): # e.g. $10 or $10.50 (walang unit)
            salary_type = "Hourly"
        
        return salary_str, salary_type
        
    return "Not Disclosed", "N/A"

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        
        url = "https://www.weremoto.com/" 
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            print(f"Log: Page Title: {page.title()}", file=sys.stderr)
            
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            all_links = page.locator('a[href]').all()
            print(f"Log: Found {len(all_links)} links. Filtering...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    
                    if "job" not in href and "remote" not in href: continue
                    if any(x in href for x in ["publish", "pricing", "login", "companies", "blog", "category", "tag"]): continue

                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # --- DEEP SCRAPE ---
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        # 1. SCAN HEADER FOR SALARY
                        # Kukunin ang unang 2000 characters ng page
                        full_page_text = detail_page.locator('body').inner_text()[:2000]
                        
                        # Hunt for Salary & Type
                        salary, salary_type = hunt_for_salary(full_page_text)

                        # 2. Get Other Details
                        h1_text = "N/A"
                        if detail_page.locator('h1').count() > 0:
                            h1_text = detail_page.locator('h1').first.inner_text().strip()
                        
                        # Company Name Heuristic
                        company_name = "See Description"
                        try:
                            # Try finding something that looks like a company name near title
                            candidates = detail_page.locator('h1 ~ p, h1 ~ div, .company-name').all_inner_texts()
                            if candidates: company_name = candidates[0].strip()
                        except: pass

                        description = full_page_text # Fallback if specific div fails
                        desc_locator = detail_page.locator('div.job-description, article, div.prose')
                        if desc_locator.count() > 0:
                            description = desc_locator.first.inner_text()[:3000]

                        # Tags
                        tags_string = "N/A"
                        try:
                            badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                            tags_string = ", ".join([b.strip() for b in badges if b.strip()])
                        except: pass

                        data.append({
                            "Date Posted": get_todays_date(),
                            "Job Title": h1_text,
                            "Company Name": company_name,
                            "Salary": salary,
                            "Salary Type": salary_type, # <-- FIXED TYPE
                            "Location": "Latin America (Remote)",
                            "Job Description": description,
                            "Required Skills": tags_string,
                            "external_apply_link": full_link,
                            "Source": "WeRemoto"
                        })
                        count += 1
                        
                    except Exception: pass
                    finally: detail_page.close()

                except Exception: continue

        except Exception as e:
            print(f"Log: Critical Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
