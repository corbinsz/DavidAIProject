"""Tests for the pipeline orchestrator."""

import pytest
from unittest.mock import patch, MagicMock

from src.agent import OutreachAgent, AgentConfig, PipelineResult
from src.models import ScrapedWebsite, ScrapedPage, NeedAnalysis, EmailDraft, OutreachRecord


def _make_config() -> AgentConfig:
    return AgentConfig(
        anthropic_api_key="test-key",
        gmail_address="sender@gmail.com",
        gmail_app_password="abcdefghijklmnop",
    )


def _make_scraped() -> ScrapedWebsite:
    return ScrapedWebsite(
        base_url="https://acme.com",
        company_name="Acme",
        pages=[ScrapedPage(url="https://acme.com", content="Acme builds widgets.", page_type="homepage")],
        raw_text_summary="Acme builds widgets.",
    )


def _make_analysis() -> NeedAnalysis:
    return NeedAnalysis(
        company_name="Acme Corp",
        company_summary="Widgets for enterprise",
        industry="Manufacturing",
        pain_points=["Manual QA"],
        ai_opportunities=["Automated inspection"],
        value_proposition="AI-powered QA",
        recommended_angle="Quality control",
    )


def _make_draft() -> EmailDraft:
    return EmailDraft(subject="Quick question", body="Hi there...")


class TestOutreachAgent:
    @patch("src.agent.send_email")
    @patch("src.agent.draft_email")
    @patch("src.agent.analyze_prospect")
    @patch("src.agent.scrape_website")
    def test_full_pipeline(self, mock_scrape, mock_analyze, mock_draft, mock_send):
        mock_scrape.return_value = _make_scraped()
        mock_analyze.return_value = _make_analysis()
        mock_draft.return_value = _make_draft()

        agent = OutreachAgent(_make_config())
        result = agent.run_pipeline(url="https://acme.com")

        assert result.stage == "reviewing"  # stops at review by default
        assert result.scraped is not None
        assert result.analysis.company_name == "Acme Corp"
        assert result.draft.subject == "Quick question"
        assert result.error is None

    @patch("src.agent.scrape_website")
    def test_empty_scrape_fails(self, mock_scrape):
        mock_scrape.return_value = ScrapedWebsite(base_url="https://down.com", pages=[])

        agent = OutreachAgent(_make_config())
        result = agent.run_pipeline(url="https://down.com")

        assert result.stage == "failed"
        assert "Failed to scrape" in result.error

    @patch("src.agent.draft_email")
    @patch("src.agent.analyze_prospect")
    @patch("src.agent.scrape_website")
    def test_analysis_exception(self, mock_scrape, mock_analyze, mock_draft):
        mock_scrape.return_value = _make_scraped()
        mock_analyze.side_effect = ValueError("Bad LLM response")

        agent = OutreachAgent(_make_config())
        result = agent.run_pipeline(url="https://acme.com")

        assert result.stage == "failed"
        assert "Bad LLM response" in result.error

    @patch("src.agent.send_email")
    @patch("src.agent.draft_email")
    @patch("src.agent.analyze_prospect")
    @patch("src.agent.scrape_website")
    def test_auto_send(self, mock_scrape, mock_analyze, mock_draft, mock_send):
        mock_scrape.return_value = _make_scraped()
        mock_analyze.return_value = _make_analysis()
        mock_draft.return_value = _make_draft()
        mock_send.return_value = OutreachRecord(
            prospect_url="https://acme.com",
            prospect_name="Acme Corp",
            recipient_email="test@acme.com",
            email_subject="Quick question",
            email_body="Hi there...",
            status="sent",
        )

        agent = OutreachAgent(_make_config())
        result = agent.run_pipeline(
            url="https://acme.com",
            to_address="test@acme.com",
            auto_send=True,
        )

        assert result.stage == "complete"
        assert result.send_result.status == "sent"

    @patch("src.agent.draft_email")
    @patch("src.agent.analyze_prospect")
    @patch("src.agent.scrape_website")
    def test_progress_callback(self, mock_scrape, mock_analyze, mock_draft):
        mock_scrape.return_value = _make_scraped()
        mock_analyze.return_value = _make_analysis()
        mock_draft.return_value = _make_draft()

        messages = []
        agent = OutreachAgent(_make_config())
        agent.run_pipeline(url="https://acme.com", progress_callback=messages.append)

        assert any("Phase 1" in m for m in messages)
        assert any("Phase 2" in m for m in messages)
        assert any("Phase 3" in m for m in messages)

    @patch("src.agent.draft_email")
    @patch("src.agent.analyze_prospect")
    @patch("src.agent.scrape_website")
    def test_batch_mode(self, mock_scrape, mock_analyze, mock_draft):
        mock_scrape.return_value = _make_scraped()
        mock_analyze.return_value = _make_analysis()
        mock_draft.return_value = _make_draft()

        agent = OutreachAgent(_make_config())
        results = agent.run_batch(urls=["https://a.com", "https://b.com"])

        assert len(results) == 2
        assert all(r.stage == "reviewing" for r in results)

    @patch("src.agent.scrape_website")
    def test_batch_isolates_failures(self, mock_scrape):
        """One URL failing should not stop the batch."""
        mock_scrape.side_effect = [
            ScrapedWebsite(base_url="https://a.com", pages=[]),  # fails
            _make_scraped(),  # this won't reach analyze since we only mock scrape
        ]

        agent = OutreachAgent(_make_config())

        with patch("src.agent.analyze_prospect", return_value=_make_analysis()), \
             patch("src.agent.draft_email", return_value=_make_draft()):
            results = agent.run_batch(urls=["https://a.com", "https://b.com"])

        assert len(results) == 2
        assert results[0].stage == "failed"  # first URL failed
