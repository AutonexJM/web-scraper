import json
import sys
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def parse_date_string(date_text):
    """
    Kukuha ng date sa text (e.g. 'Jan 12', 'Ene 10') at gagawing object.
    Returns: datetime object or None
    """
    try:
        # Dictionary para sa English at Spanish months
        months = {
            'jan': 1, 'ene': 1, 'january': 1, 'enero': 1,
            'feb': 2, 'february': 2, 'febrero': 2,
            'mar': 3, 'march': 3, 'marzo': 3,
            'apr': 4, 'abr': 4, 'april': 4, 'abril': 4,
            'may': 5, 'mayo': 5,
            'jun': 6, 'june': 6, 'junio': 6,
            'jul': 7, 'july': 7, 'julio': 7,
            'aug': 8, 'ago': 8, 'august': 8, 'agosto': 8,
            'sep': 9, 'september': 9, 'septiembre': 9, 'set': 9,
            'oct': 10, 'october': 10, 'octubre': 10,
            'nov': 11, 'november': 11, 'noviembre': 11,
            'dec': 12, 'dic': 12, 'december': 12, 'diciembre': 12
        }
        
        # Regex para hulihin ang "Mon DD" (e.g., Jan 12, Ene 10)
        match = re.search(r'([a-zA-Z]{3,})\s+(\d{1,2})', date_text, re.IGNORECASE)
        
        if match:
            month_str = match.group(1).lower()[:3] # First 3 chars
            day = int(match.group(2))
            
            if month_str in months:
                month = months[month_str]
                current_year = datetime.now().year
                
                # Handle year rollover (e.g., Dec 30 post while running in Jan)
                # Kung ang month ng job ay Dec at Jan ngayon, ibig sabihin last year yun
                if month == 12 and datetime.now().month == 1:
                    year = current_year - 1
                else:
                    year = current_year
                    
                return datetime(year, month, day)
    except:
        pass
    return None

def is_recent_job(text, days_limit=3):
    """
    Returns True kung ang job ay posted within 'days_limit' (default 3 days).
    """
    text = text.lower()
    
    # 1. Check Keywords (Instant Pass)
    if "new" in text or "nuevo" in text or "just" in text or "hours" in text or "horas" in text or "mins" in text:
        return True
    
    if "today" in text or "hoy" in text: return True
    if "yesterday" in text or "ayer" in text: return True
    if "1 day" in text or "1 día" in text: return True
    
    # 2. Check Specific Dates (Jan 12, Ene 10)
    job_date = parse_date_string(text)
    if job_date:
        delta = datetime.now() - job_date
        # Payagan kung within X days (e.g. 3 days)
        if delta.days <= days_limit:
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
            
            # Scroll
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

                    # --- FRESHNESS CHECK (THE FIX) ---
                    card_text = link_el.inner_text().strip()
                    
                    if not is_test:
                        # Check date with 3-day window
                        if not is_recent_job(card_text, days_limit=3): 
                            continue

                    # Deep Scrape
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        full_text = detail_page.locator('body').inner_text()[:3000]
                        salary, stype = hunt_for_salary(full_text)

                        h1 = detail_page.locator('h1').first.inner_text().strip() if detail_page.locator('h1').count() else "N/A"
                        
                        comp = "See Description"
                        try:
                            # H1 is usually company in WeRemoto detail
                            comp = h1 
                        except: pass

                        # Role usually prefixed
                        title = "See Description"
                        role_match = re.search(r'(?:Role|Rol|Puesto)\s*[:\-\—]\s*(.+)', full_text, re.IGNORECASE)
                        if role_match: title = role_match.group(1).strip()
                        else: title = h1 # Fallback

                        # Description
                        desc = "Check link"
                        if detail_page.locator('div.job-description').count():
                            desc = detail_page.locator('div.job-description').first.inner_text()[:3000]
                        else:
                            desc = full_text[:2000]

                        # Tags
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
