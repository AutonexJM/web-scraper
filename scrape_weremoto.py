import requests
from bs4 import BeautifulSoup
import json
import sys
from datetime import datetime

# --- HELPER: Get Date ---
def get_todays_date():
    return datetime.now().strftime("%m-%d-%Y")

# --- MAIN SCRAPER ---
def scrape_weremoto(limit=20):
    base_url = "https://www.weremoto.com"
    # Target: Programming & Design & Marketing (Mixed) or just remove category to get all
    url = "https://www.weremoto.com/remote-jobs" 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # WeRemoto job cards usually have a specific link structure
        # Hinahanap natin ang mga link na papunta sa /job-post/
        job_links = soup.find_all('a', href=lambda href: href and "/job-post/" in href)
        
        data = []
        count = 0

        for link_tag in job_links:
            if count >= limit: break
            
            try:
                # 1. Kunin ang Basic Info sa Listahan
                job_url = base_url + link_tag['href']
                
                # Check duplicates (Simple logic)
                is_duplicate = False
                for d in data:
                    if d['external_apply_link'] == job_url: is_duplicate = True
                if is_duplicate: continue

                # 2. DEEP DIVE: Buksan ang Job Page para makuha ang Description
                # (Mabilis lang to sa requests)
                job_resp = requests.get(job_url, headers=headers)
                job_soup = BeautifulSoup(job_resp.text, 'html.parser')

                # --- EXTRACTION ---
                
                # Job Title (H1)
                title = job_soup.find('h1').text.strip() if job_soup.find('h1') else "N/A"
                
                # Company Name (Usually in a p tag or badge)
                # WeRemoto structure varies, trying common selectors
                company_name = "N/A"
                company_tag = job_soup.find('p', class_='company_name') 
                if not company_tag: company_tag = job_soup.find('div', class_='company')
                if company_tag: company_name = company_tag.text.strip()

                # Description (Ang pinaka-laman)
                description_div = job_soup.find('div', id='job-description') 
                if not description_div: description_div = job_soup.find('div', class_='description')
                
                # Linisin ang description (Text only)
                full_description = description_div.get_text(separator="\n").strip() if description_div else "Check link"
                # Putulin kung sobrang haba para hindi sumabog ang sheets (Optional)
                
                # Tags / Skills (Badges)
                tags = []
                for badge in job_soup.find_all('span', class_='badge'):
                    tags.append(badge.text.strip())
                
                tags_string = ", ".join(tags)

                # Salary (Minsan wala, minsan nasa tags)
                # Check tags for "$"
                salary = "Not Disclosed"
                salary_type = "N/A"
                for t in tags:
                    if "$" in t:
                        salary = t
                        salary_type = "Contract" if "hour" in t or "hora" in t else "Yearly/Monthly"

                # Date Posted (Hanapin ang "Hace x horas")
                # WeRemoto usually puts date in a span/p near title
                # For now, we use Today's date since we scrape daily
                date_posted = get_todays_date()

                # --- MAPPING TO YOUR GOOGLE SHEETS COLUMNS ---
                job_data = {
                    "Date": date_posted,
                    "Company Email": "N/A", # Needs Enrichment Tool
                    "Company Name": company_name,
                    "Company Description": "N/A", # Needs AI to generate from desc
                    "Company Website": "N/A", # Needs AI to deduce
                    "Required Skills": tags_string, # Needs AI to split to Tools/Industries
                    "Required Tools": "Use AI to extract", 
                    "Required Industries": "Use AI to extract",
                    "Max # of Applicants": "N/A",
                    "Link": job_url, # Ito yung LinkedIn URL column mo, ginawa kong job link
                    "Job Title": title,
                    "Job Description": full_description,
                    "Salary Type": salary_type,
                    "Salary": salary
                }

                data.append(job_data)
                count += 1
                
                # Konting delay para hindi ma-ban IP
                time.sleep(0.5)

            except Exception as e:
                continue

        print(json.dumps(data))

    except Exception as e:
        # Return empty list on error
        print(json.dumps([{"error": str(e)}]))

if __name__ == "__main__":
    # Get limit from args
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    scrape_weremoto(limit_arg)
