# mailer.py - builds and sends the report email. No Streamlit in here,
# so it can be tested on its own.

import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

IST = timezone(timedelta(hours=5, minutes=30))
ID_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I look-alikes
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAX_SUBJECT_LEN = 200


def now_ist():
    return datetime.now(IST)


def make_report_id(now=None):
    """Exact values come from code, not from the AI."""
    now = now or now_ist()
    suffix = "".join(secrets.choice(ID_CHARS) for _ in range(4))
    return f"CS-{now:%Y%m%d}-{suffix}"


def _one_line(value):
    return " ".join(str(value).split())


def recipients_for(user_email, authority_email):
    """Return (to, cc). If an authority email is given, it receives the report
    and the user is copied. Otherwise (or if both are the same address) the
    report goes only to the user."""
    authority = _one_line(authority_email or "")
    if authority and authority.lower() != user_email.lower():
        return authority, user_email
    return user_email, None


def build_email(sender, profile, subject, report_text, report_id, now=None):
    now = now or now_ist()
    to_addr, cc_addr = recipients_for(profile["email"], profile.get("authority_email"))

    body = (
        "CIVIC ISSUE REPORT\n"
        f"Report ID: {report_id}\n"
        f"Date: {now:%d %b %Y, %I:%M %p} IST\n"
        f"Reported by: {_one_line(profile['name'])} ({profile['email']})\n"
        f"Area: {_one_line(profile['area'])}\n"
        "\n"
        "----------------------------------------\n"
        f"{report_text}\n"
        "----------------------------------------\n"
        "\n"
        "This report was drafted with the help of CivicSnap, an AI assistant, "
        "and reviewed by the reporter before sending. Category and urgency are "
        "AI estimates, not an official assessment.\n"
        f"To respond, reply to this email. Replies go to {profile['email']}.\n"
    )

    msg = EmailMessage()
    msg["Subject"] = f"[{report_id}] {_one_line(subject)}"[:MAX_SUBJECT_LEN]
    msg["From"] = formataddr(("CivicSnap", sender))
    msg["To"] = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr
    msg["Reply-To"] = profile["email"]
    # utf-8 + base64 keeps Hindi/Marathi (Devanagari) text intact.
    msg.set_content(body, subtype="plain", charset="utf-8", cte="base64")
    return msg


def send_email(msg, sender, app_password):
    """Send through Gmail. Returns (ok, error_message)."""
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.login(sender, app_password.replace(" ", ""))
            server.send_message(msg)
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail rejected the login. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
            "(use the 16-character App Password, not your normal password)."
        )
    except smtplib.SMTPRecipientsRefused:
        return False, "Gmail refused one of the email addresses. Please check them."
    except (smtplib.SMTPException, OSError) as error:
        return False, f"Couldn't send the email: {error}"