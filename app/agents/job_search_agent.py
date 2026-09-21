import logging
from sqlalchemy.orm import Session

from app.automation.remoteok import fetch_remoteok_jobs
from app.automation.arbeitnow import fetch_arbeitnow_jobs
from app.automation.linkedin import fetch_linkedin_jobs
from app.automation.naukri import fetch_naukri_jobs
from app.automation.foundit import fetch_foundit_jobs

from app.matching.filters import DuplicateDetector, create_job_fingerprint
from app.database.models import Job

logger = logging.getLogger(__name__)


class JobSearchAgent:
    def __init__(self, db_session: Session, target_roles: list = None):
        self.db = db_session
        self.target_roles = target_roles or [
            "QA Engineer", "Software Tester", "Manual QA Tester", "QA Analyst", "Software Test Engineer"
        ]
        self.dupe_detector = DuplicateDetector(self.db)

    def discover_jobs(self) -> dict:
        """
        Discovers jobs across configured sources, deduplicates, and saves new records.
        """
        raw_jobs = []

        logger.info("Harvesting RemoteOK jobs...")
        raw_jobs.extend(fetch_remoteok_jobs(self.target_roles))

        logger.info("Harvesting Arbeitnow jobs...")
        raw_jobs.extend(fetch_arbeitnow_jobs(self.target_roles))

        logger.info("Harvesting LinkedIn jobs...")
        raw_jobs.extend(fetch_linkedin_jobs(self.target_roles))

        logger.info("Harvesting Naukri jobs...")
        raw_jobs.extend(fetch_naukri_jobs(self.target_roles))

        logger.info("Harvesting Foundit jobs...")
        raw_jobs.extend(fetch_foundit_jobs(self.target_roles))

        total_found = len(raw_jobs)
        duplicates_count = 0
        new_jobs = []
        seen_urls = set()
        seen_fingerprints = set()

        for item in raw_jobs:
            url = item.get("url")
            company = item.get("company", "")
            title = item.get("title", "")
            location = item.get("location", "")

            if not url or url in seen_urls:
                duplicates_count += 1
                continue

            fingerprint = create_job_fingerprint(company, title, location)
            if fingerprint in seen_fingerprints:
                duplicates_count += 1
                continue

            if self.dupe_detector.is_duplicate(url, company, title, location):
                duplicates_count += 1
                continue

            seen_urls.add(url)
            seen_fingerprints.add(fingerprint)

            try:
                job_rec = Job(
                    source=item.get("source"),
                    external_job_id=item.get("external_job_id"),
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=item.get("description", ""),
                    posted_date=item.get("posted_date", ""),
                    fingerprint=fingerprint,
                    status="DISCOVERED"
                )
                self.db.add(job_rec)
                self.db.commit()
                new_jobs.append(job_rec)
            except Exception as e:
                self.db.rollback()
                duplicates_count += 1
                logger.warning(f"Skipping duplicate or constrained job ({url}): {e}")

        logger.info(f"Discovery complete. Found: {total_found}, Duplicates: {duplicates_count}, New: {len(new_jobs)}")

        return {
            "total_found": total_found,
            "duplicates": duplicates_count,
            "new_saved": len(new_jobs),
            "jobs": new_jobs
        }
