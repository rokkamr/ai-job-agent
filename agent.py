"""
agent.py
--------
Main AI Resume Job Finder Agent.
Orchestrates the full pipeline: Parse → Search → Match → Report

Usage:
  python agent.py           — Full run (uses config.yaml)
  python agent.py --test    — Test mode with mock data (no API calls for jobs)
  python agent.py --config path/to/config.yaml
"""

import argparse
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Fix Windows console Unicode encoding
os.environ.setdefault("PYTHONUTF8", "1")

# Setup logging — console (UTF-8) + file
log_file = Path("agent.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"❌ Config file not found: {path}\n"
            f"   Please run: python setup.py"
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main(test_mode: bool = False, config_path: str = "config.yaml"):
    separator = "=" * 65
    log.info(separator)
    log.info(f"  🤖 AI Resume Job Finder — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(separator)

    # ── Load config ──────────────────────────────────────────────
    config = load_config(config_path)

    # ── Step 1: Parse Resume (or use mock in test mode) ────────
    log.info("")
    log.info("STEP 1/4 -- Parsing Resume")
    log.info("-" * 40)

    if test_mode:
        log.info("   TEST MODE -- Using mock profile and job data")
        profile = _mock_profile()
    else:
        from resume_parser import ResumeParser
        parser = ResumeParser(config)
        profile = parser.parse()

    log.info(f"   Candidate: {profile.get('name', 'Unknown')}")
    log.info(f"   Skills: {', '.join(profile.get('primary_skills', profile.get('skills', []))[:7])}")
    log.info(f"   Role: {profile.get('current_title', 'Developer')}")

    # ── Step 2: Search Jobs ──────────────────────────────────────
    log.info("")
    log.info("STEP 2/4 -- Searching for Jobs")
    log.info("-" * 40)

    if test_mode:
        jobs = _mock_jobs()
    else:
        from job_searcher import JobSearcher
        searcher = JobSearcher(config)
        jobs = searcher.search(profile)

    log.info(f"   📊 Total jobs fetched: {len(jobs)}")
    if not jobs:
        log.warning("   ⚠️  No jobs found! Check your API keys or internet connection.")
        log.warning("   Tip: Run with --test to verify the pipeline works.")
        return

    # -- Step 3/6: AI Matching
    log.info("")
    log.info("STEP 3/6 -- AI Job Matching")
    log.info("-" * 40)

    if test_mode:
        matched_jobs = _mock_match(jobs)
    else:
        from job_matcher import JobMatcher
        matcher = JobMatcher(config)
        matched_jobs = matcher.match(profile, jobs)

    if not matched_jobs:
        log.warning("   No jobs exceeded the minimum match score.")
        log.warning(f"   Tip: Lower 'min_match_score' in config.yaml (currently "
                    f"{config['job_preferences'].get('min_match_score', 40)})")
        return

    log.info(f"   Top match: {matched_jobs[0]['title']} @ {matched_jobs[0]['company']} "
             f"({matched_jobs[0]['match_score']}%)")

    # -- Step 4/6: Resume Optimization
    log.info("")
    log.info("STEP 4/6 -- Optimizing Resume for Each Job")
    log.info("-" * 40)

    if test_mode:
        optimizations = _mock_optimizations(matched_jobs, profile)
    else:
        from resume_optimizer import ResumeOptimizer
        optimizer = ResumeOptimizer(config)
        optimizations = optimizer.optimize_all(profile, matched_jobs)

    log.info(f"   Resume tailored for {len(optimizations)} jobs")

    # -- Step 5/6: Auto-Apply
    log.info("")
    log.info("STEP 5/6 -- Auto-Applying to Jobs")
    log.info("-" * 40)

    from auto_applier import AutoApplier
    applier = AutoApplier(config)
    apply_results = applier.apply_all(profile, matched_jobs, optimizations)

    applied = sum(1 for r in apply_results if "applied_" in r.get("status", ""))
    already = sum(1 for r in apply_results if r.get("status") == "skipped_already_applied")
    manual  = sum(1 for r in apply_results if r.get("status") == "manual_required")
    log.info(f"   Application status: {applied} applied | {already} already applied | {manual} manual required")

    # -- Step 6/6: Generate Report
    log.info("")
    log.info("STEP 6/6 -- Generating Report")
    log.info("-" * 40)
    from reporter import Reporter
    reporter = Reporter(config)
    report_path = reporter.report(profile, matched_jobs, apply_results=apply_results)

    log.info("")
    log.info(separator)
    log.info(f"  Done! {len(matched_jobs)} jobs matched, {applied} applied automatically.")
    log.info(f"  Report: {report_path}")
    log.info(separator)


def _mock_profile() -> dict:
    """Mock candidate profile for test mode."""
    return {
        "name": "Demo Candidate",
        "email": "demo@example.com",
        "current_title": "Software Developer",
        "skills": ["Python", "React", "SQL", "REST APIs", "Git", "Django"],
        "primary_skills": ["Python", "React", "SQL", "REST APIs", "Django"],
        "experience_years": 1.4,
        "experience_level": "entry",
        "job_titles": ["Software Developer", "Full Stack Developer"],
        "summary": "A passionate entry-level developer with 1.5 years of experience.",
        "education": ["B.Tech Computer Science"],
        "preferred_location": "Hyderabad",
        "preferred_job_types": ["remote", "hybrid"],
    }


def _mock_match(jobs: list[dict]) -> list[dict]:
    """Add pre-scored match data to mock jobs for test mode."""
    scores = [88, 75, 62]
    results = []
    for i, job in enumerate(jobs):
        results.append({
            **job,
            "match_score": scores[i] if i < len(scores) else 50,
            "match_level": "Strong Match" if i == 0 else "Good Match",
            "match_reasons": [
                "Python skills directly match the job requirements",
                "Experience level aligns with junior/entry requirements",
            ],
            "skill_gaps": ["Docker"] if i == 0 else ["AWS", "Redis"],
            "cover_letter_snippet": (
                f"I am excited to apply for the {job['title']} role at {job['company']}. "
                f"My background in Python and web development makes me a strong fit "
                f"for this opportunity."
            ),
            "why_apply": "Strong skill alignment with growth potential.",
        })
    return results


def _mock_optimizations(jobs: list[dict], profile: dict) -> list[dict]:
    """Mock resume optimizations for test mode."""
    return [
        {
            "index": i,
            "tailored_summary": f"Entry-level developer with Python and React skills, eager to contribute to {job.get('company', 'your team')}.",
            "highlighted_skills": ["Python", "React", "SQL", "REST APIs", "Django"],
            "ats_keywords": ["Python", "Django", "REST API", "PostgreSQL", "Git", "Agile"],
            "cover_letter": (
                f"Dear Hiring Team at {job.get('company', 'your company')},\n\n"
                f"I am excited to apply for the {job.get('title', 'role')} position. "
                f"With 1.5 years of hands-on experience in Python and full-stack development, "
                f"I am confident in my ability to contribute effectively to your team.\n\n"
                f"My background includes building REST APIs with Django, working with PostgreSQL, "
                f"and collaborating in agile environments — all directly relevant to this role.\n\n"
                f"I would love the opportunity to discuss how I can add value to {job.get('company', 'your organisation')}. "
                f"Thank you for your consideration.\n\nBest regards,\n{profile.get('name', 'Applicant')}"
            ),
            "email_subject": f"Application for {job.get('title', 'the role')} at {job.get('company', '')} – {profile.get('name', '')}",
        }
        for i, job in enumerate(jobs)
    ]

def _mock_jobs() -> list[dict]:
    """Mock job data for testing without API calls."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "id": "mock-1",
            "title": "Python Backend Developer",
            "company": "CloudTech Solutions",
            "location": "Remote (India)",
            "description": (
                "We are looking for a Python Backend Developer with 1-2 years of experience. "
                "Requirements: Django or FastAPI, REST APIs, PostgreSQL, Git. "
                "Nice to have: Docker, AWS, Redis. We offer flexible remote work, "
                "competitive salary, and great growth opportunities."
            ),
            "url": "https://example.com/apply/python-backend",
            "salary": "₹6–10 LPA",
            "posted_date": today,
            "job_type": "remote",
            "source": "Test",
            "tags": ["python", "django", "backend"],
        },
        {
            "id": "mock-2",
            "title": "Full Stack Developer",
            "company": "FinEdge Startup",
            "location": "Hyderabad (Hybrid)",
            "description": (
                "Join our fast-growing fintech startup as a Full Stack Developer. "
                "You'll build React frontends and Node.js/Python backends. "
                "1-3 years experience preferred. Tech: React, Python/Flask, MongoDB, REST APIs. "
                "Hybrid work policy with Hyderabad office."
            ),
            "url": "https://example.com/apply/fullstack",
            "salary": "₹7–11 LPA",
            "posted_date": today,
            "job_type": "hybrid",
            "source": "Test",
            "tags": ["react", "python", "full-stack"],
        },
        {
            "id": "mock-3",
            "title": "Junior Data Engineer",
            "company": "DataWave Analytics",
            "location": "Remote (Worldwide)",
            "description": (
                "DataWave is hiring a Junior Data Engineer to help build our data pipelines. "
                "Skills: Python, SQL, basic ETL concepts, data cleaning. "
                "Bonus: PySpark, Airflow, dbt. This is a fully remote role with async culture."
            ),
            "url": "https://example.com/apply/data-engineer",
            "salary": "$20,000–$35,000/year",
            "posted_date": today,
            "job_type": "remote",
            "source": "Test",
            "tags": ["python", "sql", "data"],
        },
    ]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="AI Resume Job Finder — Finds jobs matching your resume daily"
    )
    ap.add_argument(
        "--test", action="store_true",
        help="Run in test mode (mock jobs, no API calls for searching)"
    )
    ap.add_argument(
        "--config", default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    args = ap.parse_args()

    try:
        main(test_mode=args.test, config_path=args.config)
    except KeyboardInterrupt:
        log.info("\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        log.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
