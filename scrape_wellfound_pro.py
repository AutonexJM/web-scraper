import json
import sys
import time
import re
import random
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync # <--- NEW IMPORT
from bs4 import BeautifulSoup

# --- CONSTANTS ---
LATAM_KEYWORDS = [
    "Latin America", "LATAM", "Remote - Latin America",
    "Argentina", "Bolivia", "Brazil", "Brasil", "Chile", "Colombia", 
    "Costa Rica", "Cuba", "Dominican Republic", "Ecuador", "El Salvador", 
    "Guatemala", "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", 
    "Peru", "Puerto Rico", "Uruguay", "Venezuela"
]

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def clean_text(text):
    if not text: return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def is_latam_location(text):
    if not text: return False
    text = text.lower()
    for key in LATAM_KEYWORDS:
        if key.lower() in text: return True
    return False

def is_within_24_hours(date_text):
    text = date_text.lower()
    if 'just now' in text or 'today' in text: return True
    if re.search(r'\d+\s*h', text) or re.search(r'\d+\s*m', text): return True
    return False

def parse_relative_date(date_text):
    try:
        today = datetime.now()
        date_text = date_text.lower()
        target_date = today 
        if 'yesterday' in date_text: target_date = today - timedelta(days=1)
        elif 'mo' in date_text:
            match = re.search(r'\d+', date_text)
            num = int(match.group()) if match else 1
            target_date = today - timedelta(days=num*30)
        elif 'w' in date_text:
            match = re.search(r'\d+', date_text)
            num = int(match.group()) if match else 1
            target_date = today - timedelta(weeks=num)
        elif 'd' in date_text:
            match = re.search(r'\d+', date_text)
            num = int(match.group()) if match else 1
            target_date = today - timedelta(days=num)
        return target_date.strftime('%m/%d/%Y, 09:00 AM')
    except:
        return datetime.now().strftime('%m/%d/%Y, 09:00 AM')

# --- MAIN SCRAPER ---

def scrape_jobs_pro(keyword="all", limit=5, is_test_mode=False):
    data = []
    seen_urls = set()
    
    with sync_playwright() as p:
        # Browser Launch (Stealth Mode Enabled)
        browser = p.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-blink-features=AutomationControlled'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        
        page = context.new_page()
        # ACTIVATE STEALTH
        stealth_sync(page)

        # URL
        if keyword.lower() == "all" or keyword == "":
            url = "https://wellfound.com/jobs"
            print(f"Log: Searching ALL jobs...", file=sys.stderr)
        else:
            url = f"https://wellfound.com/jobs?role={keyword}"
            print(f"Log: Searching for '{keyword}'...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            random_sleep(3, 5) # Initial wait
            
            # Check Title
            page_title = page.title()
            print(f"Log: Page Title: '{page_title}'", file=sys.stderr)

            # --- DEBUG: Kung nasa homepage tayo, try natin mag-search manually ---
            if page_title.strip() == "wellfound.com" or "Log In" in page.content():
                 print("Log: Redirected to Home/Login. Attempting to click Jobs link...", file=sys.stderr)
                 try:
                     # Try clicking "Jobs" or "Find a Job" if available
                     page.get_by_text("Jobs", exact=True).first.click()
                     page.wait_for_load_state("networkidle")
                     random_sleep(3, 5)
                 except: pass

        except Exception as e:
            print(f"Log: Nav error: {e}", file=sys.stderr)

        # Scroll
        for _ in range(5):
            page.mouse.wheel(0, 4000)
            random_sleep(1, 3)

        # Find Cards
        job_cards = page.locator('div[data-test="JobCard"]').all()
        if not job_cards: 
            job_cards = page.locator('div[class^="styles_component__"]').all()

        print(f"Log: Found {len(job_cards)} cards.", file=sys.stderr)

        # --- DEBUG: KUNG 0 CARDS, PRINT HTML SNIPPET ---
        if len(job_cards) == 0:
            content_sample = page.content()[:1000] # First 1000 chars
            clean_sample = clean_text(content_sample)
            print(f"Log: DEBUG PAGE CONTENT: {clean_sample}", file=sys.stderr)

        count = 0
        for card in job_cards:
            if count >= limit: break

            try:
                full_card_text = card.inner_text()
                
                # Filter LATAM
                if not is_latam_location(full_card_text): continue

                # Filter Date
                date_posted_raw = "Unknown"
                if 'just now' in full_card_text.lower(): date_posted_raw = "Just now"
                elif 'today' in full_card_text.lower(): date_posted_raw = "Today"
                else:
                    match = re.search(r'(\d+[dwhmo])', full_card_text)
                    if match: date_posted_raw = match.group(1)
                
                if not is_test_mode:
                    if not is_within_24_hours(date_posted_raw): continue 

                # Filter Salary
                if "₹" in full_card_text or "€" in full_card_text or "£" in full_card_text: continue 
                salary_text = "Hidden"
                if "$" in full_card_text:
                    lines = full_card_text.split('\n')
                    for l in lines:
                        if "$" in l: salary_text = l; break
                
                # Duplicate Check
                try:
                    link = card.locator('a').first
                    job_url = "https://wellfound.com" + link.get_attribute('href')
                except: continue
                if job_url in seen_urls: continue 
                seen_urls.add(job_url)

                # Scrape
                title = card.locator('h2').first.inner_text()
                company = card.locator('div[class*="companyName"]').first.inner_text()
                job_post_date = parse_relative_date(date_posted_raw)

                detail_page = context.new_page()
                stealth_sync(detail_page) # Stealth on detail page too
                detail_page.goto(job_url)
                
                try: detail_page.wait_for_selector('body', timeout=10000)
                except: detail_page.close(); continue
                random_sleep(1, 2)

                content_html = detail_page.content()
                soup = BeautifulSoup(content_html, 'html.parser')
                full_text = soup.get_text(separator="\n")

                company_website = "Not Available"
                try:
                    profile_link = detail_page.locator(f'a[href^="/company/"]').first
                    if profile_link.count() > 0:
                        company_website = "https://wellfound.com" + profile_link.get_attribute('href')
                except: pass

                qualifications = "See Job Description"
                for marker in ["Requirements", "Qualifications", "Skills"]:
                    if marker in full_text:
                        try: qualifications = full_text.split(marker)[1].strip()[:1500]; break
                        except: pass

                company_desc = "See Description"
                if f"About {company}" in full_text:
                    try: company_desc = full_text.split(f"About {company}")[1].split("\n\n")[0][:800]
                    except: pass

                tags = []
                try:
                    for t in detail_page.locator('div[class*="Tag"]').all(): tags.append(t.inner_text())
                except: pass
                
                tools_found = [t for t in tags if any(kt.lower() in t.lower() for kt in ["Python", "React", "Node", "AWS", "Docker", "SQL"])]
                industries_found = [t for t in tags if t not in tools_found]
                if not tools_found: tools_found = tags[:3]

                hours = "Standard"
                if "part-time" in full_text.lower(): hours = "Part-time"
                
                app_type = "Wellfound Easy Apply"
                try:
                    if "External" in detail_page.locator('button[data-test="ApplyButton"]').inner_text():
                        app_type = "External Application"
                except: pass

                job_data = {
                    "job_title": title,
                    "company_name": company,
                    "company_website": company_website,
                    "job_post_date": job_post_date,
                    "salary_offer": salary_text,
                    "location": "Latin America (Remote)",
                    "company_description": clean_text(company_desc),
                    "job_description_snippet": clean_text(full_text[:1000]), 
                    "qualifications": clean_text(qualifications),
                    "required_tools": ", ".join(tools_found),
                    "industries": ", ".join(industries_found),
                    "application_type": app_type,
                    "hours_per_week": hours,
                    "external_apply_link": job_url
                }

                data.append(job_data)
                count += 1
                detail_page.close()

            except Exception as e:
                try: detail_page.close()
                except: pass
                continue

        browser.close()

    print(json.dumps(data))

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "all"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    test_mode = False
    if len(sys.argv) > 3 and sys.argv[3] == "test": test_mode = True
    scrape_jobs_pro(kw, lim, test_mode)
