"""
resume_optimizer.py
-------------------
Uses Gemini AI (ONE batch call) to optimize the resume for every matched job.
For each job it produces:
  - tailored_summary  : rewritten professional summary matching the JD
  - highlighted_skills: skills from the resume that best fit this role
  - ats_keywords      : ATS-critical keywords from the JD to weave in
  - cover_letter      : full 3-paragraph personalised cover letter
  - email_subject     : ready-to-use email subject line
"""

import json
import logging
import os

from google import genai

log = logging.getLogger(__name__)


class ResumeOptimizer:
    def __init__(self, config: dict):
        self.config = config
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or config.get("gemini", {}).get("api_key", "")
        )
        self.client = genai.Client(api_key=api_key)
        self.model_name = config.get("gemini", {}).get("model", "gemini-3.6-flash")

    def optimize_all(self, profile: dict, jobs: list[dict]) -> list[dict]:
        """
        Optimize resume content for ALL jobs in ONE Gemini API call.
        Returns a list of optimization dicts aligned by index with `jobs`.
        """
        if not jobs:
            return []

        log.info(f"   Tailoring resume for {len(jobs)} jobs (single batch call)...")

        profile_summary = {
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "skills": profile.get("skills", []),
            "primary_skills": profile.get("primary_skills", []),
            "experience_years": profile.get("experience_years", 0),
            "experience_level": profile.get("experience_level", "entry"),
            "current_title": profile.get("current_title", ""),
            "summary": profile.get("summary", ""),
            "education": profile.get("education", []),
            "job_titles": profile.get("job_titles", []),
        }

        job_list = [
            {
                "index": i,
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location", ""),
                "description": (j.get("description") or "")[:900],
            }
            for i, j in enumerate(jobs)
        ]

        prompt = f"""
You are an expert resume writer and career coach.
Tailor a job application package for each listing below based on the candidate's profile.

CANDIDATE PROFILE:
{json.dumps(profile_summary, indent=2)}

JOB LISTINGS:
{json.dumps(job_list, indent=2)}

Return a JSON ARRAY (raw JSON, no markdown) with EXACTLY {len(jobs)} objects:
[
  {{
    "index": 0,
    "tailored_summary": "3-4 sentence professional summary rewritten to match this specific role and company. Use first person.",
    "highlighted_skills": ["skill1", "skill2", "skill3"],
    "ats_keywords": ["keyword1", "keyword2", "keyword3"],
    "cover_letter": "Full 3-paragraph cover letter. Para 1: Express enthusiasm and hook. Para 2: Match specific experience to role. Para 3: Call to action. 280-350 words. Mention the company name and role specifically.",
    "email_subject": "Application for [Job Title] at [Company] – [Candidate Name]"
  }},
  ...
]

Rules:
- tailored_summary: Emphasise skills most relevant to the JD. Match energy/tone to company culture.
- highlighted_skills: 5-8 skills from the candidate's profile that best match the JD
- ats_keywords: 8-12 exact keywords/phrases from the JD description (for ATS systems)
- cover_letter: Professional, warm, and specific. Do NOT use generic filler sentences.
- Return EXACTLY {len(jobs)} objects in the same order as input.
"""

        optimizations = None
        for m in [self.model_name, "gemini-3.6-flash"]:
            try:
                log.info(f"   Calling Gemini ({m}) to optimize resume for {len(jobs)} jobs...")
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
                optimizations = json.loads(raw)
                break
            except Exception as e:
                log.warning(f"   Model {m} failed for resume optimizer ({e})")
                import time
                time.sleep(2)

        if not optimizations:
            log.warning("   Gemini API unavailable/rate-limited for resume optimizer. Using template-based optimization...")
            return self._fallback_optimize_all(profile, jobs)

        opt_map = {o["index"]: o for o in optimizations}

        results = []
        for i, job in enumerate(jobs):
            o = opt_map.get(i, {})
            results.append({
                "index": i,
                "tailored_summary": o.get("tailored_summary", profile.get("summary", "")),
                "highlighted_skills": o.get("highlighted_skills", profile.get("primary_skills", [])),
                "ats_keywords": o.get("ats_keywords", []),
                "cover_letter": o.get("cover_letter", ""),
                "email_subject": o.get(
                    "email_subject",
                    f"Application for {job.get('title', 'the role')} at {job.get('company', '')} – {profile.get('name', '')}",
                ),
            })

        log.info(f"   Resume tailored for all {len(jobs)} jobs")
        return results

    def _fallback_optimize_all(self, profile: dict, jobs: list[dict]) -> list[dict]:
        """Template-based resume optimizer fallback when API quota is exhausted."""
        name = profile.get("name", "Candidate")
        skills = profile.get("primary_skills", profile.get("skills", []))
        skills_str = ", ".join(skills[:5])
        years = profile.get("experience_years", 1.4)

        results = []
        for i, job in enumerate(jobs):
            title = job.get("title", "Software Developer")
            company = job.get("company", "Company")

            summary = (
                f"Results-oriented {title} with {years} years of experience specializing in {skills_str}. "
                f"Proven ability to deliver high-quality solutions, collaborate effectively, and drive project success at {company}."
            )
            cover_letter = (
                f"Dear Hiring Manager at {company},\n\n"
                f"I am writing to express my strong interest in the {title} position at {company}. "
                f"With over {years} years of practical experience working with {skills_str}, I am confident in my ability to contribute value immediately.\n\n"
                f"Throughout my career, I have consistently focused on building scalable, reliable software applications and solving complex problems. "
                f"I admire {company}'s work and would be thrilled to bring my technical skills and enthusiasm to your team.\n\n"
                f"Thank you for considering my application. I look forward to the opportunity to discuss how my background aligns with your needs.\n\n"
                f"Sincerely,\n{name}"
            )

            results.append({
                "index": i,
                "tailored_summary": summary,
                "highlighted_skills": skills[:6],
                "ats_keywords": skills[:8],
                "cover_letter": cover_letter,
                "email_subject": f"Application for {title} at {company} – {name}",
            })
        return results
