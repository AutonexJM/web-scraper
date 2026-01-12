import requests
from bs4 import BeautifulSoup
import json
import sys
import re
from datetime import datetime

def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

def is_fresh_job(text):
    """Checks for 'hours', 'minutes', 'horas', 'minutos', 'new', 'nuevo'"""
    text = text.lower()
    if "new" in text or "nuevo" in text or "just" in text: return True
    if re.search(r'\d+\s*(h|m|min|hour|hora)', text): return True
    return False

def scrape_weremoto(limit=20, is_test=False):
    base_url = "https://www.weremoto.com"
    url = "https://www.weremoto.com/remote-jobs" 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"Log: Fetching {url}...", file=sys.stderr)
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Hanapin ang mga job links
        job_links = soup.find_all('a', href=lambda href: href and "/job-post/" in href)
        
        print(f"Log: Found {len(job_links)} total job cards on page.", file=sys.stderr)
        
        data = []
        count = 0

        for link_tag in job_links:
            if count >= limit: break
            
            try:
                # Basic info from the list item
                # Note: WeRemoto HTML structure relies heavily on text inside the link
                card_text = link_tag.get_text(separator=" ", strip=True)
                
                # --- FILTERING ---
                # Kung HINDI Test Mode, i-check ang date
                if not is_test:
                    if not is_fresh_job(card_text):
                        # print(f"Log: Skipped old job: {card_text[:30]}...", file=sys.stderr)
                        continue

                job_url = base_url + link_tag['href']
                
                # Check duplicates within this run
                if any(d['external_apply_link'] == job_url for d in data): continue

                # --- DEEP SCRAPE ---
                job_resp = requests.get(job_url, headers=headers)
                job_soup = BeautifulSoup(job_resp.text, 'html.parser')

                title = job_soup.find('h1').text.strip() if job_soup.find('h1') else "N/A"
                
                company_name = "N/A"
                # Try different selectors for company
                company_elem = job_soup.find('p', class_='company_name') or job_soup.find('a', class_='company_link')
                if company_elem: company_name = company_elem.text.strip()

                desc_elem = job_soup.find('div', id='job-description') or job_soup.find('div', class_='description')
                full_description = desc_elem.get_text(separator="\n").strip() if desc_elem else "Check link"

                tags = [badge.text.strip() for badge in job_soup.find_all('span', class_='badge')]
                tags_string = ", ".join(tags)

                salary = "Not Disclosed"
                salary_type = "N/A"
                for t in tags:
                    if "$" in t:
                        salary = t
                        salary_type = "Contract" if "hour" in t or "hora" in t else "Yearly/Monthly"

                job_data = {
                    "Date Posted": get_todays_date(),
                    "Company Name": company_name,
                    "Job Title": title,
                    "Salary": salary,
                    "Salary Type": salary_type,
                    "Location": "Latin America (Remote)",
                    "Job Description": full_description,
                    "Required Skills": tags_string,
                    "external_apply_link": job_url
                }

                data.append(job_data)
                count += 1
                
            except Exception as e:
                print(f"Log: Error parsing card: {e}", file=sys.stderr)
                continue

        print(json.dumps(data))

    except Exception as e:
        print(json.dumps([{"error": str(e)}]))

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    
    # Check for "test" argument
    test_mode = False
    if len(sys.argv) > 2 and sys.argv[2] == "test":
        test_mode = True
        
    scrape_weremoto(limit_arg, test_mode)
