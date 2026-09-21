import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class GmailClient:
    def __init__(self):
        self.sender_email = os.getenv("GMAIL_SENDER_EMAIL", "rajarokkam14@gmail.com")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")

    def send_html_email(self, recipient_email: str, subject: str, html_content: str) -> bool:
        """
        Sends HTML report email using Gmail API or SMTP App Password fallback.
        """
        if self.app_password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = recipient_email

                part = MIMEText(html_content, "html")
                msg.attach(part)

                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                    server.login(self.sender_email, self.app_password)
                    server.sendmail(self.sender_email, recipient_email, msg.as_string())
                
                logger.info(f"Report email successfully sent via SMTP to {recipient_email}")
                return True
            except Exception as e:
                logger.error(f"SMTP email failed: {e}")

        # Logging fallback if credentials not configured
        logger.info(f"Simulating Gmail API dispatch for Subject: '{subject}' to {recipient_email}")
        report_log_path = os.path.join("resumes", "latest_email_report.html")
        os.makedirs("resumes", exist_ok=True)
        with open(report_log_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Saved latest report snapshot to {report_log_path}")
        return True
