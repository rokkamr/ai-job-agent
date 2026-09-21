import os
import json
import logging
from sqlalchemy.orm import Session

from app.database.models import Job, ResumeVersion
from app.resume.tailor import ResumeTailor
from app.agents.truth_validator import TruthValidator
from app.resume.generator import ResumeGenerator

logger = logging.getLogger(__name__)


class ResumeTailorAgent:
    def __init__(self, db_session: Session, candidate_kb: dict):
        self.db = db_session
        self.candidate_kb = candidate_kb
        self.tailor = ResumeTailor(candidate_kb)
        self.truth_validator = TruthValidator(candidate_kb)

    def tailor_resume_for_job(self, job_id: int) -> dict:
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job ID {job_id} not found")

        # 1. Generate tailored text content
        tailored_data = self.tailor.tailor_profile_for_job(job.title, job.description)

        # 2. Programmatic Truth Protection Check
        is_valid, violations = self.truth_validator.validate_tailored_profile(
            tailored_data["summary"],
            tailored_data["ordered_skills"]
        )

        if not is_valid:
            logger.error(f"TruthValidator rejected resume tailoring for Job {job_id}: {violations}")
            job.status = "MANUAL_ACTION_REQUIRED"
            self.db.commit()
            return {"status": "TRUTH_VALIDATION_FAILED", "violations": violations}

        # 3. Output directory under resumes/tailored/{job_id}/
        output_dir = os.path.join("resumes", "tailored", f"job_{job_id}")
        generator = ResumeGenerator(output_dir)

        contact_info = {
            "email": self.candidate_kb.get("candidate", {}).get("email", "rajarokkam14@gmail.com"),
            "phone": self.candidate_kb.get("candidate", {}).get("phone", "+91 9876543210"),
            "location": "Hyderabad, Telangana, India"
        }

        docx_path = generator.generate_docx(
            candidate_name=self.candidate_kb.get("candidate", {}).get("name", "Rokkam Raja"),
            contact_info=contact_info,
            summary=tailored_data["summary"],
            skills=tailored_data["ordered_skills"],
            experience=tailored_data["experience"],
            education=tailored_data["education"]
        )

        pdf_path = generator.generate_pdf_from_docx(docx_path)

        # 4. Save ResumeVersion record
        resume_version = ResumeVersion(
            job_id=job.id,
            file_path_docx=docx_path,
            file_path_pdf=pdf_path,
            skills_added=json.dumps(tailored_data["matched_keywords"]),
            keywords_used=json.dumps(tailored_data["matched_keywords"]),
            truth_verified=True
        )
        self.db.add(resume_version)
        job.status = "TAILORED"
        self.db.commit()

        logger.info(f"Resume tailored successfully for Job {job_id} at {output_dir}")

        return {
            "status": "TAILORED",
            "resume_version_id": resume_version.id,
            "docx_path": docx_path,
            "pdf_path": pdf_path
        }
