import os
import json
import pymupdf as fitz
import docx
import yaml


class ResumeParser:
    def __init__(self, master_resume_path: str = None):
        if master_resume_path is None:
            # Default lookup paths
            possible_paths = [
                os.path.join("resumes", "master", "master_resume.docx"),
                os.path.join("resumes", "master", "master_resume.pdf"),
                os.path.join("resume", "resume.pdf"),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    master_resume_path = p
                    break

        self.resume_path = master_resume_path

    def extract_text(self) -> str:
        if not self.resume_path or not os.path.exists(self.resume_path):
            return ""

        ext = os.path.splitext(self.resume_path)[1].lower()
        text = ""

        if ext == ".pdf":
            doc = fitz.open(self.resume_path)
            for page in doc:
                text += page.get_text()
        elif ext in [".docx", ".doc"]:
            doc = docx.Document(self.resume_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        
        return text.strip()

    def load_user_profile_config(self) -> dict:
        config_path = os.path.join("config", "user_profile.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def get_candidate_knowledge_base(self) -> dict:
        """
        Builds the structured Candidate Knowledge Base by combining config data and extracted resume text.
        """
        config_data = self.load_user_profile_config()
        candidate_cfg = config_data.get("candidate", {})
        
        extracted_text = self.extract_text()

        # Cache file fallback if available
        cache_path = os.path.join("resume", "profile_cache.json")
        cached_data = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
            except Exception:
                pass

        kb = {
            "candidate": {
                "name": candidate_cfg.get("name", cached_data.get("name", "Rokkam Raja")),
                "email": candidate_cfg.get("email", "rajarokkam14@gmail.com"),
                "phone": candidate_cfg.get("phone", "+91 9876543210"),
                "experience_years": candidate_cfg.get("experience_years", 1.4),
                "experience_summary": cached_data.get("experience", "1 year 4 months QA experience"),
            },
            "skills": candidate_cfg.get("skills", cached_data.get("skills", [])),
            "target_roles": candidate_cfg.get("target_roles", []),
            "domains": candidate_cfg.get("domains", ["Healthcare", "Healthcare Staffing"]),
            "projects": cached_data.get("projects", [
                {
                    "name": "NurseIO",
                    "domain": "Healthcare Staffing / Workforce Management",
                    "testing": ["Web", "Mobile (BrowserStack / TestFlight)", "API (Postman)", "Regression"],
                    "details": "Executed manual and API testing for healthcare staffing platform, verified web and mobile flows, logged defects in Jira."
                }
            ]),
            "education": cached_data.get("education", [
                {
                    "degree": "Bachelor's Degree",
                    "field": "Computer Science / Engineering",
                    "institution": "University / College"
                }
            ]),
            "predefined_answers": config_data.get("predefined_answers", {}),
            "raw_text": extracted_text
        }
        return kb
