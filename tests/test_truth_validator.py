from app.agents.truth_validator import TruthValidator

def test_truth_validator_valid():
    kb = {
        "candidate": {"name": "Rokkam Raja", "experience_years": 1.4},
        "skills": ["Manual Testing", "API Testing", "Postman", "SQL", "Jira", "Selenium", "Java"],
        "raw_text": "Experienced QA engineer with 1.4 years of experience in manual testing, postman, sql, selenium."
    }
    validator = TruthValidator(kb)
    is_valid, violations = validator.validate_tailored_profile(
        tailored_summary="QA engineer with 1.4 years experience in manual testing.",
        tailored_skills=["Manual Testing", "SQL"]
    )
    assert is_valid is True
    assert len(violations) == 0

def test_truth_validator_rejects_hallucination():
    kb = {
        "candidate": {"name": "Rokkam Raja", "experience_years": 1.4},
        "skills": ["Manual Testing", "API Testing", "Postman", "SQL"],
        "raw_text": "QA engineer manual testing."
    }
    validator = TruthValidator(kb)
    is_valid, violations = validator.validate_tailored_profile(
        tailored_summary="Lead QA Manager with 8 years experience in Kubernetes and AWS.",
        tailored_skills=["Kubernetes", "AWS"]
    )
    assert is_valid is False
    assert len(violations) > 0
