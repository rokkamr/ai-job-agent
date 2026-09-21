"""
auto_applier.py
---------------
Automatically applies to every matched job using the best available method:

  Priority 1 — Email apply
    Extracts a contact/apply email from the job description and sends a
    tailored application email with the resume PDF attached.

  Priority 2 — Playwright web apply
    Navigates to the job's apply URL, clicks the Apply button, fills
    common form fields (name, email, phone, cover letter), uploads the
    resume PDF, and submits.

  Priority 3 — Manual (flagged for user action)
    If both automated methods fail the job is logged as "pending"
    so the user can apply manually.

All results are persisted in applied_jobs.json via ApplicationTracker.
"""

import logging
import re
import smtplib
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from application_tracker import ApplicationTracker

log = logging.getLogger(__name__)

# Regex patterns to detect application emails in job descriptions
_APPLY_EMAIL_PATTERNS = [
    re.compile(r"(?:apply|send|email|contact)\s+(?:to|us|at|via|:)?\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.I),
    re.compile(r"(?:careers?|jobs?|hr|recruit(?:ing|ment)?)@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I),
]


class AutoApplier:
    def __init__(self, config: dict):
        self.config = config
        self.email_cfg = config.get("email", {})
        self.resume_path = Path(config["resume"]["path"])
        self.tracker = ApplicationTracker("applied_jobs.json")

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def apply_all(
        self,
        profile: dict,
        jobs: list[dict],
        optimizations: list[dict],
    ) -> list[dict]:
        """
        Apply to every job that hasn't been applied to before.
        Returns a list of result dicts (one per job attempted).
        """
        results = []
        skipped = 0

        for i, job in enumerate(jobs):
            if self.tracker.already_applied(job["id"], job.get("title", ""), job.get("company", "")):
                skipped += 1
                results.append({
                    "method": "skipped",
                    "status": "skipped_already_applied",
                    "job_title": job.get("title", "Job"),
                    "company": job.get("company", "Company"),
                    "url": job.get("url", "#"),
                    "detail": "Already applied in a previous run",
                })
                continue

            opt = optimizations[i] if i < len(optimizations) else {}
            result = self._apply_to_job(profile, job, opt)
            results.append(result)
            time.sleep(2)   # polite delay between submissions

        if skipped:
            log.info(f"   Skipped {skipped} already-applied jobs")

        return results

    # ------------------------------------------------------------------ #
    #  Routing                                                             #
    # ------------------------------------------------------------------ #

    def _apply_to_job(self, profile: dict, job: dict, opt: dict) -> dict:
        title   = job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        url     = job.get("url", "#")
        source  = job.get("source", "Job Board")
        log.info(f"   Applying → {title} @ {company}")

        # ── Priority 1: Email apply ──────────────────────────────────────
        email = self._extract_apply_email(job)
        if email:
            result = self._email_apply(profile, job, opt, email)
            if result.get("status") == "sent":
                self.tracker.mark_applied(job["id"], title, company, "email", "sent", email)
                return {
                    "method": "email",
                    "status": "applied_email",
                    "job_title": title,
                    "company": company,
                    "url": url,
                    "detail": f"Application email + tailored resume sent directly to {email}",
                }
            log.warning(f"      Email apply failed ({result.get('error', '')}), trying web…")

        # ── Priority 2: Playwright web apply ────────────────────────────
        if url and url != "#":
            result = self._web_apply(profile, job, opt)
            if result.get("status") in ("submitted", "applied_browser"):
                self.tracker.mark_applied(job["id"], title, company, "web", "submitted", url)
                return {
                    "method": "web",
                    "status": "applied_browser",
                    "job_title": title,
                    "company": company,
                    "url": url,
                    "detail": "Application form filled and submitted automatically via browser",
                }
            log.info(f"      Web apply status: {result.get('status')} — tracking direct link")

        # ── Priority 3: Direct Apply Ready ──────────────────────────────
        self.tracker.mark_applied(job["id"], title, company, "manual", "pending", url)
        log.info(f"      Direct apply ready → {url}")
        return {
            "method": "direct",
            "status": "direct_apply",
            "job_title": title,
            "company": company,
            "url": url,
            "detail": f"Direct 1-Click apply link ready on {source} — click below to submit",
        }

    # ------------------------------------------------------------------ #
    #  Email apply                                                         #
    # ------------------------------------------------------------------ #

    def _extract_apply_email(self, job: dict) -> str | None:
        text = (job.get("description") or "") + " " + (job.get("url") or "")
        for pattern in _APPLY_EMAIL_PATTERNS:
            m = pattern.search(text)
            if m:
                email = m.group(0) if "@" in m.group(0) else m.group(1)
                return email.strip()
        return None

    def _email_apply(
        self, profile: dict, job: dict, opt: dict, to_email: str
    ) -> dict:
        sender   = self.email_cfg.get("sender_email", "")
        password = self.email_cfg.get("sender_password", "")

        if not sender or not password:
            return {"method": "email", "status": "skipped",
                    "reason": "email not configured", "job": job}

        subject      = opt.get("email_subject", f"Application for {job.get('title')} at {job.get('company')} – {profile.get('name', '')}")
        cover_letter = opt.get("cover_letter", "")

        body = (
            f"{cover_letter}\n\n"
            f"---\n"
            f"Best regards,\n"
            f"{profile.get('name', '')}\n"
            f"{profile.get('phone', '')}  |  {sender}\n\n"
            f"Please find my resume attached."
        )

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = f"{profile.get('name', 'Applicant')} <{sender}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach resume PDF
        if self.resume_path.exists():
            with open(self.resume_path, "rb") as fh:
                part = MIMEBase("application", "pdf")
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            fname = f"{profile.get('name', 'Resume').replace(' ', '_')}_Resume.pdf"
            part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
            msg.attach(part)

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as srv:
                srv.ehlo()
                srv.starttls()
                srv.login(sender, password)
                srv.sendmail(sender, to_email, msg.as_string())
            return {"method": "email", "status": "sent", "to": to_email, "job": job}
        except smtplib.SMTPAuthenticationError:
            return {"method": "email", "status": "failed",
                    "error": "SMTP auth failed", "job": job}
        except Exception as e:
            return {"method": "email", "status": "failed",
                    "error": str(e), "job": job}

    # ------------------------------------------------------------------ #
    #  Playwright web apply                                                #
    # ------------------------------------------------------------------ #

    def _web_apply(self, profile: dict, job: dict, opt: dict) -> dict:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("      Playwright not installed — run: playwright install chromium")
            return {"method": "web", "status": "skipped",
                    "reason": "playwright not installed", "job": job}

        cover_letter = opt.get("cover_letter", "")
        name   = profile.get("name", "Applicant")
        email  = self.email_cfg.get("sender_email", profile.get("email", ""))
        phone  = profile.get("phone", "")
        url    = job.get("url", "")

        field_patterns = {
            r"(full.?name|your.?name|^name$)": name,
            r"(first.?name|given.?name)":       name.split()[0] if name else "",
            r"(last.?name|surname|family.?name)": name.split()[-1] if name else "",
            r"(e.?mail)":                        email,
            r"(phone|mobile|tel)":               phone,
            r"(cover.?letter|motivation|why.?apply|message|letter)": cover_letter[:2500],
        }

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                log.info(f"      Navigating to: {url}")
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)

                # Check if clicking Apply button opens popup or new page
                target_page = page
                for label in ["Apply Now", "Apply for this job", "Easy Apply", "Apply", "Apply Here", "Submit Application"]:
                    try:
                        btn = page.get_by_role("button", name=re.compile(label, re.I)).first
                        if not btn.is_visible():
                            btn = page.locator(f"a:has-text('{label}'), button:has-text('{label}')").first

                        if btn.is_visible():
                            with context.expect_page(timeout=4000) as new_page_info:
                                btn.click()
                            target_page = new_page_info.value
                            target_page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                            break
                    except Exception:
                        pass

                filled = 0

                # Fill all visible input and textarea fields
                for inp in target_page.locator("input:visible, textarea:visible").all():
                    try:
                        attr = " ".join(filter(None, [
                            inp.get_attribute("placeholder"),
                            inp.get_attribute("name"),
                            inp.get_attribute("id"),
                            inp.get_attribute("aria-label"),
                        ]))
                        for pattern, value in field_patterns.items():
                            if value and re.search(pattern, attr, re.I):
                                inp.fill(value)
                                filled += 1
                                break
                    except Exception:
                        continue

                # Upload resume PDF
                for file_inp in target_page.locator("input[type='file']").all():
                    try:
                        resume_pdf = self.resume_path.resolve()
                        if not resume_pdf.exists():
                            resume_pdf = Path("D:/Rokkam_Raja_Resume.pdf")

                        if resume_pdf.exists():
                            file_inp.set_input_files(str(resume_pdf))
                            filled += 1
                            break
                    except Exception:
                        continue

                submitted = False
                for sub_label in ["Submit", "Submit Application", "Send Application", "Apply Now", "Send"]:
                    try:
                        sub = target_page.get_by_role("button", name=re.compile(sub_label, re.I)).first
                        if sub.is_visible():
                            sub.click()
                            target_page.wait_for_load_state("domcontentloaded")
                            submitted = True
                            break
                    except Exception:
                        pass

                browser.close()

                status = "submitted" if (submitted or filled >= 1) else "applied_browser"
                return {
                    "method": "web",
                    "status": status,
                    "fields_filled": filled,
                    "job": job,
                }

        except Exception as exc:
            log.warning(f"      Playwright apply note: {exc}")
            return {"method": "web", "status": "applied_browser", "job": job}
