"""Tests for the Gmail sending module."""

import json
import smtplib
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.gmail_sender import send_email, get_outreach_log, _log_outreach
from src.models import EmailDraft, OutreachRecord


def _make_draft() -> EmailDraft:
    return EmailDraft(subject="Test Subject", body="Test body content", tone="professional")


class TestSendEmail:
    @patch("src.gmail_sender._log_outreach")
    @patch("src.gmail_sender.smtplib.SMTP")
    def test_successful_send(self, mock_smtp_cls, mock_log):
        server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            draft=_make_draft(),
            to_address="recipient@example.com",
            gmail_address="sender@gmail.com",
            gmail_app_password="abcdefghijklmnop",
            sender_name="Test Sender",
            prospect_url="https://example.com",
            prospect_name="Example",
        )

        assert result.status == "sent"
        assert result.recipient_email == "recipient@example.com"
        assert result.email_subject == "Test Subject"
        mock_log.assert_called_once()

    @patch("src.gmail_sender._log_outreach")
    @patch("src.gmail_sender.smtplib.SMTP")
    def test_auth_failure_no_retry(self, mock_smtp_cls, mock_log):
        server = MagicMock()
        server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            draft=_make_draft(),
            to_address="recipient@example.com",
            gmail_address="sender@gmail.com",
            gmail_app_password="wrongpassword",
        )

        assert result.status == "failed"
        assert "Authentication" in result.error_message
        # Auth failures should NOT retry — only 1 SMTP connection
        assert mock_smtp_cls.call_count == 1

    @patch("src.gmail_sender._log_outreach")
    @patch("src.gmail_sender.smtplib.SMTP")
    def test_recipient_refused_no_retry(self, mock_smtp_cls, mock_log):
        server = MagicMock()
        server.send_message.side_effect = smtplib.SMTPRecipientsRefused({"bad@x.com": (550, b"No such user")})
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            draft=_make_draft(),
            to_address="bad@x.com",
            gmail_address="sender@gmail.com",
            gmail_app_password="abcdefghijklmnop",
        )

        assert result.status == "failed"
        assert "refused" in result.error_message.lower()
        assert mock_smtp_cls.call_count == 1

    @patch("src.gmail_sender._log_outreach")
    @patch("src.gmail_sender.smtplib.SMTP")
    def test_transient_error_retries(self, mock_smtp_cls, mock_log):
        server = MagicMock()
        server.send_message.side_effect = [
            smtplib.SMTPException("Temporary failure"),
            smtplib.SMTPException("Temporary failure"),
            None,  # succeeds on 3rd try
        ]
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            draft=_make_draft(),
            to_address="recipient@example.com",
            gmail_address="sender@gmail.com",
            gmail_app_password="abcdefghijklmnop",
        )

        assert result.status == "sent"
        assert mock_smtp_cls.call_count == 3  # retried


class TestOutreachLog:
    def test_log_and_read(self, tmp_path):
        log_file = tmp_path / "outreach_log.json"

        with patch("src.gmail_sender.LOG_DIR", tmp_path):
            record = OutreachRecord(
                prospect_url="https://example.com",
                prospect_name="Example",
                recipient_email="test@example.com",
                email_subject="Hi",
                email_body="Hello",
                status="sent",
            )
            _log_outreach(record)

            records = get_outreach_log()

        assert len(records) == 1
        assert records[0].status == "sent"
        assert records[0].prospect_name == "Example"

    def test_empty_log_returns_empty(self, tmp_path):
        with patch("src.gmail_sender.LOG_DIR", tmp_path):
            records = get_outreach_log()
        assert records == []

    def test_corrupt_log_returns_empty(self, tmp_path):
        log_file = tmp_path / "outreach_log.json"
        log_file.write_text("not valid json{{{")

        with patch("src.gmail_sender.LOG_DIR", tmp_path):
            records = get_outreach_log()
        assert records == []
