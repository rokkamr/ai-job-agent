import os
import json
import yaml
from pathlib import Path
from pypdf import PdfReader
from google import genai

def parse_resume():
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    api_key = cfg["gemini"]["api_key"]
    client = genai.Client(api_key=api_key)

    resume_path = Path(cfg["resume"]["path"])
    if not resume_path.exists():
        resume_path = Path("D:/Rokkam_Raja_Resume.pdf")

    print(f"Reading PDF: {resume_path.resolve()}")
    reader = PdfReader(str(resume_path))
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    print(f"Extracted Raw Text Length: {len(text)} characters")

    prompt = f"""
Analyze the following candidate resume text completely and extract an exhaustive, detailed structured profile.

RESUME TEXT:
---
{text}
---

Return a JSON object with EXACTLY this structure (no markdown, raw JSON only):
{{
  "name": "Full Candidate Name",
  "email": "Candidate Email",
  "phone": "Candidate Phone",
  "location": "Candidate Location",
  "summary": "Comprehensive 3-4 sentence professional summary highlighting key achievements and skills",
  "skills": ["all technical skills, frameworks, databases, tools, programming languages, cloud services, methodologies"],
  "primary_skills": ["top 7-10 core skills"],
  "experience_years": {cfg['job_preferences']['experience_years']},
  "experience_level": "{cfg['job_preferences']['experience_level']}",
  "current_title": "Most recent job title",
  "job_titles": ["target and past job titles"],
  "education": ["degrees, college, year"],
  "certifications": ["certifications if any"],
  "search_keywords": ["15-20 specific job search queries combining primary skills and roles"],
  "role_queries": ["6-8 job titles to search on job boards"]
}}
"""

    print("Calling Gemini 3.6 Flash to parse full resume...")
    response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    profile = json.loads(raw)
    profile["preferred_location"] = cfg["job_preferences"]["location"]
    profile["preferred_job_types"] = cfg["job_preferences"]["job_types"]

    print("\n✅ Full Profile Extracted:")
    print("Candidate Name:", profile.get("name"))
    print("Primary Skills:", profile.get("primary_skills"))
    print("All Skills:", profile.get("skills"))
    print("Role Queries:", profile.get("role_queries"))

    cache_path = Path("resume/profile_cache.json")
    cache_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved updated profile to {cache_path.resolve()}")

if __name__ == "__main__":
    parse_resume()
