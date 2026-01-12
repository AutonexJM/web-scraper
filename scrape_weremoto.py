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
    
    # 1. Relative Time (Hours/Mins/New)
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    if "day" in text or "días" in text or "dia" in text or "ayer" in text or "yesterday" in text: return True
    
    # 2. ABSOLUTE DATE FIX (Para sa "Jan 12")
    # Kukunin natin ang current day at month
    now = datetime.now()
    day = str(now.day)       # e.g., "12"
    prev_day = str(now.day - 1) # e.g., "11" (Kahapon)
    
    # Listahan ng buwan (English & Spanish short codes)
    # Add more if needed: 'feb', 'mar', 'abr', 'apr', etc.
    months = ['jan', 'ene', 'feb', 'mar', 'apr', 'abr', 'may', 'jun', 'jul', 'aug', 'ago', 'sep', 'oct', 'nov', 'dec', 'dic']
    
    # Kung may nakasulat na month sa text
    if any(m in text for m in months):
        # At kung nandun din ang araw ngayon (12) o kahapon (11)
        if day in text or prev_day in text:
            return True
            
    return False

def hunt_for_salary(text):
    if not text: return "Not Disclosed", "N/A"
    pattern = r'((?:USD\s?|\$)\s?\d[\d,.]*[kK]?(?:\s*-\s*(?:USD\s?|\$)\s?\d[\d,.]*[kK]?)?(?:\s*\/\s*(?:mo|hr|h|month|year|annum|mes|hora|año))?)'
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        salary_str = match.group(1).strip()
        lower_str = salary_str.lower()
        salary_type = "Monthly" # Default
        
        if any(x in lower_str for x in ['/hr', '/h', 'hour', 'hora']): salary_type = "Hourly"
        elif any(x in lower_str for x in ['/mo', 'month', 'mes', 'mensual']): salary_type = "Monthly"
        elif any(x in lower_str for x in ['/yr', 'year', 'annum', 'año', 'anual', 'k']): salary_type = "Yearly"
        elif re.search(r'\$\s?\d{1,2}(?:\.\d+)?\s*$', salary_str): salary_type = "Hourly"
        
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
            
            # Print para sure tayo sa nakikita ng bot
            print(f"Log: Page Title: {page.title()}", file=sys.stderr)
            
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # --- URL SELECTOR FIX ---
            # Hahanapin natin ang links na may "/job-posts/"
            # Ang sample mo ay: https://weremoto.com/job-posts/id-....
            all_links = page.locator('a[href*="/job-posts/"]').all()
            
            print(f"Log: Found {len(all_links)} links matching '/job-posts/'. Filtering...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    
                    # Siguraduhin na job post ito
                    if "job-posts" not in href: continue 

                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # --- FRESHNESS CHECK (Dito nagkatalo kanina) ---
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): 
                            # Optional Debug: Makita kung ano ang nire-reject
                            # print(f"Skipped old job: {card_text[:20]}...", file=sys.stderr)
                            continue

                    # --- DEEP SCRAPE ---
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        full_page_text = detail_page.locator('body').inner_text()[:2500]
                        salary, salary_type = hunt_for_salary(full_page_text)

                        h1_text = "N/A"
                        if detail_page.locator('h1').count() > 0:
                            h1_text = detail_page.locator('h1').first.inner_text().strip()
                        
                        # Company Name Logic
                        company_name = "See Description"
                        # Try finding elements near H1 (Subtitle)
                        try:
                            # Usually h2 or p below h1
                            subtitle = detail_page.locator('h1 + p, h1 + h2, .company-name').first
                            if subtitle.count() > 0:
                                company_name = subtitle.inner_text().strip()
                        except: pass

                        # Job Title Logic
                        job_title = h1_text # Default to H1 if no "Role:" found
                        role_match = re.search(r'(?:Role|Rol|Puesto|Position)\s*[:\-\—]\s*(.+)', full_page_text, re.IGNORECASE)
                        if role_match:
                            job_title = role_match.group(1).strip()

                        # Description
                        description = full_page_text
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
                            "Job Title": job_title,
                            "Company Name": company_name,
                            "Salary": salary,
                            "Salary Type": salary_type,
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
