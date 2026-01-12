import json
import sys
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def is_fresh_job(text):
    """Checks for 'hours', 'minutes', 'horas', 'minutos', 'new', 'nuevo'"""
    text = text.lower()
    if "new" in text or "nuevo" in text or "just" in text: return True
    # Matches "2h", "4 hours", "5 horas", "30 mins"
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    return False

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        # Launch Browser (Headless)
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        
        url = "https://www.weremoto.com/remote-jobs"
        print(f"Log: Visiting {url} using Playwright...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            
            # Wait for job cards to appear (Important!)
            # We wait for links that contain "/job-post/"
            page.wait_for_selector('a[href*="/job-post/"]', timeout=15000)
            
            # Scroll down to load more
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # Select all job links
            job_links = page.locator('a[href*="/job-post/"]').all()
            
            print(f"Log: Found {len(job_links)} potential cards. Extracting...", file=sys.stderr)
            
            count = 0
            for link in job_links:
                if count >= limit: break
                
                try:
                    # Get Text from the list item
                    card_text = link.inner_text()
                    
                    # --- FILTER ---
                    if not is_test:
                        if not is_fresh_job(card_text): 
                            continue

                    href = link.get_attribute('href')
                    full_link = "https://www.weremoto.com" + href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Extract details from Card Text (Lines)
                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                    
                    # Fallback values
                    title = "N/A"
                    company = "N/A"
                    tags = []
                    
                    # Heuristic parsing (Hula base sa pwesto ng text)
                    if len(lines) > 0: title = lines[0]
                    if len(lines) > 1: company = lines[1]
                    
                    # Collect tags (usually yung mga nasa baba na texts)
                    if len(lines) > 2: tags = lines[2:]
                    tags_string = ", ".join(tags)

                    # Salary Check
                    salary = "Not Disclosed"
                    salary_type = "N/A"
                    for t in tags:
                        if "$" in t:
                            salary = t
                            salary_type = "Contract" if "hour" in t.lower() else "Yearly/Monthly"

                    # Build Object
                    job_data = {
                        "Date Posted": get_todays_date(),
                        "Company Name": company,
                        "Job Title": title,
                        "Salary": salary,
                        "Salary Type": salary_type,
                        "Location": "Latin America (Remote)", # WeRemoto is mostly LATAM
                        "Job Description": "Check link for details", # List view lang to
                        "Required Skills": tags_string, 
                        "external_apply_link": full_link
                    }

                    data.append(job_data)
                    count += 1
                    
                except Exception as e:
                    # print(f"Log: Error on card: {e}", file=sys.stderr)
                    continue

        except Exception as e:
            print(f"Log: Page load error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test":
        test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
