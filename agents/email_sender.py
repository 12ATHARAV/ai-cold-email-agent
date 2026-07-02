import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from config import RESUME_PATH, MY_NAME, MY_EMAIL
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EmailSender:
    def __init__(self):
        self.gmail_user = os.getenv("GMAIL_USER") or MY_EMAIL
        self.gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

    def send_email(self, to_email: str, subject: str, body_content: str) -> bool:
        """Sends an email with attachment using Gmail SMTP."""
        if not self.gmail_user or not self.gmail_app_password:
            logger.error("Gmail credentials are not configured in environment variables (.env). Cannot send email.")
            return False

        if not to_email:
            logger.error("No recipient email specified. Cannot send email.")
            return False

        logger.info(f"Preparing to send email to {to_email} with subject: {subject}")
        
        try:
            # Create message container
            msg = MIMEMultipart()
            msg["From"] = f"{MY_NAME} <{self.gmail_user}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # Check if body is HTML or plain text
            is_html = "<html" in body_content.lower() or "<p" in body_content.lower() or "<div" in body_content.lower()
            
            if is_html:
                # Attach HTML body
                msg.attach(MIMEText(body_content, "html", "utf-8"))
                # Also attach a plain text version for email clients that don't render HTML
                # Simple strip of HTML tags for plain text fallback
                plain_text = re.sub('<[^<]+?>', '', body_content) if 're' in globals() else body_content
                msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            else:
                # It's plain text, we can convert newlines to <br> for a simple HTML version
                html_body = f"<html><body>{body_content.replace('\n', '<br>')}</body></html>"
                msg.attach(MIMEText(body_content, "plain", "utf-8"))
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Attach resume PDF
            if RESUME_PATH.exists():
                logger.info(f"Attaching resume from {RESUME_PATH}...")
                with open(RESUME_PATH, "rb") as f:
                    pdf_data = f.read()
                    attachment = MIMEApplication(pdf_data, _subtype="pdf")
                    attachment.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=RESUME_PATH.name
                    )
                    msg.attach(attachment)
            else:
                logger.warning(f"Resume PDF not found at {RESUME_PATH}. Sending email without attachment.")

            # Connect to Gmail SMTP Server
            # We use port 587 with starttls (preferred for Gmail)
            logger.info("Connecting to Gmail SMTP server (smtp.gmail.com:587)...")
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
            logger.info("Logging into Gmail...")
            server.login(self.gmail_user, self.gmail_app_password)
            
            logger.info("Sending message...")
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email successfully sent to {to_email}!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False
