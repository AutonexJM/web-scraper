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
        
        url = "https://www.weremoto.com/"
        print(f"Log: Visiting {url}...", file=sys.stderr)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Scroll para lumabas ang jobs
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(1)
            
            # --- STRICT URL FILTER ---
            # Kukunin lang ang links na may "/job-posts/id-"
            # Ito ang pattern ng SPECIFIC JOB POST sa WeRemoto
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

                    # Freshness Check (List View)
                    card_text = link_el.inner_text().strip()
                    if not is_test:
                        if not is_fresh_job(card_text): continue

                    # --- DEEP SCRAPE (Pasok sa Job Page) ---
                    detail_page = browser.new_page()
                    try:
                        detail_page.goto(full_link, timeout=30000)
                        
                        # 1. COMPANY NAME (Ang H1 sa WeRemoto ay madalas Company Name)
                        company_name = "N/A"
                        if detail_page.locator('h1').count() > 0:
                            company_name = detail_page.locator('h1').first.inner_text().strip()

                        # 2. JOB TITLE (Hahanapin sa "Role:" o "Rol:")
                        job_title = "See Description"
                        page_text = detail_page.locator('body').inner_text()
                        
                        # Regex para hanapin ang "Role: XXXXX" o "Rol: XXXXX"
                        # Hinahanap nito ang text pagkatapos ng 📌 o "Role:" hanggang sa dulo ng linya
                        role_match = re.search(r'(?:Role|Rol|Puesto|Position)\s*[:\-\—]\s*(.+)', page_text, re.IGNORECASE)
                        if role_match:
                            job_title = role_match.group(1).strip()
                        else:
                            # Fallback: Kung walang "Role:", baka yung H1 ay Job Title at yung Company ay nasa URL/Logo
                            # Pero base sa screenshot mo, Company ang H1.
                            # So we keep "See Description" kung walang explicit Role line.
                            pass

                        # 3. DESCRIPTION & SALARY
                        description = "Check link"
                        desc_locator = detail_page.locator('div.job-description, article, div.prose')
                        if desc_locator.count() > 0:
                            description = desc_locator.first.inner_text()[:3000]
                        else:
                            description = page_text[:2000]

                        # Salary Hunt (Regex)
                        salary = "Not Disclosed"
                        salary_type = "N/A"
                        
                        # Specific regex for salary lines like "Salary: $140k"
                        salary_match = re.search(r'(?:Salary|Salario|Compensation)\s*[:\-\—]\s*(.+)', page_text, re.IGNORECASE)
                        
                        target_text_for_salary = salary_match.group(1) if salary_match else description
                        
                        # Parse amount
                        money_pattern = r'((?:USD\s?|\$)\s?\d[\d,.]*[kK]?(?:\s*-\s*(?:USD\s?|\$)\s?\d[\d,.]*[kK]?)?(?:\s*\/\s*(?:mo|hr|h|month|year|annum))?)'
                        money_found = re.search(money_pattern, target_text_for_salary)
                        
                        if money_found:
                            salary = money_found.group(1).strip()
                            # Determine type
                            lower_sal = salary.lower()
                            if any(x in lower_sal for x in ['/hr', '/h', 'hour']): salary_type = "Hourly"
                            elif any(x in lower_sal for x in ['/mo', 'month']): salary_type = "Monthly"
                            elif 'k' in lower_sal or 'year' in lower_sal: salary_type = "Yearly"

                        # Tags
                        tags_string = "N/A"
                        try:
                            badges = detail_page.locator('span[class*="badge"], div[class*="tag"]').all_inner_texts()
                            tags_string = ", ".join([b.strip() for b in badges if b.strip()])
                        except: pass

                        data.append({
                            "Date Posted": get_todays_date(),
                            "Company Name": company_name, # H1
                            "Job Title": job_title,       # Role: ...
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
