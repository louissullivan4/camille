"""
Email service using Gmail SMTP with an app password.
Configure via GMAIL_ADDRESS and GMAIL_APP_PASSWORD env vars.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import settings

log = structlog.get_logger()


def _send_email(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    """Send an email via Gmail SMTP. Raises on failure."""
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        log.warning("email.skipped_no_credentials", to=to_email, subject=subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Camille <{settings.GMAIL_ADDRESS}>"
    msg["To"] = to_email

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        server.sendmail(settings.GMAIL_ADDRESS, to_email, msg.as_string())

    log.info("email.sent", to=to_email, subject=subject)


def send_password_reset_code(to_email: str, code: str) -> None:
    """Send a 6-digit password reset code to the user."""
    subject = "Your Camille password reset code"
    text_body = (
        f"Your password reset code is: {code}\n\n"
        "This code expires in 15 minutes.\n\n"
        "If you did not request this, ignore this email."
    )
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #161616;">Password Reset</h2>
      <p>Use the code below to reset your Camille password. It expires in <strong>15 minutes</strong>.</p>
      <div style="background: #f4f4f4; padding: 24px; text-align: center; border-radius: 4px; margin: 24px 0;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0f62fe;">{code}</span>
      </div>
      <p style="color: #6f6f6f; font-size: 14px;">
        If you did not request a password reset, you can safely ignore this email.
      </p>
    </div>
    """
    _send_email(to_email, subject, html_body, text_body)


def send_invitation_email(to_email: str, token: str, role: str, org_name: str | None) -> None:
    """Send an invitation email with signup link."""
    signup_url = f"{settings.FRONTEND_URL}/signup?token={token}"

    if role == "org_manager":
        role_label = "Organization Manager"
        context = "You have been invited to create an organization on Camille."
    elif role == "org_underwriter":
        role_label = "Underwriter"
        org_context = f" at {org_name}" if org_name else ""
        context = f"You have been invited to join{org_context} as an underwriter on Camille."
    else:
        role_label = role.replace("_", " ").title()
        context = "You have been invited to Camille."

    subject = f"You have been invited to Camille as {role_label}"
    text_body = f"{context}\n\nAccept your invitation here:\n{signup_url}\n\nThis link expires in 48 hours."
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #161616;">You have been invited to Camille</h2>
      <p>{context}</p>
      <p>Your role: <strong>{role_label}</strong></p>
      <div style="margin: 32px 0;">
        <a href="{signup_url}"
           style="background: #0f62fe; color: #fff; padding: 12px 24px; text-decoration: none;
                  border-radius: 2px; font-weight: 600; display: inline-block;">
          Accept Invitation
        </a>
      </div>
      <p style="color: #6f6f6f; font-size: 14px;">
        This link expires in 48 hours. If you did not expect this invite, ignore this email.
      </p>
      <p style="color: #6f6f6f; font-size: 12px;">Or copy this link: {signup_url}</p>
    </div>
    """
    _send_email(to_email, subject, html_body, text_body)
