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

def scrape_weremoto(limit=20, is_test=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        
        # FIX: Gamitin ang Homepage, mali ang /remote-jobs
        url = "https://www.weremoto.com/" 
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Print Title para ma-confirm kung nasa tamang page na
            print(f"Log: Page Title: {page.title()}", file=sys.stderr)
            
            # Scroll para mag-load pa
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
                    
                    # WeRemoto usually puts jobs under /job-post/ or /p/
                    if "job" not in href and "remote" not in href: 
                        continue
                    
                    # Iwasan ang non-job pages
                    if "category" in href or "blog" in href or "login" in href or "companies" in href:
                        continue

                    full_link = "https://www.weremoto.com" + href if href.startswith("/") else href
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Freshness Check
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

                        # Salary
                        salary = "Not Disclosed"
                        salary_type = "N/A"
                        if "$" in description or "$" in tags_string:
                            salary = "See Description"

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
                        
                    except Exception:
                        pass
                    finally:
                        detail_page.close()

                except Exception:
                    continue

        except Exception as e:
            print(f"Log: Critical Error: {e}", file=sys.stderr)
            
        browser.close()
    
    print(json.dumps(data))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test": test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
