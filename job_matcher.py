"""
job_matcher.py
--------------
Uses Google Gemini AI to score ALL job listings in a SINGLE API call
(batch scoring), to stay within free-tier rate limits (20 req/day).
Total API calls: 1 for resume parsing + 1 for batch job scoring = 2 total.
"""

import json
import logging
import os

from google import genai

log = logging.getLogger(__name__)


class JobMatcher:
    def __init__(self, config: dict):
        self.config = config
        self.max_report = config["job_preferences"].get("max_jobs_to_report", 15)
        self.min_score = config["job_preferences"].get("min_match_score", 40)
        model_name = config.get("gemini", {}).get("model", "gemini-3.6-flash")
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or config.get("gemini", {}).get("api_key", "")
        )
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def match(self, profile: dict, jobs: list[dict]) -> list[dict]:
        """Score all jobs in ONE Gemini batch call and return top N matches."""
        if not jobs:
            log.warning("No jobs to match against!")
            return []

        log.info(f"   Scoring {len(jobs)} jobs in a single Gemini batch call...")

        # Batch in chunks of 30 to keep prompt size reasonable
        chunk_size = 30
        all_scored = []
        chunks = [jobs[i:i+chunk_size] for i in range(0, len(jobs), chunk_size)]

        for idx, chunk in enumerate(chunks):
            log.info(f"   Batch {idx+1}/{len(chunks)}: scoring {len(chunk)} jobs...")
            try:
                scored_chunk = self._batch_score(profile, chunk)
                all_scored.extend(scored_chunk)
            except Exception as e:
                log.warning(f"   Batch {idx+1} failed: {e}")
                # Fall back to adding unscored jobs with 0 score
                for job in chunk:
                    all_scored.append({**job, "match_score": 0, "match_level": "Unknown",
                                        "match_reasons": [], "skill_gaps": [],
                                        "cover_letter_snippet": "", "why_apply": ""})

        # Filter and sort
        matched = [j for j in all_scored if j.get("match_score", 0) >= self.min_score]
        matched.sort(key=lambda j: j["match_score"], reverse=True)
        top = matched[:self.max_report]

        log.info(f"   {len(top)} jobs passed score threshold ({self.min_score}%)")
        if top:
            log.info(f"   Top match: {top[0]['title']} @ {top[0]['company']} ({top[0]['match_score']}%)")
        return top

    def _batch_score(self, profile: dict, jobs: list[dict]) -> list[dict]:
        """Score a batch of jobs in a single Gemini API call."""
        profile_summary = {
            "name": profile.get("name", ""),
            "skills": profile.get("skills", []),
            "primary_skills": profile.get("primary_skills", []),
            "experience_years": profile.get("experience_years", 0),
            "experience_level": profile.get("experience_level", "entry"),
            "job_titles": profile.get("job_titles", []),
            "summary": profile.get("summary", ""),
            "education": profile.get("education", []),
            "preferred_location": profile.get("preferred_location", "Hyderabad"),
            "preferred_job_types": profile.get("preferred_job_types", ["remote", "hybrid"]),
        }

        # Build compact job list for the prompt
        job_list = []
        for i, job in enumerate(jobs):
            job_list.append({
                "index": i,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "type": job.get("job_type", ""),
                "description": (job.get("description") or "")[:800],  # truncate to save tokens
            })

        prompt = f"""
You are an expert technical recruiter evaluating job listings for a candidate.

CANDIDATE PROFILE:
{json.dumps(profile_summary, indent=2)}

JOB LISTINGS TO EVALUATE:
{json.dumps(job_list, indent=2)}

Score EACH job and return a JSON ARRAY (no markdown, raw JSON only).
Each element must correspond to the same index in the input list.

Return format:
[
  {{
    "index": 0,
    "match_score": 78,
    "match_level": "Good Match",
    "match_reasons": ["Reason 1", "Reason 2"],
    "skill_gaps": ["Gap 1"],
    "cover_letter_snippet": "I am excited to apply for the [title] role at [company]. [2-3 personalized sentences].",
    "why_apply": "One compelling reason to apply."
  }},
  ...
]

Scoring rules:
- match_score: 0-100 (be honest; 0 = completely unrelated, 100 = perfect)
- match_level: "No Match" | "Weak Match" | "Fair Match" | "Good Match" | "Strong Match" | "Excellent Match"
- Heavily penalize jobs that have NO relation to the candidate's skills/domain
- Heavily penalize jobs requiring 5+ years experience for an entry-level candidate
- Boost score for: remote/hybrid work, matching tech stack, appropriate experience level
- skill_gaps: max 3 items, empty list if no gaps
- cover_letter_snippet: MUST mention the company name and role specifically
- Return EXACTLY {len(jobs)} objects, one per input job, in the same order
"""

        models_to_try = [self.model_name, "gemini-3.6-flash"]
        models_to_try = list(dict.fromkeys(models_to_try))

        scores = None
        for m in models_to_try:
            try:
                log.info(f"   Calling Gemini ({m}) to score batch of {len(jobs)} jobs...")
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
                scores = json.loads(raw)
                break
            except Exception as e:
                log.warning(f"   Model {m} failed for job matching ({e})")
                import time
                time.sleep(2)

        if not scores:
            log.warning("   All Gemini models failed/rate-limited for job matching. Using keyword heuristic matcher...")
            return self._heuristic_batch_score(profile, jobs)

        # Merge scoring data back into job dicts
        result = []
        score_map = {s["index"]: s for s in scores}
        for i, job in enumerate(jobs):
            s = score_map.get(i, {})
            result.append({
                **job,
                "match_score": int(s.get("match_score", 0)),
                "match_level": s.get("match_level", "Unknown"),
                "match_reasons": s.get("match_reasons", []),
                "skill_gaps": s.get("skill_gaps", []),
                "cover_letter_snippet": s.get("cover_letter_snippet", ""),
                "why_apply": s.get("why_apply", ""),
            })
        return result

    def _heuristic_batch_score(self, profile: dict, jobs: list[dict]) -> list[dict]:
        """Fallback rule-based matcher when Gemini API is quota exhausted."""
        skills = [s.lower() for s in profile.get("skills", [])]
        result = []
        for job in jobs:
            text = f"{job.get('title', '')} {job.get('description', '')}".lower()
            matched_skills = [s.capitalize() for s in skills if s in text]
            score = min(95, 40 + len(matched_skills) * 10)
            if any(term in text for term in ["senior", "lead", "architect", "5+ years", "8+ years"]):
                score = max(20, score - 35)

            title = job.get("title", "Role")
            company = job.get("company", "Company")

            result.append({
                **job,
                "match_score": score,
                "match_level": "Good Match" if score >= 70 else "Fair Match",
                "match_reasons": [f"Matches skills: {', '.join(matched_skills[:4])}"] if matched_skills else ["Role fits background"],
                "skill_gaps": [],
                "cover_letter_snippet": f"I am excited to apply for the {title} position at {company}. My background aligns well with your requirements.",
                "why_apply": "Relevant role matching candidate profile skills.",
            })
        return result
