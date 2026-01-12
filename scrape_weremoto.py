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
    # Keywords na nagpapakita na bago ang job
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    return False

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        
        # 1. VISITING HOMEPAGE
        url = "https://www.weremoto.com/remote-jobs"
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Print Page Title (Debug)
            print(f"Log: Page Title: {page.title()}", file=sys.stderr)
            
            # Scroll para mag-load pa ng jobs
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # 2. FINDING LINKS (Ang Process ng Pagpili)
            # Kukunin natin lahat ng <a> na may href attribute
            all_links = page.locator('a[href]').all()
            
            print(f"Log: Scanning {len(all_links)} links for jobs...", file=sys.stderr)
            
            count = 0
            for link_el in all_links:
                if count >= limit: break
                
                try:
                    href = link_el.get_attribute('href')
                    
                    # --- FILTER: Dito tayo pipili kung alin ang iki-click ---
                    # Dapat may 'job' sa URL (para sure na trabaho, hindi blog o login)
                    if "job" not in href: 
                        continue
                    
                    # Iwasan ang categories o tags
                    if "category" in href or "tag" in href:
                        continue

                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Check kung bago (24 hours) - based sa text sa labas
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # 3. CLICKING / VISITING (Deep Scrape)
                    # Ito yung part na "Click the job post"
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        # --- EXTRACT DETAILS (Nasa loob na tayo ng job post) ---
                        
                        # Job Title (Usually H1)
                        h1_text = detail_page.locator('h1').first.inner_text().strip()
                        
                        # Description
                        description = "Check link"
                        # Try finding the main text block
                        desc_locator = detail_page.locator('div.job-description, article, div.prose, section')
                        if desc_locator.count() > 0:
                            description = desc_locator.first.inner_text()[:3000] # Limit length
                        else:
                            description = detail_page.locator('body').inner_text()[:2000]

                        # Tags / Badges
                        tags_string = "N/A"
                        try:
                            badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                            tags_string = ", ".join([b.strip() for b in badges if b.strip()])
                        except: pass

                        # Salary Detection
                        salary = "Not Disclosed"
                        salary_type = "N/A"
                        if "$" in description or "$" in tags_string:
                            salary = "See Description/Tags" # AI will extract exact amount later
                        
                        # Save Data
                        data.append({
                            "Date Posted": get_todays_date(),
                            "Job Title": h1_text,
                            "Company Name": "See Description", # AI na bahala maghanap sa text
                            "Salary": salary,
                            "Salary Type": salary_type,
                            "Location": "Latin America (Remote)",
                            "Job Description": description,
                            "Required Skills": tags_string,
                            "external_apply_link": full_link,
                            "Source": "WeRemoto"
                        })
                        count += 1
                        
                    except Exception as e:
                        # Skip kung may error sa loob ng page
                        pass
                    finally:
                        detail_page.close()
