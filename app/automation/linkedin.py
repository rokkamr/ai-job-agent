import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging

logger = logging.getLogger(__name__)


def fetch_linkedin_jobs(keywords: list, location: str = "India") -> list:
    jobs = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for kw in keywords[:3]:  # Top keywords
        try:
            query = urllib.parse.quote(kw)
            loc = urllib.parse.quote(location)
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&location={loc}&start=0"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                job_cards = soup.find_all("li")
                for card in job_cards:
                    title_elem = card.find("h3", class_="base-search-card__title")
                    company_elem = card.find("h4", class_="base-search-card__subtitle")
                    loc_elem = card.find("span", class_="job-search-card__location")
                    link_elem = card.find("a", class_="base-card__full-link")

                    if title_elem and company_elem and link_elem:
                        title = title_elem.text.strip()
                        company = company_elem.text.strip()
                        loc_str = loc_elem.text.strip() if loc_elem else location
                        job_url = link_elem["href"].split("?")[0]

                        jobs.append({
                            "source": "LinkedIn",
                            "external_job_id": job_url.split("-")[-1],
                            "title": title,
                            "company": company,
                            "location": loc_str,
                            "url": job_url,
                            "description": f"LinkedIn QA position for {title} at {company}",
                            "posted_date": ""
                        })
        except Exception as e:
            logger.error(f"Error fetching LinkedIn jobs for {kw}: {e}")

    return jobs
