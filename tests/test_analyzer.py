"""Tests for the LLM analysis module."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.analyzer import analyze_prospect, ANALYSIS_SYSTEM_PROMPT
from src.models import ScrapedWebsite, ScrapedPage, NeedAnalysis


VALID_ANALYSIS_JSON = json.dumps({
    "company_name": "Acme Corp",
    "company_summary": "Acme builds widgets for enterprise clients.",
    "industry": "Manufacturing",
    "services_offered": ["Widget Design", "Custom Fabrication"],
    "pain_points": ["Manual quality inspection", "Slow order processing"],
    "ai_opportunities": ["Automated visual QA", "Order routing optimization"],
    "value_proposition": "DAVID AI can automate Acme's QA pipeline.",
    "recommended_angle": "Quality control automation",
})


def _make_scraped(content: str = "Acme builds widgets.") -> ScrapedWebsite:
    return ScrapedWebsite(
        base_url="https://acme.com",
        company_name="Acme",
        pages=[ScrapedPage(url="https://acme.com", content=content, page_type="homepage")],
        raw_text_summary=content,
    )


def _mock_claude_response(text: str):
    """Create a mock Anthropic messages.create response."""
    message = MagicMock()
    block = MagicMock()
    block.text = text
    message.content = [block]
    return message


class TestAnalyzeProspect:
    @patch("src.analyzer.anthropic.Anthropic")
    def test_valid_json_response(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response(VALID_ANALYSIS_JSON)
        mock_client_cls.return_value = client

        result = analyze_prospect(_make_scraped(), api_key="test-key")

        assert isinstance(result, NeedAnalysis)
        assert result.company_name == "Acme Corp"
        assert result.industry == "Manufacturing"
        assert len(result.pain_points) == 2
        assert len(result.ai_opportunities) == 2

    @patch("src.analyzer.anthropic.Anthropic")
    def test_markdown_wrapped_json(self, mock_client_cls):
        """Claude sometimes wraps JSON in ```json ... ``` blocks."""
        client = MagicMock()
        wrapped = f"```json\n{VALID_ANALYSIS_JSON}\n```"
        client.messages.create.return_value = _mock_claude_response(wrapped)
        mock_client_cls.return_value = client

        result = analyze_prospect(_make_scraped(), api_key="test-key")
        assert result.company_name == "Acme Corp"

    @patch("src.analyzer.anthropic.Anthropic")
    def test_lenient_json_parsing(self, mock_client_cls):
        """JSON preceded by extra text should still parse via fallback."""
        client = MagicMock()
        messy = f"Here is the analysis:\n{VALID_ANALYSIS_JSON}\nDone."
        client.messages.create.return_value = _mock_claude_response(messy)
        mock_client_cls.return_value = client

        result = analyze_prospect(_make_scraped(), api_key="test-key")
        assert result.company_name == "Acme Corp"

    @patch("src.analyzer.anthropic.Anthropic")
    def test_content_truncation(self, mock_client_cls):
        """Content longer than 15000 chars should be truncated before sending."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response(VALID_ANALYSIS_JSON)
        mock_client_cls.return_value = client

        long_content = "x" * 20000
        analyze_prospect(_make_scraped(content=long_content), api_key="test-key")

        # Check that the content sent to Claude was truncated
        call_kwargs = client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "truncated" in user_msg

    @patch("src.analyzer.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_client_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("This is not JSON at all.")
        mock_client_cls.return_value = client

        with pytest.raises(ValueError, match="LLM did not return valid JSON"):
            analyze_prospect(_make_scraped(), api_key="test-key")

    @patch("src.analyzer.time.sleep")
    @patch("src.analyzer.anthropic.Anthropic")
    def test_retries_on_rate_limit(self, mock_client_cls, mock_sleep):
        """Should retry on RateLimitError and succeed on second attempt."""
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
            _mock_claude_response(VALID_ANALYSIS_JSON),
        ]
        mock_client_cls.return_value = client

        result = analyze_prospect(_make_scraped(), api_key="test-key")
        assert result.company_name == "Acme Corp"
        assert client.messages.create.call_count == 2

    def test_system_prompt_mentions_david_ai(self):
        assert "DAVID AI" in ANALYSIS_SYSTEM_PROMPT
        assert "pain" in ANALYSIS_SYSTEM_PROMPT.lower() or "opportunities" in ANALYSIS_SYSTEM_PROMPT.lower() or "analyst" in ANALYSIS_SYSTEM_PROMPT.lower()
