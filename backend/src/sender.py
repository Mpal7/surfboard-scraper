import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

logger = logging.getLogger(__name__)


def _smtp_error_detail(error: Exception) -> str:
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "Gmail rejected the recipient address."
    if isinstance(error, smtplib.SMTPDataError):
        return "Gmail rejected the message contents."
    if isinstance(error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError)):
        return "Could not connect to Gmail SMTP. Check network access and port 587."
    return f"Unexpected SMTP error ({type(error).__name__}). Check backend logs."


def send_email_with_diagnostics(
    subject: str, body: str, to_email: str
) -> tuple[bool, str | None]:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return (
            False,
            "SMTP configuration is incomplete in the running backend process. "
            "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set.",
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True, None
    except Exception as error:
        detail = _smtp_error_detail(error)
        logger.error("Failed to send email to %s: %s", to_email, detail)
        return False, detail


def send_email(subject: str, body: str, to_email: str) -> bool:
    success, _ = send_email_with_diagnostics(subject, body, to_email)
    return success
