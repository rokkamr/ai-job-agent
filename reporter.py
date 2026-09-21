"""
reporter.py
-----------
Generates a beautiful HTML report of matched jobs and sends it via email.
Also saves the report as an HTML file in the output directory.
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

log = logging.getLogger(__name__)


def _score_color(score: int) -> str:
    if score >= 75:
        return "#22c55e"   # green
    elif score >= 55:
        return "#f59e0b"   # amber
    elif score >= 40:
        return "#f97316"   # orange
    else:
        return "#ef4444"   # red


def _score_gradient(score: int) -> str:
    if score >= 75:
        return "linear-gradient(90deg, #22c55e, #16a34a)"
    elif score >= 55:
        return "linear-gradient(90deg, #f59e0b, #d97706)"
    else:
        return "linear-gradient(90deg, #f97316, #ea580c)"


def _badge_color(job_type: str) -> tuple[str, str]:
    """Return (bg_color, text_color) for job type badge."""
    t = job_type.lower()
    if "remote" in t:
        return "#0ea5e9", "#fff"
    elif "hybrid" in t:
        return "#8b5cf6", "#fff"
    else:
        return "#64748b", "#fff"


def _job_card_html(job: dict, rank: int) -> str:
    score = job.get("match_score", 0)
    color = _score_color(score)
    gradient = _score_gradient(score)
    badge_bg, badge_fg = _badge_color(job.get("job_type", ""))

    reasons_html = "".join(
        f'<li>✅ {r}</li>' for r in job.get("match_reasons", [])
    )
    gaps_html = "".join(
        f'<li>📌 {g}</li>' for g in job.get("skill_gaps", [])
    )
    gaps_section = (
        f'<div class="gaps"><strong>Skill Gaps:</strong><ul>{gaps_html}</ul></div>'
        if job.get("skill_gaps") else ""
    )
    tags_html = "".join(
        f'<span class="tag">{t}</span>'
        for t in (job.get("tags") or [])[:6]
        if t
    )
    salary_html = (
        f'<span class="salary">💰 {job["salary"]}</span>' if job.get("salary") else ""
    )
    cover_letter = job.get("cover_letter_snippet", "")
    cover_section = (
        f'''
        <div class="cover-letter">
          <strong>✍️ Cover Letter Starter:</strong>
          <p><em>"{cover_letter}"</em></p>
        </div>
        '''
        if cover_letter else ""
    )

    return f"""
    <div class="job-card">
      <div class="job-card-header">
        <div class="rank">#{rank}</div>
        <div class="job-info">
          <div class="job-title">{job.get('title', 'Unknown Title')}</div>
          <div class="company">🏢 {job.get('company', 'Unknown')}
            <span class="location">📍 {job.get('location', '')}</span>
          </div>
          <div class="meta">
            <span class="badge" style="background:{badge_bg};color:{badge_fg}">
              {job.get('job_type', 'Unknown').upper()}
            </span>
            <span class="source-badge">🔗 {job.get('source', '')}</span>
            {salary_html}
          </div>
        </div>
        <div class="score-circle" style="border-color:{color}; color:{color}">
          <span class="score-number">{score}</span>
          <span class="score-pct">%</span>
          <span class="score-label">{job.get('match_level', '')}</span>
        </div>
      </div>

      <div class="score-bar-container">
        <div class="score-bar" style="width:{score}%; background:{gradient}"></div>
      </div>

      <div class="match-reasons">
        <strong>Why You're a Match:</strong>
        <ul>{reasons_html}</ul>
      </div>

      {gaps_section}
      {cover_section}

      <div class="card-footer">
        <a class="apply-btn" href="{job.get('url', '#')}" target="_blank">
          🚀 Apply Now
        </a>
        <span class="posted-date">📅 Posted: {job.get('posted_date', 'Today')}</span>
      </div>
    </div>
    """


def _apply_card_html(res: dict) -> str:
    status = res.get("status", "")
    if status == "applied_email":
        badge_bg, badge_txt = "#22c55e", "EMAIL SUBMITTED ✅"
    elif status == "applied_browser" or status == "submitted":
        badge_bg, badge_txt = "#0ea5e9", "FORM SUBMITTED 🤖"
    elif status == "skipped_already_applied":
        badge_bg, badge_txt = "#64748b", "PREVIOUSLY TRACKED ⏩"
    else:
        badge_bg, badge_txt = "#8b5cf6", "DIRECT APPLY LINK 🔗"

    return f"""
    <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:14px 18px; margin-bottom:10px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
      <div>
        <strong style="color:#f1f5f9; font-size:0.95rem;">{res.get('job_title', 'Job')}</strong>
        <span style="color:#94a3b8; font-size:0.85rem; margin-left:8px;">🏢 {res.get('company', '')}</span>
        <p style="color:#64748b; font-size:0.78rem; margin-top:4px;">{res.get('detail', '')}</p>
      </div>
      <div style="display:flex; align-items:center; gap:10px;">
        <span style="background:{badge_bg}; color:#fff; font-size:0.72rem; font-weight:700; padding:4px 12px; border-radius:20px;">{badge_txt}</span>
        <a href="{res.get('url', '#')}" target="_blank" style="color:#8b5cf6; font-size:0.82rem; text-decoration:none;">View Job →</a>
      </div>
    </div>
    """


def build_html_report(profile: dict, jobs: list[dict], run_date: str, apply_results: list[dict] = None) -> str:
    """Build the full HTML report as a string."""
    total = len(jobs)
    top_score = jobs[0]["match_score"] if jobs else 0
    avg_score = int(sum(j["match_score"] for j in jobs) / total) if total else 0

    job_cards = "".join(_job_card_html(job, i + 1) for i, job in enumerate(jobs))

    if not jobs:
        job_cards = '<p style="text-align:center;color:#94a3b8;padding:2rem;">No matching jobs found today. Try again tomorrow!</p>'

    apply_section = ""
    if apply_results:
        cards_html = "".join(_apply_card_html(r) for r in apply_results)
        applied_cnt = sum(1 for r in apply_results if "applied_" in r.get("status", ""))
        apply_section = f"""
        <div class="section-title">🚀 Auto-Application Status ({applied_cnt}/{len(apply_results)} Applied)</div>
        <div style="margin-bottom:28px;">
          {cards_html}
        </div>
        """

    candidate_name = profile.get("name", "Candidate")
    skills_preview = ", ".join(profile.get("primary_skills", profile.get("skills", []))[:6])
    role = profile.get("current_title", profile.get("job_titles", ["Developer"])[0])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Daily Job Matches — {run_date}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #0a0f1e;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 0;
    }}

    /* ---- HEADER ---- */
    .header {{
      background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4c1d95 100%);
      padding: 48px 32px;
      text-align: center;
      border-bottom: 1px solid rgba(139, 92, 246, 0.3);
      position: relative;
      overflow: hidden;
    }}
    .header::before {{
      content: '';
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: radial-gradient(circle at 60% 40%, rgba(139,92,246,0.15) 0%, transparent 60%);
    }}
    .header-emoji {{ font-size: 3rem; display: block; margin-bottom: 12px; }}
    .header h1 {{
      font-size: 2.2rem;
      font-weight: 800;
      background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 8px;
    }}
    .header-sub {{
      color: #94a3b8;
      font-size: 0.95rem;
      margin-bottom: 24px;
    }}

    /* ---- STATS ---- */
    .stats-bar {{
      display: flex;
      justify-content: center;
      gap: 32px;
      flex-wrap: wrap;
      margin-top: 24px;
    }}
    .stat {{
      text-align: center;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      padding: 16px 28px;
      backdrop-filter: blur(10px);
    }}
    .stat-value {{
      font-size: 2rem;
      font-weight: 800;
      color: #a78bfa;
    }}
    .stat-label {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}

    /* ---- PROFILE BANNER ---- */
    .profile-banner {{
      background: linear-gradient(90deg, rgba(14,165,233,0.1), rgba(139,92,246,0.1));
      border: 1px solid rgba(14,165,233,0.2);
      border-radius: 16px;
      margin: 32px auto;
      max-width: 900px;
      padding: 20px 28px;
      display: flex;
      align-items: center;
      gap: 20px;
    }}
    .profile-avatar {{
      width: 56px;
      height: 56px;
      background: linear-gradient(135deg, #a78bfa, #60a5fa);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      font-weight: 800;
      color: white;
      flex-shrink: 0;
    }}
    .profile-info h3 {{ font-size: 1.1rem; font-weight: 700; color: #e2e8f0; }}
    .profile-info p {{ font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }}

    /* ---- MAIN CONTENT ---- */
    .container {{ max-width: 900px; margin: 0 auto; padding: 0 24px 60px; }}

    .section-title {{
      font-size: 1.2rem;
      font-weight: 700;
      color: #c4b5fd;
      margin: 32px 0 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .section-title::after {{
      content: '';
      flex: 1;
      height: 1px;
      background: rgba(196,181,253,0.2);
    }}

    /* ---- JOB CARDS ---- */
    .job-card {{
      background: linear-gradient(145deg, #111827, #1a2234);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 20px;
      padding: 28px;
      margin-bottom: 24px;
      transition: transform 0.2s, border-color 0.2s;
      position: relative;
      overflow: hidden;
    }}
    .job-card::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
      background: linear-gradient(90deg, #8b5cf6, #06b6d4);
    }}
    .job-card:hover {{
      transform: translateY(-2px);
      border-color: rgba(139,92,246,0.3);
    }}

    .job-card-header {{
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .rank {{
      font-size: 1.4rem;
      font-weight: 800;
      color: #4b5563;
      min-width: 36px;
      padding-top: 4px;
    }}
    .job-info {{ flex: 1; }}
    .job-title {{
      font-size: 1.2rem;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 6px;
    }}
    .company {{
      color: #94a3b8;
      font-size: 0.9rem;
      margin-bottom: 10px;
    }}
    .location {{ margin-left: 12px; color: #64748b; }}

    .meta {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .badge {{
      font-size: 0.7rem;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 20px;
      letter-spacing: 0.05em;
    }}
    .source-badge {{
      font-size: 0.78rem;
      color: #64748b;
      background: rgba(255,255,255,0.05);
      padding: 3px 10px;
      border-radius: 20px;
    }}
    .salary {{ font-size: 0.85rem; color: #34d399; font-weight: 600; }}

    /* ---- SCORE CIRCLE ---- */
    .score-circle {{
      width: 90px;
      height: 90px;
      border-radius: 50%;
      border: 3px solid;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      background: rgba(0,0,0,0.3);
    }}
    .score-number {{ font-size: 1.6rem; font-weight: 800; line-height: 1; }}
    .score-pct {{ font-size: 0.75rem; font-weight: 600; opacity: 0.7; }}
    .score-label {{ font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.7; margin-top: 2px; text-align: center; }}

    /* ---- SCORE BAR ---- */
    .score-bar-container {{
      background: rgba(255,255,255,0.06);
      height: 6px;
      border-radius: 3px;
      margin-bottom: 20px;
      overflow: hidden;
    }}
    .score-bar {{
      height: 100%;
      border-radius: 3px;
      transition: width 0.6s ease;
    }}

    /* ---- REASONS / GAPS ---- */
    .match-reasons, .gaps {{
      font-size: 0.88rem;
      margin-bottom: 14px;
    }}
    .match-reasons strong, .gaps strong {{
      color: #c4b5fd;
      display: block;
      margin-bottom: 8px;
    }}
    .match-reasons ul, .gaps ul {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .match-reasons li {{ color: #cbd5e1; }}
    .gaps li {{ color: #fbbf24; }}

    /* ---- COVER LETTER ---- */
    .cover-letter {{
      background: rgba(139,92,246,0.08);
      border: 1px solid rgba(139,92,246,0.2);
      border-radius: 12px;
      padding: 14px 18px;
      margin-bottom: 14px;
      font-size: 0.88rem;
    }}
    .cover-letter strong {{ color: #c4b5fd; display: block; margin-bottom: 8px; }}
    .cover-letter p {{ color: #94a3b8; line-height: 1.6; font-style: italic; }}

    /* ---- TAGS ---- */
    .tag {{
      display: inline-block;
      font-size: 0.72rem;
      padding: 3px 10px;
      border-radius: 20px;
      background: rgba(99,102,241,0.15);
      color: #a5b4fc;
      margin: 3px 3px 3px 0;
    }}

    /* ---- CARD FOOTER ---- */
    .card-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.06);
    }}
    .apply-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: linear-gradient(90deg, #7c3aed, #4f46e5);
      color: white;
      text-decoration: none;
      padding: 10px 24px;
      border-radius: 30px;
      font-size: 0.88rem;
      font-weight: 600;
      transition: transform 0.15s, opacity 0.15s;
    }}
    .apply-btn:hover {{ transform: translateY(-1px); opacity: 0.9; }}
    .posted-date {{ font-size: 0.78rem; color: #4b5563; }}

    /* ---- FOOTER ---- */
    .page-footer {{
      text-align: center;
      padding: 32px;
      border-top: 1px solid rgba(255,255,255,0.06);
      color: #374151;
      font-size: 0.8rem;
      margin-top: 40px;
    }}
    .page-footer a {{ color: #6366f1; text-decoration: none; }}

    @media (max-width: 600px) {{
      .header h1 {{ font-size: 1.5rem; }}
      .stats-bar {{ gap: 16px; }}
      .job-card-header {{ flex-wrap: wrap; }}
      .score-circle {{ width: 72px; height: 72px; }}
      .score-number {{ font-size: 1.3rem; }}
    }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <div class="header">
    <span class="header-emoji">🤖</span>
    <h1>Your Daily Job Matches</h1>
    <p class="header-sub">{run_date} • AI-powered by Gemini • Resume match for <strong style="color:#a78bfa">{candidate_name}</strong></p>
    <div class="stats-bar">
      <div class="stat">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Jobs Found</div>
      </div>
      <div class="stat">
        <div class="stat-value" style="color:#22c55e">{top_score}%</div>
        <div class="stat-label">Top Match Score</div>
      </div>
      <div class="stat">
        <div class="stat-value" style="color:#f59e0b">{avg_score}%</div>
        <div class="stat-label">Average Score</div>
      </div>
    </div>
  </div>

  <div class="container">

    <!-- PROFILE BANNER -->
    <div class="profile-banner">
      <div class="profile-avatar">{candidate_name[0].upper() if candidate_name else "?"}</div>
      <div class="profile-info">
        <h3>{candidate_name} — {role}</h3>
        <p>🛠️ Skills: {skills_preview} &nbsp;•&nbsp; 📍 {profile.get('preferred_location', 'Hyderabad')} &nbsp;•&nbsp; 🏠 Remote/Hybrid</p>
      </div>
    </div>

    {apply_section}

    <!-- JOB LISTINGS -->
    <div class="section-title">🎯 Top Job Matches</div>
    {job_cards}

  </div>

  <div class="page-footer">
    <p>Generated by <strong>AI Resume Job Finder</strong> &nbsp;•&nbsp; {run_date} &nbsp;•&nbsp; Powered by Google Gemini</p>
    <p style="margin-top:6px">Jobs sourced from RemoteOK, Arbeitnow, JSearch &amp; Adzuna</p>
  </div>

</body>
</html>"""


class Reporter:
    def __init__(self, config: dict):
        self.config = config
        self.email_cfg = config.get("email", {})
        self.output_dir = Path(config.get("output", {}).get("directory", "output"))
        self.output_dir.mkdir(exist_ok=True)

    def report(self, profile: dict, jobs: list[dict], apply_results: list[dict] = None):
        """Generate HTML report, save it, and optionally send via email."""
        run_date = datetime.now().strftime("%B %d, %Y")
        date_slug = datetime.now().strftime("%Y-%m-%d")

        html = build_html_report(profile, jobs, run_date, apply_results=apply_results)

        # Save HTML file
        report_path = self.output_dir / f"job_report_{date_slug}.html"
        report_path.write_text(html, encoding="utf-8")
        log.info(f"   💾 Report saved: {report_path.resolve()}")

        # Send email if enabled
        if self.email_cfg.get("enabled"):
            self._send_email(html, profile, jobs, run_date)

        # Cleanup old reports
        self._cleanup_old_reports()

        return str(report_path.resolve())

    def _send_email(self, html: str, profile: dict, jobs: list[dict], run_date: str):
        sender = self.email_cfg.get("sender_email", "")
        password = self.email_cfg.get("sender_password", "")
        recipient = self.email_cfg.get("recipient_email", sender)
        subject_template = self.email_cfg.get("subject", "🤖 Your Daily Job Matches — {date}")
        subject = subject_template.format(date=run_date)

        if not sender or sender == "YOUR_EMAIL@gmail.com":
            log.warning("   ⚠️  Email skipped: sender_email not configured in config.yaml")
            return
        if not password or password == "YOUR_APP_PASSWORD_HERE":
            log.warning("   ⚠️  Email skipped: sender_password not configured in config.yaml")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"AI Job Finder <{sender}>"
            msg["To"] = recipient

            # Plain text fallback
            top_jobs_text = "\n".join(
                f"  {i+1}. {j['title']} @ {j['company']} — {j['match_score']}% match\n"
                f"     Apply: {j.get('url', 'N/A')}"
                for i, j in enumerate(jobs[:5])
            )
            text_body = (
                f"Your Daily Job Matches — {run_date}\n\n"
                f"Hi {profile.get('name', 'there')}!\n\n"
                f"Found {len(jobs)} matching jobs today.\n\n"
                f"Top Matches:\n{top_jobs_text}\n\n"
                f"Open the HTML version for full details with cover letter snippets."
            )
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html, "html"))

            smtp_server = self.email_cfg.get("smtp_server", "smtp.gmail.com")
            smtp_port = self.email_cfg.get("smtp_port", 587)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, recipient, msg.as_string())

            log.info(f"   📧 Email sent to: {recipient}")
        except smtplib.SMTPAuthenticationError:
            log.error(
                "   ❌ Email authentication failed!\n"
                "   Make sure you're using a Gmail App Password, NOT your regular password.\n"
                "   Guide: https://support.google.com/accounts/answer/185833"
            )
        except Exception as e:
            log.error(f"   ❌ Failed to send email: {e}")

    def _cleanup_old_reports(self):
        keep_days = self.config.get("output", {}).get("keep_reports_days", 30)
        cutoff = datetime.now().timestamp() - (keep_days * 86400)
        for f in self.output_dir.glob("job_report_*.html"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                log.info(f"   🗑️  Deleted old report: {f.name}")
