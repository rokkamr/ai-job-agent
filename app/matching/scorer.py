import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class JobMatchScorer:
    def __init__(self, candidate_kb: Dict[str, Any]):
        self.candidate = candidate_kb.get("candidate", {})
        self.skills = [s.lower() for s in candidate_kb.get("skills", [])]
        self.domains = [d.lower() for d in candidate_kb.get("domains", [])]
        self.cand_exp = float(self.candidate.get("experience_years", 1.4))

    def evaluate_job(self, job_title: str, job_desc: str, location: str) -> Dict[str, Any]:
        """
        Evaluates job description against candidate profile to generate breakdown scores.
        """
        text = f"{job_title} {job_desc}".lower()

        # 1. Skill Match & Title Relevance
        matched_skills = [s for s in self.skills if s in text]
        
        is_qa_title = any(role.lower() in job_title.lower() for role in ["qa", "test", "quality assurance", "sdett", "automation"])
        
        if matched_skills:
            skill_score = min(100.0, 70.0 + (len(matched_skills) * 7.5))
        elif is_qa_title:
            skill_score = 75.0
        else:
            skill_score = 40.0

        # 2. Experience Match
        exp_matches = re.findall(r"(\d+)\+?\s*(?:-\s*\d+)?\s*(?:years?|yrs?)", text)
        req_exp = float(exp_matches[0]) if exp_matches else 1.5
        
        if req_exp <= self.cand_exp:
            exp_score = 100.0
        elif req_exp <= self.cand_exp + 1.5:
            exp_score = 85.0
        elif req_exp <= 5.0:
            exp_score = 60.0
        else:
            exp_score = 30.0

        # 3. Domain Match
        matched_domains = [d for d in self.domains if d in text]
        domain_score = 100.0 if matched_domains else 80.0

        # 4. Location Match
        loc_text = location.lower()
        if not loc_text or "remote" in loc_text or "hybrid" in loc_text or "hyderabad" in loc_text or "india" in loc_text or "kochi" in loc_text:
            location_score = 100.0
        else:
            location_score = 70.0

        # Overall Weighted Score
        overall_score = round(
            (skill_score * 0.45) + (exp_score * 0.25) + (domain_score * 0.15) + (location_score * 0.15),
            1
        )

        return {
            "overall_score": overall_score,
            "skill_match": round(skill_score, 1),
            "exp_match": round(exp_score, 1),
            "domain_match": round(domain_score, 1),
            "location_match": round(location_score, 1),
            "matched_skills": [s.title() for s in matched_skills],
            "req_exp_estimated": req_exp
        }
