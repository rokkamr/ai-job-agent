import requests
import logging

logger = logging.getLogger(__name__)


def fetch_remoteok_jobs(keywords: list) -> list:
    jobs = []
    try:
        url = "https://remoteok.com/api"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # First item in RemoteOK JSON is legal notice dict
            for item in data[1:]:
                title = item.get("position", "")
                company = item.get("company", "")
                job_url = item.get("url", "")
                tags = item.get("tags", [])
                description = item.get("description", "")
                
                # Filter against QA keywords
                combined_text = f"{title} {' '.join(tags)}".lower()
                if any(k.lower() in combined_text for k in keywords):
                    jobs.append({
                        "source": "RemoteOK",
                        "external_job_id": str(item.get("id", "")),
                        "title": title,
                        "company": company,
                        "location": "Remote",
                        "url": job_url if job_url.startswith("http") else f"https://remoteok.com{job_url}",
                        "description": description[:2000],
                        "posted_date": item.get("date", "")
                    })
    except Exception as e:
        logger.error(f"Error fetching RemoteOK jobs: {e}")
    return jobs
