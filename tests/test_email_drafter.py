"""Tests for the email drafting module."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.email_drafter import draft_email, TONE_DESCRIPTIONS, EMAIL_SYSTEM_PROMPT
from src.models import NeedAnalysis, EmailDraft


VALID_DRAFT_JSON = json.dumps({
    "subject": "Quick question about your QA process",
    "body": "Hi there,\n\nI noticed Acme's focus on precision manufacturing...\n\nBest,\nThe DAVID AI Team",
})


def _make_analysis() -> NeedAnalysis:
    return NeedAnalysis(
        company_name="Acme Corp",
        company_summary="Widgets for enterprise",
        industry="Manufacturing",
        services_offered=["Widget Design"],
        pain_points=["Manual QA"],
        ai_opportunities=["Automated inspection"],
        value_proposition="AI-powered QA",
        recommended_angle="Quality control",
    )


def _mock_claude_response(text: str):
    message = MagicMock()
    block = MagicMock()
    block.text = text
    message.content = [block]
    return message


class TestDraftEmail:
    @patch("src.email_drafter.anthropic.Anthropic")
    def test_valid_response(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response(VALID_DRAFT_JSON)
        mock_client_cls.return_value = client

        result = draft_email(_make_analysis(), api_key="test-key")

        assert isinstance(result, EmailDraft)
        assert "QA" in result.subject
        assert "Acme" in result.body

    @patch("src.email_drafter.anthropic.Anthropic")
    def test_markdown_wrapped_response(self, mock_client_cls):
        client = MagicMock()
        wrapped = f"```json\n{VALID_DRAFT_JSON}\n```"
        client.messages.create.return_value = _mock_claude_response(wrapped)
        mock_client_cls.return_value = client

        result = draft_email(_make_analysis(), api_key="test-key")
        assert result.subject  # parsed successfully

    @patch("src.email_drafter.anthropic.Anthropic")
    def test_tone_passed_to_prompt(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response(VALID_DRAFT_JSON)
        mock_client_cls.return_value = client

        draft_email(_make_analysis(), api_key="test-key", tone="bold")

        call_kwargs = client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "bold" in user_msg.lower()

    @patch("src.email_drafter.anthropic.Anthropic")
    def test_sender_name_in_prompt(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response(VALID_DRAFT_JSON)
        mock_client_cls.return_value = client

        draft_email(_make_analysis(), api_key="test-key", sender_name="Jane from DAVID AI")

        call_kwargs = client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "Jane from DAVID AI" in user_msg

    @patch("src.email_drafter.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("Not valid JSON")
        mock_client_cls.return_value = client

        with pytest.raises(ValueError, match="LLM did not return valid JSON"):
            draft_email(_make_analysis(), api_key="test-key")

    @patch("src.email_drafter.time.sleep")
    @patch("src.email_drafter.anthropic.Anthropic")
    def test_retries_on_rate_limit(self, mock_client_cls, mock_sleep):
        import anthropic as anthropic_mod

        client = MagicMock()
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {}

        client.messages.create.side_effect = [
            anthropic_mod.RateLimitError(
                message="rate limited",
                response=error_response,
                body=None,
            ),
            _mock_claude_response(VALID_DRAFT_JSON),
        ]
        mock_client_cls.return_value = client

        result = draft_email(_make_analysis(), api_key="test-key")
        assert result.subject
        assert client.messages.create.call_count == 2


class TestToneDescriptions:
    def test_all_tones_exist(self):
        for tone in ["professional", "conversational", "bold", "consultative"]:
            assert tone in TONE_DESCRIPTIONS
            assert len(TONE_DESCRIPTIONS[tone]) > 10

    def test_system_prompt_mentions_david_ai(self):
        assert "DAVID AI" in EMAIL_SYSTEM_PROMPT
        assert "200 words" in EMAIL_SYSTEM_PROMPT or "concise" in EMAIL_SYSTEM_PROMPT.lower()
