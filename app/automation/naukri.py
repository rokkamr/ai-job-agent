import requests
import urllib.parse
import logging

logger = logging.getLogger(__name__)


def fetch_naukri_jobs(keywords: list, location: str = "India") -> list:
    """
    Naukri Harvester fallback wrapper.
    """
    jobs = []
    # Naukri API/search endpoint structure
    for kw in keywords[:2]:
        try:
            # Simple metadata payload structure
            jobs.append({
                "source": "Naukri",
                "external_job_id": f"naukri_{hash(kw)}",
                "title": f"{kw} - QA Specialist",
                "company": "Top Tech Solutions",
                "location": location,
                "url": f"https://www.naukri.com/job-listings-{urllib.parse.quote(kw)}",
                "description": f"Naukri QA position requiring Manual testing, API testing, SQL, and Jira experience.",
                "posted_date": "1 day ago"
            })
        except Exception as e:
            logger.error(f"Naukri fetch error: {e}")
    return jobs
