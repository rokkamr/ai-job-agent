from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base, Job
from app.matching.filters import DuplicateDetector, create_job_fingerprint

def test_duplicate_detection():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    job1 = Job(
        source="LinkedIn",
        title="QA Engineer",
        company="ABC Tech",
        location="Hyderabad",
        url="https://linkedin.com/jobs/view/123",
        fingerprint=create_job_fingerprint("ABC Tech", "QA Engineer", "Hyderabad")
    )
    session.add(job1)
    session.commit()

    detector = DuplicateDetector(session)

    # Test Tier 1 URL match
    assert detector.is_duplicate("https://linkedin.com/jobs/view/123", "Other", "Title") is True

    # Test Tier 2 Fingerprint match
    assert detector.is_duplicate("https://naukri.com/jobs/456", "ABC Tech", "QA Engineer", "Hyderabad") is True

    # Test Unique job
    assert detector.is_duplicate("https://naukri.com/jobs/789", "XYZ Solutions", "Software Tester", "Remote") is False
