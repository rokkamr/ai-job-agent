import requests
import logging

logger = logging.getLogger(__name__)


def fetch_arbeitnow_jobs(keywords: list) -> list:
    jobs = []
    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                title = item.get("title", "")
                company = item.get("company_name", "")
                location = item.get("location", "")
                job_url = item.get("url", "")
                description = item.get("description", "")

                combined_text = f"{title} {description}".lower()
                if any(k.lower() in combined_text for k in keywords):
                    jobs.append({
                        "source": "Arbeitnow",
                        "external_job_id": item.get("slug", ""),
                        "title": title,
                        "company": company,
                        "location": location or "Remote / Hybrid",
                        "url": job_url,
                        "description": description[:2000],
                        "posted_date": ""
                    })
    except Exception as e:
        logger.error(f"Error fetching Arbeitnow jobs: {e}")
    return jobs
