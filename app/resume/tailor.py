import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

STRICT_RESUME_TAILOR_SYSTEM_PROMPT = """You are a professional ATS resume optimization agent.

Your task is to tailor the candidate's resume to a specific job description.

RULES:
1. Never invent experience.
2. Never invent skills.
3. Never invent certifications.
4. Never invent employment history.
5. Never invent project responsibilities.
6. Never change dates.
7. Never change education information.
8. Never claim a technology was used if the master resume doesn't establish that.
9. You may reorder existing skills.
10. You may improve wording.
11. You may emphasize existing relevant experience.
12. You may incorporate exact keywords from the job description when they accurately describe existing experience.
13. Keep the resume ATS-friendly.
14. Keep the resume truthful.
15. Return the changes made.
"""


class ResumeTailor:
    def __init__(self, candidate_kb: Dict[str, Any]):
        self.kb = candidate_kb
        self.master_skills = candidate_kb.get("skills", [])
        self.master_candidate = candidate_kb.get("candidate", {})

    def tailor_profile_for_job(self, job_title: str, job_desc: str) -> Dict[str, Any]:
        """
        Tailors summary, reorders master skills, and emphasizes relevant project bullets for the given job.
        Strictly preserves truthfulness.
        """
        text_lower = f"{job_title} {job_desc}".lower()

        # 1. Reorder existing master skills to prioritize keywords present in JD
        matched_skills = []
        other_skills = []

        for skill in self.master_skills:
            if skill.lower() in text_lower:
                matched_skills.append(skill)
            else:
                other_skills.append(skill)

        ordered_skills = matched_skills + other_skills

        # 2. Emphasize relevant project bullet points
        base_details = [
            "Executed manual and functional testing of web and mobile healthcare staffing applications.",
            "Performed REST API testing and endpoint validation using Postman.",
            "Logged, tracked, and verified defect resolution lifecycle in Jira.",
            "Executed smoke, regression, and user acceptance testing (UAT) cycles.",
            "Verified cross-browser performance using BrowserStack and mobile builds via TestFlight.",
            "Constructed SQL queries in MySQL for database backend verification and test data setup.",
            "Participated in Agile Scrum ceremonies, sprint planning, and daily standups."
        ]

        # Prioritize bullet points containing matching keywords
        tailored_details = sorted(
            base_details,
            key=lambda d: sum(1 for kw in matched_skills if kw.lower() in d.lower()),
            reverse=True
        )

        # 3. Formulate tailored ATS summary
        primary_skills_str = ", ".join(matched_skills[:4]) if matched_skills else "Manual Testing, API Testing, Postman, and SQL"
        summary = (
            f"Detail-oriented QA Engineer with {self.master_candidate.get('experience_years', 1.4)} years of hands-on experience "
            f"specializing in {primary_skills_str}. Proven track record in executing functional, API, and regression testing "
            f"for web and mobile applications in healthcare and staffing domains. Proficient in Jira defect tracking, Postman API validation, "
            f"and SQL backend verification."
        )

        return {
            "summary": summary,
            "ordered_skills": ordered_skills,
            "matched_keywords": matched_skills,
            "experience": [
                {
                    "title": "QA Engineer / Software Test Engineer",
                    "company": "NurseIO Healthcare Staffing Platform",
                    "details": tailored_details
                }
            ],
            "education": self.kb.get("education", [])
        }
