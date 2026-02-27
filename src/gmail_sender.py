"""
Gmail Sender Module
Sends emails via SMTP using Gmail App Password.
Includes confirmation step, logging, error handling, and retry logic.
"""

import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import EmailDraft, OutreachRecord

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
MAX_RETRIES = 3
LOG_DIR = Path("logs")


def _ensure_log_dir():
    """Ensure the logs directory exists."""
    LOG_DIR.mkdir(exist_ok=True)


def _log_outreach(record: OutreachRecord):
    """Append an outreach record to the CRM-style JSON log."""
    _ensure_log_dir()
    log_file = LOG_DIR / "outreach_log.json"

    records = []
    if log_file.exists():
        try:
            records = json.loads(log_file.read_text())
        except (json.JSONDecodeError, OSError):
            records = []

    records.append(record.model_dump())
    log_file.write_text(json.dumps(records, indent=2))
    logger.info(f"Outreach logged: {record.status} -> {record.recipient_email}")


def get_outreach_log() -> list[OutreachRecord]:
    """Read all outreach records from the log file."""
    log_file = LOG_DIR / "outreach_log.json"
    if not log_file.exists():
        return []

    try:
        data = json.loads(log_file.read_text())
        return [OutreachRecord(**r) for r in data]
    except (json.JSONDecodeError, OSError):
        return []


def update_outreach_record(index: int, **fields) -> OutreachRecord:
    """
    Update specific fields of an outreach record by index.

    Args:
        index: Zero-based index into the outreach log list.
        **fields: Field names and values to update (must be valid OutreachRecord fields).

    Returns:
        The updated OutreachRecord.

    Raises:
        IndexError: If index is out of range.
        ValueError: If any field name is not a valid OutreachRecord field.
    """
    log_file = LOG_DIR / "outreach_log.json"
    records = []
    if log_file.exists():
        try:
            records = json.loads(log_file.read_text())
        except (json.JSONDecodeError, OSError):
            records = []

    if index < 0 or index >= len(records):
        raise IndexError(f"Record index {index} out of range (0-{len(records) - 1})")

    valid_fields = set(OutreachRecord.model_fields.keys())
    for key in fields:
        if key not in valid_fields:
            raise ValueError(f"Invalid field '{key}' — valid fields: {sorted(valid_fields)}")

    records[index].update(fields)
    log_file.write_text(json.dumps(records, indent=2))
    logger.info(f"Updated record {index}: {list(fields.keys())}")
    return OutreachRecord(**records[index])


def send_email(
    draft: EmailDraft,
    to_address: str,
    gmail_address: str,
    gmail_app_password: str,
    sender_name: str = "DAVID AI",
    prospect_url: str = "",
    prospect_name: str = "",
) -> OutreachRecord:
    """
    Send an email via Gmail SMTP with retry logic.

    Args:
        draft: The email draft to send.
        to_address: Recipient email address.
        gmail_address: Your Gmail address.
        gmail_app_password: Gmail App Password (16-char).
        sender_name: Display name for the sender.
        prospect_url: URL of the prospect's website (for logging).
        prospect_name: Name of the prospect company (for logging).

    Returns:
        OutreachRecord documenting the send attempt.
    """
    record = OutreachRecord(
        prospect_url=prospect_url,
        prospect_name=prospect_name,
        recipient_email=to_address,
        email_subject=draft.subject,
        email_body=draft.body,
        status="pending",
    )

    # Build the email message
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{sender_name} <{gmail_address}>"
    msg["To"] = to_address
    msg["Subject"] = draft.subject

    # Plain text body
    msg.attach(MIMEText(draft.body, "plain"))

    # Attempt to send with retries
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Send attempt {attempt}/{MAX_RETRIES} to {to_address}...")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(gmail_address, gmail_app_password)
                server.send_message(msg)

            record.status = "sent"
            record.timestamp = datetime.now().isoformat()
            logger.info(f"Email sent successfully to {to_address}")
            _log_outreach(record)
            return record

        except smtplib.SMTPAuthenticationError as e:
            last_error = f"Authentication failed: {e}. Check your Gmail address and App Password."
            logger.error(last_error)
            break  # Don't retry auth failures
        except smtplib.SMTPRecipientsRefused as e:
            last_error = f"Recipient refused: {e}"
            logger.error(last_error)
            break  # Don't retry recipient errors
        except (smtplib.SMTPException, OSError) as e:
            last_error = f"SMTP error (attempt {attempt}): {e}"
            logger.warning(last_error)
            if attempt == MAX_RETRIES:
                break

    # If we got here, sending failed
    record.status = "failed"
    record.error_message = last_error
    record.timestamp = datetime.now().isoformat()
    _log_outreach(record)
    return record
