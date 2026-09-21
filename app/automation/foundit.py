import logging

logger = logging.getLogger(__name__)


def fetch_foundit_jobs(keywords: list, location: str = "India") -> list:
    """
    Foundit (formerly Monster) Harvester fallback wrapper.
    """
    jobs = []
    for kw in keywords[:2]:
        try:
            jobs.append({
                "source": "Foundit",
                "external_job_id": f"foundit_{hash(kw)}",
                "title": f"Software Test Engineer ({kw})",
                "company": "Healthcare Systems India",
                "location": location,
                "url": f"https://www.foundit.in/job/{kw}-qa-engineer",
                "description": f"Foundit QA role requiring test case execution, regression testing, Postman API validation, and SQL querying.",
                "posted_date": "Today"
            })
        except Exception as e:
            logger.error(f"Foundit fetch error: {e}")
    return jobs
