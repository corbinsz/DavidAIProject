"""
Agent Orchestrator
Orchestrates the full outreach pipeline:
URL Input -> Web Scraper -> LLM Analysis -> Email Draft -> Review/Confirm -> Gmail Send

Supports single URL and batch mode.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Callable

from src.scraper import scrape_website
from src.analyzer import analyze_prospect
from src.email_drafter import draft_email
from src.gmail_sender import send_email
from src.models import ScrapedWebsite, NeedAnalysis, EmailDraft, OutreachRecord

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the outreach agent."""
    anthropic_api_key: str
    gmail_address: str = ""
    gmail_app_password: str = ""
    sender_name: str = "The DAVID AI Team"
    tone: str = "professional"
    llm_model: str = "claude-sonnet-4-5-20250929"
    use_playwright: bool = True


@dataclass
class PipelineResult:
    """Result of a single pipeline run."""
    url: str
    scraped: Optional[ScrapedWebsite] = None
    analysis: Optional[NeedAnalysis] = None
    draft: Optional[EmailDraft] = None
    send_result: Optional[OutreachRecord] = None
    error: Optional[str] = None
    stage: str = "not_started"  # scraping, analyzing, drafting, reviewing, sending, complete, failed


class OutreachAgent:
    """
    AI-Powered Outreach Agent that automates the full prospecting pipeline.
    """

    def __init__(self, config: AgentConfig):
        self.config = config

    def scrape(self, url: str, progress_callback: Optional[Callable] = None) -> ScrapedWebsite:
        """Phase 1: Scrape the prospect's website."""
        return scrape_website(
            url=url,
            use_playwright_fallback=self.config.use_playwright,
            progress_callback=progress_callback,
        )

    def analyze(self, scraped: ScrapedWebsite) -> NeedAnalysis:
        """Phase 2: Analyze the prospect's needs via LLM."""
        return analyze_prospect(
            scraped=scraped,
            api_key=self.config.anthropic_api_key,
            model=self.config.llm_model,
        )

    def draft(self, analysis: NeedAnalysis) -> EmailDraft:
        """Phase 3: Draft a personalized outreach email."""
        return draft_email(
            analysis=analysis,
            api_key=self.config.anthropic_api_key,
            sender_name=self.config.sender_name,
            tone=self.config.tone,
            model=self.config.llm_model,
        )

    def send(
        self,
        draft: EmailDraft,
        to_address: str,
        prospect_url: str = "",
        prospect_name: str = "",
    ) -> OutreachRecord:
        """Phase 4: Send the email via Gmail."""
        return send_email(
            draft=draft,
            to_address=to_address,
            gmail_address=self.config.gmail_address,
            gmail_app_password=self.config.gmail_app_password,
            sender_name=self.config.sender_name,
            prospect_url=prospect_url,
            prospect_name=prospect_name,
        )

    def run_pipeline(
        self,
        url: str,
        to_address: str = "",
        auto_send: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> PipelineResult:
        """
        Run the full pipeline end-to-end for a single URL.

        Args:
            url: Prospect website URL.
            to_address: Recipient email (required if auto_send=True).
            auto_send: If True, sends without review. If False, stops at draft stage.
            progress_callback: Optional callable(message: str) for progress updates.

        Returns:
            PipelineResult with all intermediate data.
        """
        result = PipelineResult(url=url)

        def _log(msg: str):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        try:
            # Phase 1: Scrape
            result.stage = "scraping"
            _log(f"Phase 1: Scraping {url}...")
            result.scraped = self.scrape(url, progress_callback=progress_callback)

            if not result.scraped.pages:
                result.error = "Failed to scrape any content from the website."
                result.stage = "failed"
                return result

            # Phase 2: Analyze
            result.stage = "analyzing"
            _log("Phase 2: Analyzing prospect needs...")
            result.analysis = self.analyze(result.scraped)
            _log(f"Analysis complete: {result.analysis.company_name}")

            # Phase 3: Draft
            result.stage = "drafting"
            _log("Phase 3: Drafting outreach email...")
            result.draft = self.draft(result.analysis)
            _log(f"Draft ready: \"{result.draft.subject}\"")

            # Phase 4: Send (only if auto_send)
            if auto_send and to_address:
                result.stage = "sending"
                _log(f"Phase 4: Sending to {to_address}...")
                result.send_result = self.send(
                    draft=result.draft,
                    to_address=to_address,
                    prospect_url=url,
                    prospect_name=result.analysis.company_name,
                )
                if result.send_result.status == "sent":
                    result.stage = "complete"
                    _log("Email sent successfully!")
                else:
                    result.stage = "failed"
                    result.error = result.send_result.error_message
                    _log(f"Send failed: {result.error}")
            else:
                result.stage = "reviewing"
                _log("Pipeline paused for review. Approve to send.")

        except Exception as e:
            result.error = str(e)
            result.stage = "failed"
            logger.error(f"Pipeline error: {e}", exc_info=True)
            _log(f"Error: {e}")

        return result

    def run_batch(
        self,
        urls: list[str],
        progress_callback: Optional[Callable] = None,
    ) -> list[PipelineResult]:
        """
        Run the pipeline for multiple URLs (batch mode).
        Stops at draft stage for each—does not auto-send.
        """
        results = []
        for i, url in enumerate(urls, 1):
            if progress_callback:
                progress_callback(f"\n--- Processing {i}/{len(urls)}: {url} ---")
            result = self.run_pipeline(url=url, progress_callback=progress_callback)
            results.append(result)
        return results
