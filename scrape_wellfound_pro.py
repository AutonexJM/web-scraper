import json
import sys
import time
import re
import random
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- HELPER FUNCTIONS ---

def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def clean_text(text):
    if not text: return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def is_within_24_hours(date_text):
    """
    STRICT FILTER: Returns True only if job is < 24 hours old.
    """
    text = date_text.lower()
    if 'just now' in text or 'today' in text: return True
    # Matches "4h", "14h", "30m"
    if re.search(r'\d+\s*h', text) or re.search(r'\d+\s*m', text): return True
    return False

def parse_relative_date(date_text):
    """
    Convert relative time to WordPress Format: MM/DD/YYYY, 09:00 AM
    """
    try:
        today = datetime.now()
        date_text = date_text.lower()
        target_date = today 
        
        if 'yesterday' in date_text:
            target_date = today - timedelta(days=1)
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
        browser = p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 768}
        )
        page = context.new_page()

        # --- URL LOGIC (ALL JOBS vs SPECIFIC ROLE) ---
        if keyword.lower() == "all" or keyword == "":
            # Search ALL jobs in LATAM
            url = "https://wellfound.com/jobs?locations=Latin+America"
            print(f"Log: Searching ALL jobs in LATAM...", file=sys.stderr)
        else:
            # Search specific role
            url = f"https://wellfound.com/jobs?role={keyword}&locations=Latin+America"
            print(f"Log: Searching for '{keyword}' in LATAM...", file=sys.stderr)
        
        if is_test_mode:
            print("Log: TEST MODE ON (Ignorning 24h limit)", file=sys.stderr)

        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
        except: pass

        # Scroll
        for _ in range(3):
            page.mouse.wheel(0, 3000)
            random_sleep(1, 2)

        job_cards = page.locator('div[data-test="JobCard"]').all()
        if not job_cards: job_cards = page.locator('div[class^="styles_component__"]').all()

        print(f"Log: Processing {len(job_cards)} cards...", file=sys.stderr)

        count = 0
        for card in job_cards:
            if count >= limit: break

            try:
                # 1. Date Check
                date_posted_raw = "Unknown"
                meta_spans = card.locator('span').all_inner_texts()
                for txt in meta_spans:
                    if re.match(r'\d+[dwhmo]', txt) or 'just now' in txt.lower() or 'today' in txt.lower() or 'yesterday' in txt.lower():
                        date_posted_raw = txt
                        break
                
                # --- FILTER LOGIC ---
                # Kung HINDI Test Mode, i-apply ang Strict 24h Filter.
                # Kung Test Mode, lusot lang kahit luma na.
                if not is_test_mode:
                    if not is_within_24_hours(date_posted_raw): continue 

                # 2. Salary Check (Keep this strict para USD lang makuha mo)
                raw_text = card.inner_text()
                if "₹" in raw_text or "€" in raw_text or "£" in raw_text: continue 
                
                salary_text = "Hidden"
                salary_loc = card.locator('span:has-text("$")')
                if salary_loc.count() > 0: salary_text = salary_loc.first.inner_text()
                
                # Uncomment next line kung gusto mo USD SHOWN only (no hidden)
                # if "$" not in salary_text: continue

                # 3. Duplicate Check
                link = card.locator('a').first
                job_url = "https://wellfound.com" + link.get_attribute('href')
                if job_url in seen_urls: continue 
                seen_urls.add(job_url)

                # --- Scrape Details ---
                title = card.locator('h2').first.inner_text()
                company = card.locator('div[class*="companyName"]').first.inner_text()
                job_post_date = parse_relative_date(date_posted_raw)

                detail_page = context.new_page()
                detail_page.goto(job_url)
                try: detail_page.wait_for_selector('body', timeout=10000)
                except: detail_page.close(); continue
                random_sleep(1, 2)

                content_html = detail_page.content()
                soup = BeautifulSoup(content_html, 'html.parser')
                full_text = soup.get_text(separator="\n")

                # Website
                company_website = "Not Available"
                try:
                    profile_link = detail_page.locator(f'a[href^="/company/"]').first
                    if profile_link.count() > 0:
                        profile_url = "https://wellfound.com" + profile_link.get_attribute('href')
                        detail_page.goto(profile_url)
                        try:
                            website_el = detail_page.locator('a[data-test="CompanyUrl"]').first
                            if website_el.count() == 0: website_el = detail_page.locator('a:has-text("Website")').first
                            if website_el.count() > 0: company_website = website_el.get_attribute('href')
                            else: company_website = profile_url
                        except: company_website = profile_url
                except: pass

                # Fields
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
                
                tools_found = [t for t in tags if any(kt.lower() in t.lower() for kt in ["Python", "React", "Node", "AWS", "Docker", "SQL", "Java", "Go", "Javascript", "Typescript", "PHP", "Laravel"])]
                industries_found = [t for t in tags if t not in tools_found]
                if not tools_found: tools_found = tags[:3]

                hours = "Standard"
                if "part-time" in full_text.lower(): hours = "Part-time"
                
                app_type = "Wellfound Easy Apply"
                try:
                    if "External" in detail_page.locator('button[data-test="ApplyButton"]').inner_text():
                        app_type = "External Application"
                except: pass

                # Build Data
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
    # ARG 1: Keyword (Use "all" for everything)
    kw = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    # ARG 2: Limit
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    # ARG 3: Test Mode (If present, disable 24h filter)
    test_mode = False
    if len(sys.argv) > 3 and sys.argv[3] == "test":
        test_mode = True
        
    scrape_jobs_pro(kw, lim, test_mode)
