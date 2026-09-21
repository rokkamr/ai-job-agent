import os
import json
import logging
import datetime
import asyncio
try:
    import pytz
    def get_timezone(tz_name: str):
        return pytz.timezone(tz_name)
except ImportError:
    from zoneinfo import ZoneInfo
    def get_timezone(tz_name: str):
        return ZoneInfo(tz_name)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database.database import SessionLocal, init_db
from app.database.models import AgentRun, AgentLog
from app.agents.resume_agent import ResumeAgent
from app.agents.job_search_agent import JobSearchAgent
from app.agents.matching_agent import MatchingAgent
from app.agents.resume_tailor_agent import ResumeTailorAgent
from app.agents.application_agent import ApplicationAgent
from app.agents.report_agent import ReportAgent

logger = logging.getLogger(__name__)


def log_to_db(db, run_id: int, level: str, module: str, message: str):
    try:
        log_entry = AgentLog(run_id=run_id, log_level=level, module=module, message=message)
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log to DB: {e}")


async def execute_daily_workflow():
    """
    Executes the end-to-end 12:00 AM Asia/Kolkata daily workflow.
    """
    init_db()
    db = SessionLocal()

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    run_record = AgentRun(
        run_date=today_str,
        started_at=datetime.datetime.utcnow(),
        status="RUNNING"
    )
    db.add(run_record)
    db.commit()

    run_id = run_record.id
    log_to_db(db, run_id, "INFO", "workflow", f"Starting daily job application agent run ID: {run_id}")

    try:
        # Step 1: Resume Ingestion & KB
        log_to_db(db, run_id, "INFO", "resume_agent", "Ingesting master resume & building knowledge base")
        resume_agent = ResumeAgent()
        kb = resume_agent.process_master_resume()

        # Step 2: Job Discovery & Deduplication
        log_to_db(db, run_id, "INFO", "job_search_agent", "Starting job discovery across configured sources")
        search_agent = JobSearchAgent(db, target_roles=kb.get("target_roles"))
        discovery_res = search_agent.discover_jobs()
        run_record.jobs_found = discovery_res["total_found"]
        log_to_db(db, run_id, "INFO", "job_search_agent", f"Discovered {discovery_res['total_found']} jobs ({discovery_res['duplicates']} duplicates)")

        # Step 3: Job Matching & Hard Filtering
        log_to_db(db, run_id, "INFO", "matching_agent", "Evaluating jobs against candidate match matrix")
        min_score = float(os.getenv("MINIMUM_MATCH_SCORE", "80.0"))
        matching_agent = MatchingAgent(db, kb, min_score=min_score)
        match_res = matching_agent.evaluate_discovered_jobs()
        run_record.jobs_matched = match_res["qualified_count"]
        log_to_db(db, run_id, "INFO", "matching_agent", f"Qualified {match_res['qualified_count']} matching jobs")

        # Step 4: Resume Tailoring & Truth Protection
        log_to_db(db, run_id, "INFO", "resume_tailor_agent", "Tailoring truth-protected resumes for qualified jobs")
        tailor_agent = ResumeTailorAgent(db, kb)
        qualified_jobs = match_res["qualified_jobs"]

        tailored_jobs = []
        for job in qualified_jobs[:20]:  # Limit to daily cap
            res = tailor_agent.tailor_resume_for_job(job.id)
            if res.get("status") == "TAILORED":
                tailored_jobs.append(job)

        # Step 5: Application Automation
        log_to_db(db, run_id, "INFO", "application_agent", "Executing browser/email application automation")
        dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        auto_apply = os.getenv("AUTO_APPLY", "false").lower() == "true"
        app_agent = ApplicationAgent(db, kb, dry_run=dry_run, auto_apply=auto_apply)

        submitted_count = 0
        manual_count = 0
        failed_count = 0

        for job in tailored_jobs:
            app_res = await app_agent.apply_to_job(job.id)
            st = app_res.get("status")
            if st in ["SUBMITTED", "DRY_RUN_PASSED"]:
                submitted_count += 1
            elif st == "MANUAL_ACTION_REQUIRED":
                manual_count += 1
            else:
                failed_count += 1

        run_record.applications_submitted = submitted_count
        run_record.manual_review_required = manual_count
        run_record.applications_failed = failed_count
        run_record.completed_at = datetime.datetime.utcnow()
        run_record.status = "COMPLETED"
        db.commit()

        # Step 6: Gmail Report
        log_to_db(db, run_id, "INFO", "report_agent", "Generating and dispatching daily HTML report")
        report_agent = ReportAgent(db)
        report_agent.generate_and_send_daily_report(run_id)

        log_to_db(db, run_id, "INFO", "workflow", f"Daily run completed successfully! Submitted: {submitted_count}, Manual: {manual_count}, Failed: {failed_count}")

    except Exception as e:
        logger.error(f"Fatal error during daily workflow: {e}")
        run_record.status = "FAILED"
        run_record.completed_at = datetime.datetime.utcnow()
        db.commit()
        log_to_db(db, run_id, "ERROR", "workflow", f"Daily workflow failed: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler = AsyncIOScheduler()
    tz = get_timezone("Asia/Kolkata")
    
    # 00:00 AM Asia/Kolkata daily trigger
    trigger = CronTrigger(hour=0, minute=0, timezone=tz)
    scheduler.add_job(execute_daily_workflow, trigger, id="daily_job_agent", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler initialized for 12:00 AM Asia/Kolkata daily trigger.")
    return scheduler
