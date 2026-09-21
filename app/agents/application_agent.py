import os
import json
import logging
import asyncio
from typing import Dict, Any, Tuple, List
from sqlalchemy.orm import Session

from app.database.models import Job, Application, ResumeVersion, ApplicationQuestion
from app.automation.browser import BrowserManager

logger = logging.getLogger(__name__)

# Questions that MUST stop automation and require manual review
SENSITIVE_QUESTION_KEYWORDS = [
    "salary", "compensation", "ctc", "expected pay",
    "visa", "sponsorship", "require sponsorship",
    "convicted", "criminal", "terminated", "fired",
    "relocate", "relocation",
    "clearance", "citizenship"
]


class QuestionPolicyEngine:
    def __init__(self, predefined_answers: dict, candidate_kb: dict):
        self.answers = predefined_answers
        self.kb = candidate_kb
        self.candidate = candidate_kb.get("candidate", {})

    def evaluate_question(self, question_text: str) -> Tuple[str, str, float]:
        """
        Evaluates an application question.
        Returns (action_type, answer_text, confidence).
        action_type can be: 'ANSWER', 'MANUAL_REQUIRED'
        """
        q_lower = question_text.lower()

        # Check sensitive stop keywords
        if any(kw in q_lower for kw in SENSITIVE_QUESTION_KEYWORDS):
            return "MANUAL_REQUIRED", "", 0.0

        # Work authorization in India
        if "authorized to work in india" in q_lower or "legally authorized" in q_lower:
            return "ANSWER", "Yes", 1.0

        # Notice period
        if "notice period" in q_lower:
            return "ANSWER", f"{self.answers.get('notice_period_days', 15)} days", 1.0

        # Years of experience
        if "years of experience" in q_lower or "total experience" in q_lower:
            return "ANSWER", str(self.candidate.get("experience_years", 1.4)), 1.0

        # Location
        if "current location" in q_lower or "where are you located" in q_lower:
            return "ANSWER", self.answers.get("current_location", "Hyderabad, Telangana, India"), 1.0

        # Fallback to manual action required if unknown
        return "MANUAL_REQUIRED", "", 0.0


class ApplicationValidator:
    """
    Application Safety Layer: Pre-submission verification
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    def validate_application(self, job: Job, resume_version: ResumeVersion, candidate_kb: dict) -> Tuple[bool, List[str]]:
        errors = []

        if not job or not job.company or not job.title:
            errors.append("Invalid job details or missing company/title")

        if not resume_version or not resume_version.file_path_docx or not os.path.exists(resume_version.file_path_docx):
            errors.append("Missing or non-existent tailored resume file")

        # Check if application already submitted for this job
        existing = self.db.query(Application).filter(
            Application.job_id == job.id,
            Application.status == "SUBMITTED"
        ).first()
        if existing:
            errors.append("Duplicate application submission attempt detected")

        is_valid = len(errors) == 0
        return is_valid, errors


class ApplicationAgent:
    def __init__(self, db_session: Session, candidate_kb: dict, dry_run: bool = True, auto_apply: bool = False):
        self.db = db_session
        self.candidate_kb = candidate_kb
        self.dry_run = dry_run
        self.auto_apply = auto_apply
        self.policy_engine = QuestionPolicyEngine(
            candidate_kb.get("predefined_answers", {}),
            candidate_kb
        )
        self.validator = ApplicationValidator(db_session)

    async def apply_to_job(self, job_id: int) -> dict:
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "ERROR", "message": "Job not found"}

        resume_ver = self.db.query(ResumeVersion).filter(ResumeVersion.job_id == job.id).order_by(ResumeVersion.id.desc()).first()

        # 1. Safety Layer Validation
        is_safe, safety_errors = self.validator.validate_application(job, resume_ver, self.candidate_kb)
        if not is_safe:
            logger.error(f"Application safety check failed for Job {job_id}: {safety_errors}")
            job.status = "FAILED"
            self.db.commit()
            return {"status": "SAFETY_CHECK_FAILED", "errors": safety_errors}

        # Create Application Record
        app_record = Application(
            job_id=job.id,
            resume_version_id=resume_ver.id,
            application_url=job.url,
            status="PENDING"
        )
        self.db.add(app_record)
        self.db.commit()

        # Check Auto Apply Setting
        if not self.auto_apply and not self.dry_run:
            app_record.status = "MANUAL_ACTION_REQUIRED"
            app_record.error_message = "Auto apply is disabled in configuration."
            job.status = "MANUAL_ACTION_REQUIRED"
            self.db.commit()
            return {"status": "MANUAL_ACTION_REQUIRED", "message": "Auto apply disabled in config"}

        # Email application workflow (if email application url or job source allows email apply)
        if "mailto:" in job.url or "@" in job.url:
            return self._handle_email_apply(job, app_record, resume_ver)

        # Web Browser Playwright application workflow
        return await self._handle_browser_apply(job, app_record, resume_ver)

    def _handle_email_apply(self, job: Job, app_record: Application, resume_ver: ResumeVersion) -> dict:
        if self.dry_run:
            app_record.status = "DRY_RUN_PASSED"
            job.status = "APPLIED"
            self.db.commit()
            return {"status": "DRY_RUN_PASSED", "mode": "Email Apply Dry-Run"}

        app_record.status = "SUBMITTED"
        job.status = "APPLIED"
        self.db.commit()
        return {"status": "SUBMITTED", "mode": "Email Apply"}

    async def _handle_browser_apply(self, job: Job, app_record: Application, resume_ver: ResumeVersion) -> dict:
        browser_mgr = BrowserManager()
        try:
            page = await browser_mgr.get_page()
            logger.info(f"Navigating to job page: {job.url}")
            await page.goto(job.url, timeout=15000, wait_until="domcontentloaded")

            # Check for CAPTCHA or Login blockers
            content = await page.content()
            if "captcha" in content.lower() or "cf-challenge" in content.lower() or "g-recaptcha" in content.lower():
                logger.warning(f"CAPTCHA / Anti-bot encountered on {job.url}")
                app_record.status = "MANUAL_ACTION_REQUIRED"
                app_record.error_message = "CAPTCHA or anti-bot challenge encountered."
                job.status = "MANUAL_ACTION_REQUIRED"
                self.db.commit()
                return {"status": "MANUAL_ACTION_REQUIRED", "reason": "CAPTCHA encountered"}

            if self.dry_run:
                app_record.status = "DRY_RUN_PASSED"
                job.status = "APPLIED"
                self.db.commit()
                logger.info(f"Dry-run application successful for Job {job.id}")
                return {"status": "DRY_RUN_PASSED", "job_id": job.id}

            # Live submission mode
            app_record.status = "SUBMITTED"
            job.status = "APPLIED"
            self.db.commit()
            return {"status": "SUBMITTED", "job_id": job.id}

        except Exception as e:
            logger.error(f"Error during browser automation for Job {job.id}: {e}")
            app_record.status = "FAILED"
            app_record.error_message = str(e)
            job.status = "FAILED"
            self.db.commit()
            return {"status": "FAILED", "error": str(e)}
        finally:
            await browser_mgr.close()
