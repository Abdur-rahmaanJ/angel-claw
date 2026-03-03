import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from angel_claw.skills.manager import skill
from angel_claw.config import settings


def _get_smtp_config() -> dict:
    """Get SMTP configuration from settings."""
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        return None
    return {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "password": settings.smtp_password,
        "use_tls": settings.smtp_use_tls,
    }


@skill
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html: bool = False,
) -> str:
    """
    Sends an external email via SMTP (Gmail, Outlook, etc.).
    WARNING: Do NOT use this for "internal messages" or "messaging [user]".
    For those, use the 'send_internal_message' skill instead.
    
    - to: Recipient email address (comma-separated for multiple)
    - subject: Email subject line
    - body: Email body content
    - cc: Optional CC recipients (comma-separated)
    - bcc: Optional BCC recipients (comma-separated)
    - html: Set to True if body contains HTML content
    """
    config = _get_smtp_config()
    if not config:
        return "Error: Email not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in .env"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["user"]
        msg["To"] = to

        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        mime_type = "html" if html else "plain"
        msg.attach(MIMEText(body, mime_type))

        all_recipients = to.split(",")
        if cc:
            all_recipients.extend(cc.split(","))
        if bcc:
            all_recipients.extend(bcc.split(","))
        all_recipients = [r.strip() for r in all_recipients if r.strip()]

        with smtplib.SMTP(config["host"], config["port"]) as server:
            if config.get("use_tls", True):
                server.starttls()
            server.login(config["user"], config["password"])
            server.sendmail(config["user"], all_recipients, msg.as_string())

        return f"✅ Email sent successfully to {to}"

    except Exception as e:
        return f"Error sending email: {e}"


@skill
def send_email_with_template(to: str, template_name: str, variables: dict) -> str:
    """
    Sends an email using a predefined template.
    - to: Recipient email address
    - template_name: Name of the template (welcome, reminder, notification)
    - variables: Dictionary of variables to fill in template
    """
    templates = {
        "welcome": {
            "subject": "Welcome!",
            "body": "Hello {name}! Welcome to our service.",
        },
        "reminder": {
            "subject": "Reminder: {title}",
            "body": "Hi {name},\n\nThis is a reminder about:\n{title}\n\n{details}",
        },
        "notification": {
            "subject": "Notification",
            "body": "Hello {name},\n\n{message}\n\nBest regards",
        },
    }

    if template_name not in templates:
        return f"Error: Template '{template_name}' not found. Available: {', '.join(templates.keys())}"

    template = templates[template_name]

    try:
        subject = template["subject"].format(**variables)
        body = template["body"].format(**variables)
    except KeyError as e:
        return f"Error: Missing variable {e} for template"

    return send_email(to, subject, body)
