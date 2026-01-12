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
    
    # 1. Super Fresh (Hours/Mins/New)
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    if "day" in text or "días" in text or "dia" in text or "ayer" in text or "yesterday" in text: return True
    
    # 2. CURRENT MONTH STRATEGY (Paluwagin natin)
    # Kunin ang current month (e.g. "jan", "ene")
    # Kung nakita natin 'to sa card, kunin na natin.
    now = datetime.now()
    
    # English & Spanish Month names for the CURRENT month
    current_month_en = now.strftime("%b").lower() # e.g. "jan"
    
    # Manual map for Spanish current month
    spanish_months = {
        'jan': 'ene', 'feb': 'feb', 'mar': 'mar', 'apr': 'abr', 'may': 'may', 'jun': 'jun',
        'jul': 'jul', 'aug': 'ago', 'sep': 'sep', 'oct': 'oct', 'nov': 'nov', 'dec': 'dic'
    }
    current_month_es = spanish_months.get(current_month_en, "xxx")
    
    # Check if current month name exists in text
    if current_month_en in text or current_month_es in text:
        return True
        
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
            
            all_links = page.locator('a[href*="/job-posts/"]').all()
            print(f"Log: Found {len(all_links)} links. Filtering...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # --- FRESHNESS CHECK ---
                    card_text = link_el.inner_text().strip()
                    
                    if not is_test:
                        if not is_fresh_job(card_text):
                            # LOG NATIN KUNG BAKIT NA-SKIP (Para ma-debug mo)
                            # print(f"Log: Skipped (Old): {card_text[:30]}...", file=sys.stderr)
                            continue

                    # Deep Scrape
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        full_text = detail_page.locator('body').inner_text()[:3000]
                        salary, stype = hunt_for_salary(full_text)

                        h1 = detail_page.locator('h1').first.inner_text().strip() if detail_page.locator('h1').count() else "N/A"
                        
                        comp = "See Description"
                        try: comp = detail_page.locator('h1 ~ p, h1 ~ div, .company-name').first.inner_text().strip()
                        except: pass

                        title = h1 # Default
                        role_match = re.search(r'(?:Role|Rol|Puesto)\s*[:\-\—]\s*(.+)', full_text, re.IGNORECASE)
                        if role_match: title = role_match.group(1).strip()

                        desc = full_text[:2000]
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
            print(f"Log: Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
