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

def extract_salary(text):
    """
    Hahanapin ang salary pattern: $XXk - $XXk, $X/hr, etc.
    """
    if not text: return "Not Disclosed", "N/A"
    
    # Regex para sa dollar amount (e.g. $140,000, $6-$8, $50k)
    # Matches: $ + digits/k + optional range + optional /hr
    match = re.search(r'(\$[\d,.]+[kK]?(?:\s*-\s*\$[\d,.]+[kK]?)?(?:\s*/\s*\w+)?)', text)
    
    if match:
        salary_str = match.group(1)
        
        # Determine Type
        salary_type = "Yearly" # Default
        if "/hr" in salary_str or "/h" in salary_str: salary_type = "Hourly"
        elif "/mo" in salary_str or "month" in text.lower(): salary_type = "Monthly"
        elif "contract" in text.lower(): salary_type = "Contract"
        
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
            
            # Get Links
            all_links = page.locator('a[href]').all()
            print(f"Log: Found {len(all_links)} links. Filtering...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    if not href: continue
                    
                    # --- STRICT LINK FILTERING ---
                    # 1. Dapat may 'job' o 'remote'
                    if "job" not in href and "remote" not in href: continue
                    
                    # 2. BLACKLIST: Iwasan ang mga ito
                    if any(x in href for x in ["publish", "pricing", "login", "companies", "blog", "category", "tag"]):
                        continue

                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Freshness Check (List View)
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # --- DEEP SCRAPE ---
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        # Title
                        h1_text = "N/A"
                        if detail_page.locator('h1').count() > 0:
                            h1_text = detail_page.locator('h1').first.inner_text().strip()
                        
                        # Description
                        description = "Check link"
                        desc_locator = detail_page.locator('div.job-description, article, div.prose')
                        if desc_locator.count() > 0:
                            description = desc_locator.first.inner_text()[:3000]
                        else:
                            description = detail_page.locator('body').inner_text()[:2000]

                        # Tags
                        tags_string = "N/A"
                        badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                        if badges:
                            tags_string = ", ".join([b.strip() for b in badges if b.strip()])

                        # --- SALARY EXTRACTION (NEW LOGIC) ---
                        # 1. Check Header (Madalas nandito ang salary gaya sa screenshot mo)
                        header_text = ""
                        try:
                            # Kunin ang text sa paligid ng H1
                            header_text = detail_page.locator('header, div[class*="header"]').first.inner_text()
                        except: pass
                        
                        # Search Salary in Header first (Priority), then Description
                        salary, salary_type = extract_salary(header_text)
                        
                        if salary == "Not Disclosed":
                            # Try searching in description/tags if not in header
                            salary, salary_type = extract_salary(description + " " + tags_string)

                        data.append({
                            "Date Posted": get_todays_date(),
                            "Job Title": h1_text,
                            "Company Name": "See Description", 
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
