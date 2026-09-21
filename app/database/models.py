import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), index=True)  # LinkedIn, Naukri, Foundit, RemoteOK, Arbeitnow
    external_job_id = Column(String(100), index=True, nullable=True)
    title = Column(String(200), index=True)
    company = Column(String(200), index=True)
    location = Column(String(200))
    url = Column(Text, unique=True, index=True)
    description = Column(Text, nullable=True)
    posted_date = Column(String(50), nullable=True)
    match_score = Column(Float, default=0.0)
    match_details = Column(Text, nullable=True)  # JSON string of breakdown scores
    fingerprint = Column(String(255), index=True)  # normalized company + title + location
    status = Column(String(50), default="DISCOVERED")  # DISCOVERED, EVALUATED, QUALIFIED, TAILORED, APPLIED, FAILED, MANUAL_ACTION_REQUIRED, SKIPPED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    applications = relationship("Application", back_populates="job")
    resume_versions = relationship("ResumeVersion", back_populates="job")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    file_path_docx = Column(Text, nullable=True)
    file_path_pdf = Column(Text, nullable=True)
    skills_added = Column(Text, nullable=True)
    keywords_used = Column(Text, nullable=True)
    truth_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    job = relationship("Job", back_populates="resume_versions")
    applications = relationship("Application", back_populates="resume_version")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    resume_version_id = Column(Integer, ForeignKey("resume_versions.id"), nullable=True)
    applied_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="PENDING")  # SUBMITTED, DRY_RUN_PASSED, FAILED, MANUAL_ACTION_REQUIRED
    application_url = Column(Text, nullable=True)
    confirmation_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    job = relationship("Job", back_populates="applications")
    resume_version = relationship("ResumeVersion", back_populates="applications")
    questions = relationship("ApplicationQuestion", back_populates="application")


class ApplicationQuestion(Base):
    __tablename__ = "application_questions"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    question = Column(Text)
    answer = Column(Text, nullable=True)
    answer_source = Column(String(50))  # PROFILE_PREDEFINED, RESUME_EXTRACTED, MANUAL_REQUIRED
    confidence = Column(Float, default=1.0)

    application = relationship("Application", back_populates="questions")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(String(20), index=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    applications_submitted = Column(Integer, default=0)
    applications_failed = Column(Integer, default=0)
    manual_review_required = Column(Integer, default=0)
    status = Column(String(50), default="RUNNING")  # RUNNING, COMPLETED, FAILED


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    log_level = Column(String(20), default="INFO")
    module = Column(String(100))
    message = Column(Text)
