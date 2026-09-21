import re
import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)


class TruthValidator:
    """
    Mandatory truth protection layer that verifies tailored resume contents against the master Candidate Knowledge Base.
    """
    def __init__(self, candidate_kb: Dict[str, Any]):
        self.kb = candidate_kb
        self.candidate = candidate_kb.get("candidate", {})
        self.master_skills = {s.lower().strip() for s in candidate_kb.get("skills", [])}
        self.master_text = candidate_kb.get("raw_text", "").lower()
        self.master_exp_years = float(self.candidate.get("experience_years", 1.4))

    def validate_tailored_profile(self, tailored_summary: str, tailored_skills: List[str]) -> Tuple[bool, List[str]]:
        """
        Validates that all tailored skills and statements are strictly grounded in master profile.
        Returns (is_valid, list_of_violations).
        """
        violations = []

        # 1. Check for invented skills
        for skill in tailored_skills:
            skill_clean = skill.lower().strip()
            # If skill isn't in master skills list AND not anywhere in raw text
            if skill_clean not in self.master_skills and skill_clean not in self.master_text:
                violations.append(f"Invented skill detected: '{skill}'")

        # 2. Check for experience inflation in summary (e.g., claiming 5+ years)
        exp_claims = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)", tailored_summary.lower())
        for claim in exp_claims:
            val = float(claim)
            if val > self.master_exp_years + 0.5:
                violations.append(f"Inflated experience claim: '{val} years' (Master exp is {self.master_exp_years} years)")

        # 3. Check for fabricated leadership/management claims if not present
        if "lead" in tailored_summary.lower() or "manager" in tailored_summary.lower() or "head of" in tailored_summary.lower():
            if "manager" not in self.master_text and "lead" not in self.master_text:
                violations.append("Fabricated leadership role claim detected in summary")

        is_valid = len(violations) == 0
        return is_valid, violations
