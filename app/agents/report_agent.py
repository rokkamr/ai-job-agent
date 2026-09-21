import datetime
import logging
from sqlalchemy.orm import Session

from app.database.models import AgentRun, Job, Application
from app.email.gmail import GmailClient

logger = logging.getLogger(__name__)


class ReportAgent:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.gmail = GmailClient()

    def generate_and_send_daily_report(self, run_id: int, recipient_email: str = "rajarokkam14@gmail.com") -> bool:
        run = self.db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            logger.error(f"AgentRun {run_id} not found")
            return False

        today_str = datetime.datetime.now().strftime("%d %b %Y")
        subject = f"Daily Job Application Report - {today_str}"

        # Fetch applications created today
        today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
        today_jobs = self.db.query(Job).filter(Job.created_at >= today_start).all()

        applications_submitted = []
        manual_review_items = []
        failed_items = []

        for job in today_jobs:
            if job.status in ["APPLIED", "SUBMITTED"]:
                applications_submitted.append(job)
            elif job.status == "MANUAL_ACTION_REQUIRED":
                manual_review_items.append(job)
            elif job.status == "FAILED":
                failed_items.append(job)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f9fafb; color: #111827; margin: 0; padding: 20px; }}
            .card {{ background: #ffffff; padding: 24px; border-radius: 8px; border: 1px solid #e5e7eb; max-width: 680px; margin: 0 auto; }}
            h2 {{ color: #1f2937; margin-top: 0; }}
            .stat-box {{ display: flex; justify-content: space-between; background: #f3f4f6; padding: 16px; border-radius: 6px; margin-bottom: 20px; }}
            .stat-item {{ text-align: center; }}
            .stat-val {{ font-size: 20px; font-weight: bold; color: #2563eb; }}
            .stat-lbl {{ font-size: 12px; color: #6b7280; }}
            .job-item {{ padding: 12px; border-bottom: 1px solid #f3f4f6; }}
            .badge-applied {{ background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .badge-review {{ background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .badge-failed {{ background: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
          </style>
        </head>
        <body>
          <div class="card">
            <h2>🤖 Daily Job Application Report</h2>
            <p>Hello Raja, your AI Job Application Agent completed today's run on <strong>{today_str}</strong>.</p>
            
            <div class="stat-box">
              <div class="stat-item"><div class="stat-val">{run.jobs_found}</div><div class="stat-lbl">Discovered</div></div>
              <div class="stat-item"><div class="stat-val">{run.jobs_matched}</div><div class="stat-lbl">Matched</div></div>
              <div class="stat-item"><div class="stat-val">{run.applications_submitted}</div><div class="stat-lbl">Submitted</div></div>
              <div class="stat-item"><div class="stat-val">{run.manual_review_required}</div><div class="stat-lbl">Manual Review</div></div>
              <div class="stat-item"><div class="stat-val">{run.applications_failed}</div><div class="stat-lbl">Failed</div></div>
            </div>

            <h3>Submitted Applications</h3>
        """

        if not applications_submitted:
            html_content += "<p><em>No automated submissions executed today.</em></p>"
        else:
            for job in applications_submitted:
                html_content += f"""
                <div class="job-item">
                  <strong>{job.title}</strong> at <strong>{job.company}</strong> ({job.location})<br/>
                  <small>Source: {job.source} | Match Score: {job.match_score}%</small>
                  <span class="badge-applied" style="float:right;">Applied</span>
                </div>
                """

        html_content += "<h3>Manual Action Required</h3>"
        if not manual_review_items:
            html_content += "<p><em>No items requiring manual review.</em></p>"
        else:
            for job in manual_review_items:
                html_content += f"""
                <div class="job-item">
                  <strong>{job.title}</strong> at <strong>{job.company}</strong><br/>
                  <small>URL: <a href="{job.url}">{job.url}</a></small>
                  <span class="badge-review" style="float:right;">Review Needed</span>
                </div>
                """

        html_content += """
            <hr style="margin-top:24px; border:none; border-top:1px solid #e5e7eb;"/>
            <p style="font-size:12px; color:#9ca3af; text-align:center;">Autonomous AI Job Application System — 12:00 AM IST Schedule</p>
          </div>
        </body>
        </html>
        """

        return self.gmail.send_html_email(recipient_email, subject, html_content)
