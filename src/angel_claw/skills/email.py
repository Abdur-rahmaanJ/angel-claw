import smtplib
import email
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from angel_claw.skills.manager import skill
from angel_claw.config import settings
from angel_claw.utils import get_user_root

SKILL_CONFIG = {
    "fields": [
        {
            "name": "smtp_host",
            "type": "text",
            "description": "SMTP server hostname (e.g., smtp.gmail.com)",
        },
        {"name": "smtp_port", "type": "number", "description": "SMTP port (e.g., 587)"},
        {"name": "smtp_user", "type": "text", "description": "SMTP username/email"},
        {
            "name": "smtp_password",
            "type": "password",
            "description": "SMTP password or app password",
        },
        {
            "name": "smtp_use_tls",
            "type": "checkbox",
            "description": "Use TLS (recommended)",
        },
    ]
}


def _get_user_config(user_id: str = None) -> dict:
    """Get skill config from user's config file."""
    if not user_id:
        return {}
    user_root = get_user_root(user_id)
    config_file = user_root / "skill_config.json"
    if config_file.exists():
        try:
            return json.load(open(config_file))
        except:
            pass
    return {}


def _get_smtp_config(user_id: str = None) -> dict:
    """Get SMTP configuration from user skill config or global settings."""
    if user_id:
        user_config = _get_user_config(user_id)
        email_config = user_config.get("email", {}).get("fields", {})
        if email_config.get("smtp_host") and email_config.get("smtp_user"):
            return {
                "host": email_config.get("smtp_host", ""),
                "port": int(email_config.get("smtp_port", 587)),
                "user": email_config.get("smtp_user", ""),
                "password": email_config.get("smtp_password", ""),
                "use_tls": email_config.get("smtp_use_tls", True),
            }

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
    user_id: str = None,
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
    config = _get_smtp_config(user_id)
    if not config:
        return "Error: Email not configured. Set SMTP settings in Skills config or .env"

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
