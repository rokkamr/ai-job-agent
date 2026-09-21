import os
import json
import logging
from pathlib import Path

from google import genai
from google.genai import types
import yaml

log = logging.getLogger(__name__)


class ResumeParser:
    def __init__(self, config: dict):
        self.config = config
        self._init_gemini()
        self.resume_path = Path(config["resume"]["path"])

    def _init_gemini(self):
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or self.config.get("gemini", {}).get("api_key", "")
        )
        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            raise ValueError(
                "Gemini API key not set!\n"
                "  Option 1: Set the GEMINI_API_KEY environment variable\n"
                "  Option 2: Edit config.yaml and set gemini.api_key\n"
                "  Get a free key at: https://aistudio.google.com/app/apikey"
            )
        self.client = genai.Client(api_key=api_key)
        self.model_name = self.config.get("gemini", {}).get("model", "gemini-2.0-flash")

    def parse(self) -> dict:
        """Parse the resume and return a structured profile dict."""
        cache_path = self.resume_path.parent / "profile_cache.json"
        if cache_path.exists():
            log.info(f"   Loading cached resume profile from: {cache_path}")
            try:
                profile = json.loads(cache_path.read_text(encoding="utf-8"))
                profile["preferred_location"] = self.config["job_preferences"]["location"]
                profile["preferred_job_types"] = self.config["job_preferences"]["job_types"]
                return profile
            except Exception as e:
                log.warning(f"   Cache read failed ({e}), re-parsing resume...")

        if not self.resume_path.exists():
            raise FileNotFoundError(
                f"❌ Resume not found at: {self.resume_path}\n"
                f"   Please place your resume PDF in the 'resume/' folder."
            )

        log.info(f"   Reading resume: {self.resume_path}")
        text = self._extract_text(self.resume_path)

        if not text or len(text.strip()) < 50:
            raise ValueError(
                f"❌ Could not extract text from resume. "
                f"Make sure the PDF is not scanned/image-only."
            )

        log.info(f"   Extracted {len(text)} characters from resume")
        profile = self._extract_profile_with_gemini(text)

        # Cache profile for future runs
        try:
            cache_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            log.info(f"   Cached profile to: {cache_path}")
        except Exception as e:
            log.warning(f"   Failed to cache profile: {e}")

        return profile

    def _extract_text(self, path: Path) -> str:
        """Extract raw text from PDF, DOCX, or TXT file."""
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._read_pdf(path)
        elif ext == ".docx":
            return self._read_docx(path)
        elif ext == ".txt":
            return path.read_text(encoding="utf-8")
        else:
            raise ValueError(f"Unsupported resume format: {ext}. Use PDF, DOCX, or TXT.")

    def _read_pdf(self, path: Path) -> str:
        """Extract text from PDF using pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text)
        except Exception as e:
            log.warning(f"   pypdf read error ({e}), trying PyPDF2...")
            import PyPDF2
            with open(path, "rb") as f:
                r = PyPDF2.PdfReader(f)
                return "\n".join(p.extract_text() for p in r.pages if p.extract_text())

    def _read_docx(self, path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("Run: pip install python-docx")

        doc = Document(str(path))
        return "\n".join(para.text for para in doc.paragraphs)

    def _extract_profile_with_gemini(self, text: str) -> dict:
        prompt = f"""
Analyze the following resume text carefully:

---
{text}
---

Extract and return a JSON object with EXACTLY this structure (no markdown, just raw JSON):
{{
  "name": "Full name of the candidate",
  "email": "email address or empty string",
  "phone": "phone number or empty string",
  "location": "current city/location or empty string",
  "summary": "2-3 sentence professional summary",
  "skills": ["list", "of", "technical", "and", "soft", "skills"],
  "primary_skills": ["top 5-7 most prominent skills"],
  "experience_years": {self.config['job_preferences']['experience_years']},
  "experience_level": "{self.config['job_preferences']['experience_level']}",
  "current_title": "most recent job title",
  "job_titles": ["list of past and target job titles"],
  "industries": ["relevant industries"],
  "education": ["degree and institution, year"],
  "certifications": ["any certifications"],
  "search_keywords": [
    "10-15 specific job search keywords combining skills and roles"
  ],
  "role_queries": [
    "5 specific job role queries to search for"
  ]
}}

Rules:
- experience_years: Use {self.config['job_preferences']['experience_years']} years as the actual value
- experience_level: Use "{self.config['job_preferences']['experience_level']}"
"""
        models_to_try = [
            self.model_name,
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
        ]
        # Remove duplicates preserving order
        models_to_try = list(dict.fromkeys(models_to_try))

        for m in models_to_try:
            try:
                log.info(f"   Calling Gemini ({m}) to extract profile...")
                response = self.client.models.generate_content(
                    model=m,
                    contents=prompt,
                )
                raw = response.text.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()
                profile = json.loads(raw)
                profile["preferred_location"] = self.config["job_preferences"]["location"]
                profile["preferred_job_types"] = self.config["job_preferences"]["job_types"]
                return profile
            except Exception as e:
                log.warning(f"   Model {m} failed ({e})")
                import time
                time.sleep(2)

        log.warning("   All Gemini model calls failed/rate-limited. Falling back to heuristic resume parser...")
        return self._heuristic_fallback_profile(text)

    def _heuristic_fallback_profile(self, text: str) -> dict:
        """Fallback profile parser when AI API quota is exceeded."""
        import re
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name = lines[0] if lines else "Candidate"
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        email = emails[0] if emails else self.config.get("email", {}).get("sender_email", "")

        common_skills = [
            "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js",
            "Django", "Flask", "FastAPI", "SQL", "PostgreSQL", "MySQL", "MongoDB",
            "REST API", "Docker", "Kubernetes", "AWS", "Git", "Linux", "HTML", "CSS",
            "Machine Learning", "Data Analysis", "Spring Boot", "Microservices"
        ]
        found_skills = [s for s in common_skills if re.search(r'\b' + re.escape(s) + r'\b', text, re.I)]
        if not found_skills:
            found_skills = ["Python", "Software Engineering", "REST APIs", "SQL"]

        exp_years = self.config["job_preferences"]["experience_years"]
        exp_level = self.config["job_preferences"]["experience_level"]
        loc = self.config["job_preferences"]["location"]

        return {
            "name": name,
            "email": email,
            "current_title": "Software Developer",
            "summary": f"Developer with {exp_years} years experience skilled in {', '.join(found_skills[:4])}.",
            "skills": found_skills,
            "primary_skills": found_skills[:6],
            "experience_years": exp_years,
            "experience_level": exp_level,
            "job_titles": ["Software Developer", "Python Developer", "Full Stack Developer", "Backend Developer"],
            "search_keywords": [f"{s} {loc}" for s in found_skills[:5]] + ["Software Engineer Hyderabad", "Python Developer Remote"],
            "role_queries": ["Software Developer", "Python Developer", "Backend Engineer", "Full Stack Developer"],
            "preferred_location": loc,
            "preferred_job_types": self.config["job_preferences"]["job_types"],
        }
