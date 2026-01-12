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
    
    # 1. Super Fresh (Hours/Mins)
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    
    # 2. LOOSENED FILTER: Payagan ang "1 day" o "Yesterday"
    if "1 day" in text or "1 día" in text or "ayer" in text or "yesterday" in text:
        return True
        
    return False

def hunt_for_salary(text):
    """
    Scans text for salary patterns and determines type (Hourly, Monthly, Yearly).
    Supports English and Spanish indicators.
    """
    if not text: return "Not Disclosed", "N/A"
    
    pattern = r'((?:USD\s?|\$)\s?\d[\d,.]*[kK]?(?:\s*-\s*(?:USD\s?|\$)\s?\d[\d,.]*[kK]?)?(?:\s*\/\s*(?:mo|hr|h|month|year|annum|mes|hora|año))?)'
    
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        salary_str = match.group(1).strip()
        lower_str = salary_str.lower()
        
        salary_type = "Monthly" # Default fallback
        
        if any(x in lower_str for x in ['/hr', '/h', 'hour', 'hora']):
            salary_type = "Hourly"
        elif any(x in lower_str for x in ['/mo', 'month', 'mes', 'mensual']):
            salary_type = "Monthly"
        elif any(x in lower_str for x in ['/yr', 'year', 'annum', 'año', 'anual']):
            salary_type = "Yearly"
        elif 'k' in lower_str:
            salary_type = "Yearly"
        elif re.search(r'\$\s?\d{1,2}(?:\.\d+)?\s*$', salary_str):
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
            
            # Scroll
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # Strict Link Filter
            all_links = page.locator('a[href*="/job-posts/id-"]').all()
            print(f"Log: Found {len(all_links)} job candidates...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    
                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Freshness Check (Updated Logic)
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # --- DEEP SCRAPE ---
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        full_page_text = detail_page.locator('body').inner_text()[:2000]
                        salary, salary_type = hunt_for_salary(full_page_text)

                        company_name = "N/A"
                        if detail_page.locator('h1').count() > 0:
                            company_name = detail_page.locator('h1').first.inner_text().strip()

                        # Job Title Logic
                        job_title = "See Description"
                        role_match = re.search(r'(?:Role|Rol|Puesto|Position)\s*[:\-\—]\s*(.+)', full_page_text, re.IGNORECASE)
                        if role_match:
                            job_title = role_match.group(1).strip()

                        description = "Check link"
                        desc_locator = detail_page.locator('div.job-description, article, div.prose')
                        if desc_locator.count() > 0:
                            description = desc_locator.first.inner_text()[:3000]
                        else:
                            description = full_page_text

                        tags_string = "N/A"
                        try:
                            badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                            tags_string = ", ".join([b.strip() for b in badges if b.strip()])
                        except: pass

                        data.append({
                            "Date Posted": get_todays_date(),
                            "Company Name": company_name,
                            "Job Title": job_title,
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
            print(f"Log: Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
