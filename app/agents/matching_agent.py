import json
import logging
from sqlalchemy.orm import Session
from app.database.models import Job
from app.matching.scorer import JobMatchScorer

logger = logging.getLogger(__name__)


class MatchingAgent:
    def __init__(self, db_session: Session, candidate_kb: dict, min_score: float = 70.0):
        self.db = db_session
        self.candidate_kb = candidate_kb
        self.min_score = min_score
        self.scorer = JobMatchScorer(candidate_kb)

    def evaluate_discovered_jobs(self) -> dict:
        """
        Processes all jobs with status='DISCOVERED', runs hard pre-filters & scoring, and updates database records.
        """
        discovered_jobs = self.db.query(Job).filter(Job.status == "DISCOVERED").all()
        evaluated_count = len(discovered_jobs)
        qualified_jobs = []

        for job in discovered_jobs:
            # Hard filter 1: Closed job indicator in text
            if "closed" in job.description.lower() or "no longer accepting applications" in job.description.lower():
                job.status = "SKIPPED"
                continue

            scores = self.scorer.evaluate_job(job.title, job.description, job.location)
            job.match_score = scores["overall_score"]
            job.match_details = json.dumps(scores)

            # Hard filter 2: Minimum match threshold
            if job.match_score >= self.min_score:
                job.status = "QUALIFIED"
                qualified_jobs.append(job)
            else:
                job.status = "SKIPPED"

        self.db.commit()
        logger.info(f"Evaluation complete. Evaluated: {evaluated_count}, Qualified (Score >= {self.min_score}): {len(qualified_jobs)}")

        return {
            "evaluated": evaluated_count,
            "qualified_count": len(qualified_jobs),
            "qualified_jobs": qualified_jobs
        }
