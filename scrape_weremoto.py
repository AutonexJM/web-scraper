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
    # Check common keywords for new jobs
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    return False

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        
        url = "https://www.weremoto.com/remote-jobs"
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Scroll para mag-load pa
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # --- FIX: Updated Selector for Plural "job-posts" ---
            # Kinukuha na natin lahat ng links na may "job-post" (singular or plural)
            all_links = page.locator('a[href*="/job-post"]').all()
            
            print(f"Log: Found {len(all_links)} potential links...", file=sys.stderr)
            
            count = 0
            for link in all_links:
                if count >= limit: break
                
                try:
                    href = link.get_attribute('href')
                    if not href: continue
                    
                    full_link = "https://www.weremoto.com" + href
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # --- FILTERING (List View) ---
                    # Check natin kung fresh ba base sa text sa listahan
                    card_text = link.inner_text()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # --- DEEP SCRAPE (Pasok sa loob) ---
                    # Pupuntahan natin ang link para makuha ang details sa screenshot mo
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        detail_page.wait_for_load_state("domcontentloaded")
                        
                        # 1. Job Title & Company
                        # Sa WeRemoto, minsan H1 ang Company, minsan H1 ang Title.
                        # Kukunin natin pareho para sure.
                        h1_text = detail_page.locator('h1').first.inner_text().strip()
                        
                        # Hanapin ang company name (usually katabi ng logo or sa ilalim ng H1)
                        # Fallback: Kukunin natin ang page title kung nalilito
                        page_title = detail_page.title() 
                        
                        # Logic: Kung ang H1 ay Company Name, ang Job Title ay nasa meta tags o URL
                        # Pero para simple, ipapasa natin sa AI ang raw data
                        
                        # 2. Description
                        # Hanapin ang main content div
                        description = "Check link"
                        try:
                            # Common selectors for job body
                            desc_locator = detail_page.locator('div.job-description, div.prose, article')
                            if desc_locator.count() > 0:
                                description = desc_locator.first.inner_text()
                            else:
                                # Fallback: Get all paragraphs
                                description = detail_page.locator('body').inner_text()[:2000] 
                        except: pass

                        # 3. Tags (Yung nasa screenshot mo: Full Time, Marketing, etc.)
                        tags = []
                        try:
                            # Badges usually have distinct classes
                            badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                            tags = [b.strip() for b in badges if b.strip()]
                        except: pass
                        
                        tags_string = ", ".join(tags)

                        # Salary Detection
                        salary = "Not Disclosed"
                        salary_type = "N/A"
                        if "$" in description:
                            salary = "See Description" # Let AI find it
                        
                        # Append Data
                        data.append({
                            "Date Posted": get_todays_date(),
                            "Job Title": h1_text, # AI will clean this up
                            "Company Name": "Check Description", # AI will extract from text
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
                        print(f"Log: Detail page error: {e}", file=sys.stderr)
                    finally:
                        detail_page.close()

                except: continue

        except Exception as e:
            print(f"Log: Main error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
