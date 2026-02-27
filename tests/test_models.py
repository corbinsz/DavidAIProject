"""Tests for Pydantic data models."""

import pytest
from src.models import ScrapedPage, ScrapedWebsite, NeedAnalysis, EmailDraft, OutreachRecord


class TestScrapedPage:
    def test_minimal(self):
        page = ScrapedPage(url="https://example.com")
        assert page.url == "https://example.com"
        assert page.title == ""
        assert page.content == ""
        assert page.page_type == "unknown"

    def test_full(self):
        page = ScrapedPage(
            url="https://example.com/about",
            title="About Us",
            content="We are a company.",
            page_type="about",
        )
        assert page.page_type == "about"
        assert "company" in page.content


class TestScrapedWebsite:
    def test_empty(self):
        site = ScrapedWebsite(base_url="https://example.com")
        assert site.pages == []
        assert site.company_name == ""
        assert site.raw_text_summary == ""

    def test_with_pages(self):
        pages = [ScrapedPage(url="https://example.com", content="Hello")]
        site = ScrapedWebsite(
            base_url="https://example.com",
            company_name="Example",
            pages=pages,
            raw_text_summary="Hello",
        )
        assert len(site.pages) == 1
        assert site.company_name == "Example"


class TestNeedAnalysis:
    def test_required_fields(self):
        analysis = NeedAnalysis(
            company_name="Acme",
            company_summary="A widgets company",
            industry="Manufacturing",
        )
        assert analysis.company_name == "Acme"
        assert analysis.services_offered == []
        assert analysis.pain_points == []
        assert analysis.ai_opportunities == []

    def test_full(self):
        analysis = NeedAnalysis(
            company_name="Acme",
            company_summary="They make widgets",
            industry="Manufacturing",
            services_offered=["Widget design", "Widget sales"],
            pain_points=["Manual QA", "Slow logistics"],
            ai_opportunities=["Automated inspection", "Route optimization"],
            value_proposition="AI-powered QA",
            recommended_angle="Quality control automation",
        )
        assert len(analysis.pain_points) == 2
        assert analysis.recommended_angle == "Quality control automation"


class TestEmailDraft:
    def test_defaults(self):
        draft = EmailDraft(subject="Hello", body="World")
        assert draft.tone == "professional"
        assert draft.to_address == ""

    def test_full(self):
        draft = EmailDraft(
            subject="Quick question",
            body="Hi there...",
            to_address="test@example.com",
            tone="bold",
        )
        assert draft.tone == "bold"


class TestOutreachRecord:
    def test_auto_timestamp(self):
        record = OutreachRecord(
            prospect_url="https://example.com",
            prospect_name="Example",
            recipient_email="test@example.com",
            email_subject="Hi",
            email_body="Hello",
        )
        assert record.timestamp  # auto-generated
        assert record.status == "drafted"
        assert record.error_message is None

    def test_failed_record(self):
        record = OutreachRecord(
            prospect_url="https://example.com",
            prospect_name="Example",
            recipient_email="test@example.com",
            email_subject="Hi",
            email_body="Hello",
            status="failed",
            error_message="SMTP timeout",
        )
        assert record.status == "failed"
        assert record.error_message == "SMTP timeout"
