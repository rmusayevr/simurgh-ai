"""
Email service for sending transactional emails.

Transport priority:
    1. Resend SDK  — set RESEND_API_KEY in .env (recommended, bypasses SMTP port blocks)
    2. SMTP        — fallback when RESEND_API_KEY is absent

Provides:
    - Account activation emails
    - Password reset emails
    - Welcome emails
    - Generic notification emails

Configuration (in .env):
    # Resend (primary)
    RESEND_API_KEY=re_xxxxxxxxxxxx
    EMAIL_FROM_EMAIL=you@yourdomain.com
    EMAIL_FROM_NAME=My App

    # SMTP (fallback)
    SMTP_SERVER=smtp.example.com
    SMTP_PORT=587
    SMTP_USER=user
    SMTP_PASSWORD=secret
"""

import asyncio
import structlog
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import resend
from aiosmtplib import SMTP, SMTPException

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException

logger = structlog.get_logger(__name__)


# ==================== Email Sending Core ====================


async def send_email(
    email_to: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email via SMTP.

    Args:
        email_to: Recipient email address
        subject: Email subject line
        html_content: HTML body content
        text_content: Plain text fallback (optional, auto-generated if not provided)

    Returns:
        bool: True if email sent successfully, False otherwise

    Raises:
        ServiceUnavailableException: If email service is not configured

    Example:
        >>> success = await send_email(
        ...     email_to="user@example.com",
        ...     subject="Welcome!",
        ...     html_content="<h1>Hello World</h1>"
        ... )
    """
    log = logger.bind(recipient=email_to, subject=subject)

    if not settings.EMAIL_ENABLED:
        log.warning(
            "email_disabled",
            reason="No email transport configured (set RESEND_API_KEY or SMTP_* vars)",
        )
        return False

    plain = text_content or _html_to_plain_text(html_content)

    # ------------------------------------------------------------------ #
    # Transport 1: Resend SDK                                             #
    # Preferred — uses HTTPS, never blocked by hosting providers.         #
    # ------------------------------------------------------------------ #
    if settings.resend_configured:
        return await _send_via_resend(email_to, subject, html_content, plain, log)

    # ------------------------------------------------------------------ #
    # Transport 2: SMTP fallback                                          #
    # ------------------------------------------------------------------ #
    if settings.smtp_configured:
        return await _send_via_smtp(email_to, subject, html_content, plain, log)

    log.error(
        "email_credentials_missing", hint="Set RESEND_API_KEY or full SMTP_* vars"
    )
    raise ServiceUnavailableException(
        "Email service is not configured",
        detail={
            "hint": "Set RESEND_API_KEY (recommended) or SMTP_SERVER + SMTP_USER + SMTP_PASSWORD + EMAIL_FROM_EMAIL"
        },
    )


async def _send_via_resend(
    email_to: str, subject: str, html_content: str, text_content: str, log
) -> bool:
    """Send via Resend Python SDK (HTTPS — not affected by SMTP port blocks)."""
    try:
        resend.api_key = settings.RESEND_API_KEY.get_secret_value()
        params: resend.Emails.SendParams = {
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_EMAIL}>",
            "to": [email_to],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        # resend.Emails.send is synchronous — run in thread to avoid blocking the event loop
        email = await asyncio.get_event_loop().run_in_executor(
            None, lambda: resend.Emails.send(params)
        )
        log.info(
            "email_sent_successfully", transport="resend", message_id=email.get("id")
        )
        return True
    except Exception as e:
        log.error(
            "resend_error",
            transport="resend",
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


async def _send_via_smtp(
    email_to: str, subject: str, html_content: str, text_content: str, log
) -> bool:
    """Send via raw SMTP (fallback when RESEND_API_KEY is not set)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_EMAIL}>"
    msg["To"] = email_to
    msg["Reply-To"] = settings.EMAIL_FROM_EMAIL
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # Auto-derive TLS mode from port
    port = settings.SMTP_PORT
    if port == 465:
        use_tls, starttls = True, False
    elif port == 587:
        use_tls, starttls = False, True
    else:
        use_tls, starttls = settings.SMTP_TLS, settings.SMTP_STARTTLS

    # Quick TCP reachability check — fail fast instead of 60 s hang
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.SMTP_SERVER, port), timeout=5
        )
        writer.close()
        await writer.wait_closed()
    except (asyncio.TimeoutError, OSError) as e:
        log.error(
            "smtp_port_blocked",
            transport="smtp",
            host=settings.SMTP_SERVER,
            port=port,
            hint="Port blocked by hosting provider — set RESEND_API_KEY instead.",
            error=str(e),
        )
        return False

    try:
        smtp = SMTP(
            hostname=settings.SMTP_SERVER, port=port, use_tls=use_tls, timeout=30
        )
        async with smtp:
            if starttls:
                await smtp.starttls()
            await smtp.login(
                settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value()
            )
            await smtp.send_message(msg)
        log.info("email_sent_successfully", transport="smtp")
        return True
    except SMTPException as e:
        log.error(
            "smtp_error",
            transport="smtp",
            error=str(e),
            error_code=getattr(e, "smtp_code", None),
        )
        return False
    except Exception as e:
        log.error(
            "email_delivery_failed",
            transport="smtp",
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


# ==================== Template Rendering ====================


def render_email_template(
    template_name: str,
    context: Dict[str, Any],
) -> str:
    """
    Render an email template with context variables.

    Args:
        template_name: Name of template (e.g., "password_reset")
        context: Variables to inject into template

    Returns:
        str: Rendered HTML content
    """
    templates = {
        "password_reset": _get_password_reset_template,
        "account_activation": _get_account_activation_template,
        "welcome": _get_welcome_template,
        "notification": _get_notification_template,
    }

    template_func = templates.get(template_name)
    if not template_func:
        logger.warning("template_not_found", template=template_name)
        return _get_default_template(context)

    return template_func(context)


def _get_base_template(title: str, content: str, context: Optional[Dict] = None) -> str:
    """
    Base email template with consistent styling.

    Args:
        title: Email header title
        content: Main content HTML
        context: Optional context variables

    Returns:
        str: Complete HTML email
    """
    context = context or {}

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">{settings.PROJECT_NAME}</h1>
            </div>
            
            <!-- Content -->
            <div style="padding: 40px 30px;">
                {content}
            </div>
            
            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 20px 30px; text-align: center; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; font-size: 12px; color: #6c757d;">
                    {settings.PROJECT_NAME} &copy; {context.get("year", "2026")}
                </p>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #6c757d;">
                    If you have questions, reply to this email or visit our <a href="{settings.FRONTEND_URL}/support" style="color: #667eea; text-decoration: none;">support page</a>.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def _get_password_reset_template(context: Dict[str, Any]) -> str:
    """Password reset email template."""
    reset_link = context.get("reset_link", "")

    content = f"""
    <h2 style="color: #333; margin-top: 0;">Reset Your Password</h2>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        You requested to reset your password. Click the button below to create a new password.
    </p>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        This link is valid for <strong>1 hour</strong>.
    </p>
    
    <div style="text-align: center; margin: 40px 0;">
        <a href="{reset_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">
            Reset Password
        </a>
    </div>
    
    <p style="color: #999; font-size: 13px; line-height: 1.6; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee;">
        <strong>Didn't request this?</strong> You can safely ignore this email. Your password won't change unless you click the button above.
    </p>
    
    <p style="color: #999; font-size: 12px; margin-top: 20px;">
        If the button doesn't work, copy and paste this link into your browser:<br>
        <span style="color: #667eea; word-break: break-all;">{reset_link}</span>
    </p>
    """

    return _get_base_template("Reset Your Password", content, context)


def _get_account_activation_template(context: Dict[str, Any]) -> str:
    """Account activation email template."""
    activation_link = context.get("activation_link", "")
    username = context.get("username", "there")

    content = f"""
    <h2 style="color: #333; margin-top: 0;">Welcome to {settings.PROJECT_NAME}! 🎉</h2>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        Hi <strong>{username}</strong>,
    </p>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        Thank you for signing up! To get started, please verify your email address by clicking the button below.
    </p>
    
    <div style="text-align: center; margin: 40px 0;">
        <a href="{activation_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">
            Activate Your Account
        </a>
    </div>
    
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        Once verified, you'll have full access to:
    </p>
    <ul style="color: #666; line-height: 1.8; font-size: 15px;">
        <li>Multi-agent architecture debates</li>
        <li>RAG-powered document analysis</li>
        <li>Stakeholder alignment tools</li>
        <li>Project insights dashboard</li>
    </ul>
    
    <p style="color: #999; font-size: 12px; margin-top: 30px;">
        If the button doesn't work, copy and paste this link:<br>
        <span style="color: #667eea; word-break: break-all;">{activation_link}</span>
    </p>
    """

    return _get_base_template("Activate Your Account", content, context)


def _get_welcome_template(context: Dict[str, Any]) -> str:
    """Welcome email template (sent after activation)."""
    username = context.get("username", "there")
    dashboard_link = f"{settings.FRONTEND_URL}/dashboard"

    content = f"""
    <h2 style="color: #333; margin-top: 0;">You're All Set! 🚀</h2>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        Hi <strong>{username}</strong>,
    </p>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        Your account is now active. Welcome to the future of AI-assisted software architecture!
    </p>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 30px 0;">
        <h3 style="color: #333; margin-top: 0; font-size: 18px;">Quick Start Guide</h3>
        <ol style="color: #666; line-height: 1.8; margin: 0; padding-left: 20px;">
            <li>Create your first project</li>
            <li>Upload architectural documentation</li>
            <li>Start a multi-agent debate</li>
            <li>Review and refine proposals</li>
        </ol>
    </div>
    
    <div style="text-align: center; margin: 40px 0;">
        <a href="{dashboard_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">
            Go to Dashboard
        </a>
    </div>
    
    <p style="color: #666; line-height: 1.6; font-size: 14px; margin-top: 30px;">
        Need help getting started? Check out our <a href="{settings.FRONTEND_URL}/docs" style="color: #667eea; text-decoration: none;">documentation</a> or reach out to support.
    </p>
    """

    return _get_base_template("Welcome!", content, context)


def _get_notification_template(context: Dict[str, Any]) -> str:
    """Generic notification email template."""
    title = context.get("title", "Notification")
    message = context.get("message", "")
    action_text = context.get("action_text")
    action_link = context.get("action_link")

    content = f"""
    <h2 style="color: #333; margin-top: 0;">{title}</h2>
    <p style="color: #666; line-height: 1.6; font-size: 16px;">
        {message}
    </p>
    """

    if action_text and action_link:
        content += f"""
        <div style="text-align: center; margin: 40px 0;">
            <a href="{action_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">
                {action_text}
            </a>
        </div>
        """

    return _get_base_template(title, content, context)


def _get_default_template(context: Dict[str, Any]) -> str:
    """Fallback template."""
    return _get_notification_template(context)


# ==================== High-Level Email Functions ====================


async def send_password_reset_email(
    email_to: str, token: str, username: Optional[str] = None
) -> bool:
    """
    Send password reset email.

    Args:
        email_to: Recipient email
        token: Password reset token
        username: Optional username for personalization

    Returns:
        bool: True if sent successfully
    """
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    html_content = render_email_template(
        "password_reset",
        {
            "reset_link": reset_link,
            "username": username,
        },
    )

    text_content = f"""
Reset Your Password

You requested to reset your password. Use the link below to create a new password.
This link is valid for 1 hour.

{reset_link}

If you didn't request this, you can safely ignore this email.

---
{settings.PROJECT_NAME}
    """.strip()

    return await send_email(
        email_to=email_to,
        subject=f"Reset Your Password - {settings.PROJECT_NAME}",
        html_content=html_content,
        text_content=text_content,
    )


async def send_activation_email(
    email_to: str, token: str, username: Optional[str] = None
) -> bool:
    """
    Send account activation email.

    Args:
        email_to: Recipient email
        token: Activation token
        username: Optional username for personalization

    Returns:
        bool: True if sent successfully
    """
    activation_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    html_content = render_email_template(
        "account_activation",
        {
            "activation_link": activation_link,
            "username": username or "there",
        },
    )

    text_content = f"""
Welcome to {settings.PROJECT_NAME}!

Hi {username or "there"},

Thank you for signing up! Please verify your email address:

{activation_link}

---
{settings.PROJECT_NAME}
    """.strip()

    return await send_email(
        email_to=email_to,
        subject=f"Activate Your Account - {settings.PROJECT_NAME}",
        html_content=html_content,
        text_content=text_content,
    )


async def send_welcome_email(email_to: str, username: str) -> bool:
    """
    Send welcome email after account activation.

    Args:
        email_to: Recipient email
        username: User's name

    Returns:
        bool: True if sent successfully
    """
    html_content = render_email_template("welcome", {"username": username})

    text_content = f"""
You're All Set!

Hi {username},

Your account is now active. Welcome to {settings.PROJECT_NAME}!

Visit your dashboard: {settings.FRONTEND_URL}/dashboard

---
{settings.PROJECT_NAME}
    """.strip()

    return await send_email(
        email_to=email_to,
        subject=f"Welcome to {settings.PROJECT_NAME}!",
        html_content=html_content,
        text_content=text_content,
    )


async def send_notification_email(
    email_to: str,
    title: str,
    message: str,
    action_text: Optional[str] = None,
    action_link: Optional[str] = None,
) -> bool:
    """
    Send a generic notification email.

    Args:
        email_to: Recipient email
        title: Email title
        message: Email message
        action_text: Optional button text
        action_link: Optional button link

    Returns:
        bool: True if sent successfully
    """
    html_content = render_email_template(
        "notification",
        {
            "title": title,
            "message": message,
            "action_text": action_text,
            "action_link": action_link,
        },
    )

    return await send_email(
        email_to=email_to,
        subject=title,
        html_content=html_content,
    )


# ==================== Utilities ====================


def _html_to_plain_text(html: str) -> str:
    """
    Convert HTML to plain text (simple implementation).

    For production, consider using libraries like html2text.
    """
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html)

    # Replace multiple whitespace with single space
    text = re.sub(r"\s+", " ", text)

    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")

    return text.strip()
