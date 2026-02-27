"""Tests for the web scraping module."""

import pytest
from unittest.mock import patch, MagicMock

from src.scraper import (
    _extract_text,
    _extract_title,
    _extract_company_name,
    _extract_emails,
    _discover_links,
    _fetch_page,
    scrape_website,
    MAX_CONTENT_LENGTH,
)


# --- Sample HTML fixtures ---

SAMPLE_HTML = """
<html>
<head><title>Acme Corp - Building the Future</title>
<meta property="og:site_name" content="Acme Corp"/>
</head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<main>
<h1>Welcome to Acme Corp</h1>
<p>We build innovative solutions for modern businesses.</p>
<p>Our team of experts delivers world-class engineering.</p>
</main>
<footer>Copyright 2024</footer>
<script>var x = 1;</script>
</body>
</html>
"""

LINKS_HTML = """
<html><body>
<a href="/about">About Us</a>
<a href="/services">Our Services</a>
<a href="/blog">Blog</a>
<a href="/contact">Contact</a>
<a href="https://external.com/page">External Link</a>
<a href="mailto:info@acme.com">Email</a>
<a href="#section">Anchor</a>
</body></html>
"""


class TestExtractText:
    def test_strips_scripts_and_nav(self):
        text = _extract_text(SAMPLE_HTML)
        assert "var x = 1" not in text
        assert "Copyright 2024" not in text  # footer stripped
        assert "Welcome to Acme Corp" in text

    def test_preserves_content(self):
        text = _extract_text(SAMPLE_HTML)
        assert "innovative solutions" in text
        assert "world-class engineering" in text

    def test_strips_short_lines(self):
        html = "<html><body><p>OK</p><p>A</p><p>This is real content here</p></body></html>"
        text = _extract_text(html)
        # Lines with len <= 2 are removed
        assert "This is real content here" in text

    def test_truncates_long_content(self):
        long_html = f"<html><body><p>{'x' * (MAX_CONTENT_LENGTH + 1000)}</p></body></html>"
        text = _extract_text(long_html)
        assert len(text) <= MAX_CONTENT_LENGTH + 50  # allow for truncation message
        assert "truncated" in text


class TestExtractTitle:
    def test_from_title_tag(self):
        title = _extract_title(SAMPLE_HTML)
        assert title == "Acme Corp - Building the Future"

    def test_fallback_to_h1(self):
        html = "<html><body><h1>My Page</h1></body></html>"
        title = _extract_title(html)
        assert title == "My Page"

    def test_empty_when_nothing(self):
        html = "<html><body><p>Just text</p></body></html>"
        title = _extract_title(html)
        assert title == ""


class TestExtractCompanyName:
    def test_from_og_site_name(self):
        name = _extract_company_name(SAMPLE_HTML, "https://acme.com")
        assert name == "Acme Corp"

    def test_from_title_with_separator(self):
        html = '<html><head><title>BigCo | Enterprise Solutions</title></head></html>'
        name = _extract_company_name(html, "https://bigco.com")
        assert name == "BigCo"

    def test_fallback_to_domain(self):
        html = "<html><body></body></html>"
        name = _extract_company_name(html, "https://www.coolstartup.io")
        assert name == "Coolstartup"


class TestDiscoverLinks:
    def test_finds_internal_links(self):
        links = _discover_links(LINKS_HTML, "https://acme.com")
        urls = [url for url, _ in links]
        assert "https://acme.com/about" in urls
        assert "https://acme.com/services" in urls
        assert "https://acme.com/blog" in urls
        assert "https://acme.com/contact" in urls

    def test_excludes_external(self):
        links = _discover_links(LINKS_HTML, "https://acme.com")
        urls = [url for url, _ in links]
        assert not any("external.com" in u for u in urls)

    def test_excludes_mailto_and_anchors(self):
        links = _discover_links(LINKS_HTML, "https://acme.com")
        urls = [url for url, _ in links]
        assert not any("mailto:" in u for u in urls)
        assert not any(u == "#section" for u in urls)

    def test_assigns_page_types(self):
        links = _discover_links(LINKS_HTML, "https://acme.com")
        types = {url: ptype for url, ptype in links}
        assert types.get("https://acme.com/about") == "about"
        assert types.get("https://acme.com/services") == "services"
        assert types.get("https://acme.com/blog") == "blog"


class TestFetchPage:
    def test_success(self):
        session = MagicMock()
        response = MagicMock()
        response.text = "<html>OK</html>"
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        result = _fetch_page("https://example.com", session)
        assert result == "<html>OK</html>"

    def test_non_html_returns_none(self):
        session = MagicMock()
        response = MagicMock()
        response.headers = {"Content-Type": "application/pdf"}
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        result = _fetch_page("https://example.com/file.pdf", session)
        assert result is None

    def test_timeout_returns_none(self):
        import requests
        session = MagicMock()
        session.get.side_effect = requests.exceptions.Timeout("timed out")

        result = _fetch_page("https://slow.com", session)
        assert result is None

    def test_http_error_returns_none(self):
        import requests
        session = MagicMock()
        session.get.side_effect = requests.exceptions.HTTPError("404")

        result = _fetch_page("https://example.com/404", session)
        assert result is None


class TestScrapeWebsite:
    @patch("src.scraper._fetch_page")
    @patch("src.scraper._try_playwright_fetch")
    @patch("src.scraper.time.sleep")
    def test_basic_scrape(self, mock_sleep, mock_pw, mock_fetch):
        mock_pw.return_value = None
        mock_fetch.return_value = SAMPLE_HTML

        result = scrape_website("https://acme.com", use_playwright_fallback=False)

        assert result.base_url == "https://acme.com"
        assert result.company_name == "Acme Corp"
        assert len(result.pages) >= 1
        assert result.pages[0].page_type == "homepage"

    @patch("src.scraper._fetch_page")
    @patch("src.scraper.time.sleep")
    def test_url_normalization(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML

        result = scrape_website("acme.com/", use_playwright_fallback=False)
        assert result.base_url == "https://acme.com"

    @patch("src.scraper._fetch_page")
    @patch("src.scraper.time.sleep")
    def test_empty_when_fetch_fails(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = None

        result = scrape_website("https://down.com", use_playwright_fallback=False)
        assert result.pages == []

    @patch("src.scraper._fetch_page")
    @patch("src.scraper.time.sleep")
    def test_progress_callback(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        messages = []

        result = scrape_website(
            "https://acme.com",
            use_playwright_fallback=False,
            progress_callback=messages.append,
        )
        assert any("Starting scrape" in m for m in messages)
        assert any("Homepage scraped" in m for m in messages)


class TestExtractEmails:
    def test_finds_mailto_links(self):
        html = """
        <html><body>
        <a href="mailto:sales@acme.com">Email us</a>
        <a href="mailto:support@acme.com?subject=Hello">Support</a>
        <p>Contact us today!</p>
        </body></html>
        """
        emails = _extract_emails(html)
        assert "sales@acme.com" in emails
        assert "support@acme.com" in emails

    def test_finds_text_emails(self):
        html = """
        <html><body>
        <p>Reach out at info@company.org or call us.</p>
        <p>Our CEO is at ceo@company.org</p>
        </body></html>
        """
        emails = _extract_emails(html)
        assert "info@company.org" in emails
        assert "ceo@company.org" in emails

    def test_deduplicates(self):
        html = """
        <html><body>
        <a href="mailto:hello@firm.com">Email</a>
        <p>Write to hello@firm.com for info.</p>
        </body></html>
        """
        emails = _extract_emails(html)
        assert emails.count("hello@firm.com") == 1

    def test_filters_junk_emails(self):
        html = """
        <html><body>
        <a href="mailto:noreply@acme.com">Don't reply</a>
        <a href="mailto:no-reply@acme.com">No reply</a>
        <p>test@example.com user@test.com icon@2x.png</p>
        <a href="mailto:real@acme.com">Contact</a>
        </body></html>
        """
        emails = _extract_emails(html)
        assert "real@acme.com" in emails
        assert "noreply@acme.com" not in emails
        assert "no-reply@acme.com" not in emails
        assert "test@example.com" not in emails
        assert "user@test.com" not in emails
        assert "icon@2x.png" not in emails

    def test_empty_when_no_emails(self):
        html = "<html><body><p>No contact info here.</p></body></html>"
        emails = _extract_emails(html)
        assert emails == []
