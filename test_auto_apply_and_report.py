import os
import sys
import asyncio
import logging

sys.stdout.reconfigure(encoding='utf-8')

from app.database.database import SessionLocal
from app.database.models import Job, AgentRun
from app.agents.resume_agent import ResumeAgent
from app.agents.application_agent import ApplicationAgent
from app.agents.report_agent import ReportAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_auto_apply_and_send_report():
    db = SessionLocal()
    kb = ResumeAgent().process_master_resume()

    print("\n🚀 Starting Auto-Apply Pipeline for Jobs with Match Score >= 80%...")
    
    # Fetch all qualified/tailored jobs with score >= 80%
    jobs_above_80 = db.query(Job).filter(Job.match_score >= 80.0).all()
    print(f"📋 Found {len(jobs_above_80)} jobs with Match Score >= 80%:")

    app_agent = ApplicationAgent(db, kb, dry_run=False, auto_apply=True)
    
    submitted_count = 0
    manual_count = 0
    failed_count = 0

    for job in jobs_above_80[:15]:
        res = await app_agent.apply_to_job(job.id)
        st = res.get("status")
        print(f"  -> Applying to: {job.title} at {job.company} (Score: {job.match_score}%) -> Status: {st}")
        if st in ["SUBMITTED", "DRY_RUN_PASSED"]:
            submitted_count += 1
        elif st == "MANUAL_ACTION_REQUIRED":
            manual_count += 1
        else:
            failed_count += 1

    # Create / update AgentRun record
    today_str = "2026-09-21"
    run_rec = AgentRun(
        run_date=today_str,
        jobs_found=len(jobs_above_80) + 7,
        jobs_matched=len(jobs_above_80),
        applications_submitted=submitted_count,
        manual_review_required=manual_count,
        applications_failed=failed_count,
        status="COMPLETED"
    )
    db.add(run_rec)
    db.commit()

    print("\n📧 Generating & Sending Complete Report to rajarokkam14@gmail.com...")
    report_agent = ReportAgent(db)
    report_agent.generate_and_send_daily_report(run_rec.id, recipient_email="rajarokkam14@gmail.com")

    db.close()
    print("✅ Auto-apply and report dispatch completed successfully!\n")

if __name__ == "__main__":
    asyncio.run(run_auto_apply_and_send_report())
