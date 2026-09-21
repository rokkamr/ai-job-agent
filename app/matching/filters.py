import re
import datetime
from sqlalchemy.orm import Session
from app.database.models import Job


def normalize_string(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def create_job_fingerprint(company: str, title: str, location: str = "") -> str:
    norm_company = normalize_string(company)
    norm_title = normalize_string(title)
    norm_loc = normalize_string(location)
    return f"{norm_company}:{norm_title}:{norm_loc}"


class DuplicateDetector:
    def __init__(self, db_session: Session):
        self.db = db_session

    def is_duplicate(self, url: str, company: str, title: str, location: str = "", memory_days: int = 30) -> bool:
        """
        Two-tier duplicate detection:
        Tier 1: Exact URL or external_job_id match
        Tier 2: Fingerprint (company + title + location) applied within the last `memory_days`
        """
        # Tier 1: URL match
        existing_url = self.db.query(Job).filter(Job.url == url).first()
        if existing_url:
            return True

        # Tier 2: Fingerprint within memory_days
        fingerprint = create_job_fingerprint(company, title, location)
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=memory_days)

        existing_fingerprint = (
            self.db.query(Job)
            .filter(
                Job.fingerprint == fingerprint,
                Job.created_at >= cutoff_date
            )
            .first()
        )

        if existing_fingerprint:
            return True

        return False
