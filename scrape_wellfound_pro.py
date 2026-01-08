import json
import sys
import time
import re
import random
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- LISTAHAN NG MGA BANSA SA LATAM ---
LATAM_KEYWORDS = [
    "Latin America", "LATAM", "Remote - Latin America",
    "Argentina", "Bolivia", "Brazil", "Brasil", "Chile", "Colombia", 
    "Costa Rica", "Cuba", "Dominican Republic", "Ecuador", "El Salvador", 
    "Guatemala", "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", 
    "Peru", "Puerto Rico", "Uruguay", "Venezuela", "Buenos Aires", "Sao Paulo", 
    "Bogota", "Lima", "Santiago", "Mexico City"
]

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def clean_text(text):
    if not text: return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def is_latam_location(text):
    """Checks if the text contains any LATAM country or city"""
    if not text: return False
    text = text.lower()
    for key in LATAM_KEYWORDS:
        if key.lower() in text:
            return True
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
        # Browser Launch (Mas Stealthy)
        browser = p.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-blink-features=AutomationControlled',
                '--start-maximized'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # --- URL STRATEGY ---
        # Strategy: Search lang ng keyword, tapos sa Python natin ifi-filter kung LATAM.
        # Mas reliable to kasi minsan sablay ang URL filter ng Wellfound.
        if keyword.lower() == "all" or keyword == "":
            url = "https://wellfound.com/jobs" # General Jobs Page
            print(f"Log: Searching ALL jobs (Will filter LATAM manually)...", file=sys.stderr)
        else:
            url = f"https://wellfound.com/jobs?role={keyword}"
            print(f"Log: Searching for '{keyword}'...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            
            # --- DEBUGGING: CHECK KUNG BLOCKED ---
            page_title = page.title()
            print(f"Log: Page Title loaded: '{page_title}'", file=sys.stderr)
            
            if "Just a moment" in page_title or "Cloudflare" in page_title:
                print("Log: CRITICAL - Cloudflare Blocked us. Retrying with wait...", file=sys.stderr)
                random_sleep(10, 15) # Wait baka lumusot
            
            page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"Log: Navigation error: {e}", file=sys.stderr)

        # Scroll
        print("Log: Scrolling to find jobs...", file=sys.stderr)
        for _ in range(5): # Mas maraming scroll
            page.mouse.wheel(0, 4000)
            random_sleep(1, 3)

        # Find Cards
        job_cards = page.locator('div[data-test="JobCard"]').all()
        # Fallback Selectors
        if not job_cards: 
            print("Log: data-test selector failed, trying classes...", file=sys.stderr)
            job_cards = page.locator('div[class^="styles_component__"]').all()

        print(f"Log: Found {len(job_cards)} total cards (Before filtering)...", file=sys.stderr)

        count = 0
        for card in job_cards:
            if count >= limit: break

            try:
                # --- GET CARD TEXT ---
                full_card_text = card.inner_text()
                
                # 1. LATAM LOCATION CHECK (The "Country Scanner")
                # Hahanapin natin kung may "Argentina", "Brazil", "LATAM", etc. sa card.
                # Kung WALA, skip natin (unless 'all' at walang location filter).
                # Pero dahil gusto mo LATAM only:
                if not is_latam_location(full_card_text):
                    # print("Log: Skipped non-LATAM job", file=sys.stderr)
                    continue

                # 2. Date Check
                date_posted_raw = "Unknown"
                if 'just now' in full_card_text.lower(): date_posted_raw = "Just now"
                elif 'today' in full_card_text.lower(): date_posted_raw = "Today"
                else:
                    match = re.search(r'(\d+[dwhmo])', full_card_text)
                    if match: date_posted_raw = match.group(1)
                
                if not is_test_mode:
                    if not is_within_24_hours(date_posted_raw): continue 

                # 3. Salary Check (USD Only)
                if "₹" in full_card_text or "€" in full_card_text or "£" in full_card_text: continue 
                salary_text = "Hidden"
                if "$" in full_card_text:
                    # Simple extraction fallback
                    lines = full_card_text.split('\n')
                    for l in lines:
                        if "$" in l: salary_text = l; break
                
                # 4. Duplicate Check
                try:
                    link = card.locator('a').first
                    job_url = "https://wellfound.com" + link.get_attribute('href')
                except: continue

                if job_url in seen_urls: continue 
                seen_urls.add(job_url)

                # --- Scrape Details ---
                title = card.locator('h2').first.inner_text()
                company = card.locator('div[class*="companyName"]').first.inner_text()
                job_post_date = parse_relative_date(date_posted_raw)

                # Open Page
                detail_page = context.new_page()
                detail_page.goto(job_url)
                try: detail_page.wait_for_selector('body', timeout=10000)
                except: detail_page.close(); continue
                random_sleep(1, 2)

                content_html = detail_page.content()
                soup = BeautifulSoup(content_html, 'html.parser')
                full_text = soup.get_text(separator="\n")

                # Website Logic
                company_website = "Not Available"
                try:
                    profile_link = detail_page.locator(f'a[href^="/company/"]').first
                    if profile_link.count() > 0:
                        profile_url = "https://wellfound.com" + profile_link.get_attribute('href')
                        # Don't visit profile to save time/detection, just use profile URL as fallback
                        company_website = profile_url 
                except: pass

                # Extract Fields
                qualifications = "See Job Description"
                for marker in ["Requirements", "Qualifications", "What we look for", "Skills"]:
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
                
                tools_found = [t for t in tags if any(kt.lower() in t.lower() for kt in ["Python", "React", "Node", "AWS", "Docker", "SQL", "Java", "Go"])]
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
                    "location": "Latin America (Remote)", # Static text since we filtered already
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
    if len(sys.argv) > 3 and sys.argv[3] == "test":
        test_mode = True
        
    scrape_jobs_pro(kw, lim, test_mode)
