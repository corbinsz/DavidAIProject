"""
Web Scraping Module
Accepts a URL, discovers key pages (about, services, blog),
extracts and cleans HTML into structured text content.
"""

import time
import logging
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.models import ScrapedPage, ScrapedWebsite

logger = logging.getLogger(__name__)

# Keywords that indicate important pages to scrape
PAGE_KEYWORDS = {
    "about": "about",
    "services": "services",
    "solutions": "services",
    "products": "services",
    "offerings": "services",
    "what-we-do": "services",
    "blog": "blog",
    "news": "blog",
    "insights": "blog",
    "contact": "contact",
    "team": "about",
    "careers": "about",
    "case-studies": "services",
    "portfolio": "services",
    "pricing": "services",
    "faq": "services",
}

# Elements to strip from HTML before text extraction
STRIP_ELEMENTS = [
    "script", "style", "nav", "footer", "header", "noscript",
    "iframe", "svg", "form", "button",
]

# Default headers to mimic a browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 1.0  # seconds between requests
MAX_PAGES = 8  # max pages to scrape per site
MAX_CONTENT_LENGTH = 5000  # max chars per page to keep


def _fetch_page(url: str, session: requests.Session) -> Optional[str]:
    """Fetch a single page's HTML content with error handling."""
    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            logger.warning(f"Skipping non-HTML content at {url}: {content_type}")
            return None

        return response.text
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None


def _extract_text(html: str) -> str:
    """Clean HTML and extract readable text content."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted elements
    for tag_name in STRIP_ELEMENTS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Get text with spacing
    text = soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace / blank lines
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    # Collapse runs of very short lines (likely nav remnants)
    cleaned = []
    for line in lines:
        if len(line) > 2:
            cleaned.append(line)

    text = "\n".join(cleaned)

    # Truncate if too long
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n... [content truncated]"

    return text


def _extract_title(html: str) -> str:
    """Extract the page title from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return title_tag.string.strip()

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    return ""


def _extract_company_name(html: str, url: str) -> str:
    """Try to extract the company name from the homepage."""
    soup = BeautifulSoup(html, "html.parser")

    # Check meta tags
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        return og_site["content"].strip()

    # Check title tag (often "Company Name - tagline")
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()
        # Split on common separators
        for sep in [" | ", " - ", " — ", " – ", " :: "]:
            if sep in title:
                return title.split(sep)[0].strip()
        return title

    # Fallback to domain name
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    return domain.split(".")[0].capitalize()


def _discover_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """
    Discover important internal links from the homepage.
    Returns list of (url, page_type) tuples.
    """
    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()

    discovered = {}

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        # Skip empty, anchors, mailto, tel, javascript
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only follow internal links
        if parsed.netloc.lower() != base_domain:
            continue

        # Check path against keywords
        path_lower = parsed.path.lower().rstrip("/")
        link_text = a_tag.get_text(strip=True).lower()

        for keyword, page_type in PAGE_KEYWORDS.items():
            if keyword in path_lower or keyword in link_text:
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                clean_url = clean_url.rstrip("/")
                if clean_url not in discovered and clean_url != base_url.rstrip("/"):
                    discovered[clean_url] = page_type
                break

    return list(discovered.items())[:MAX_PAGES - 1]  # -1 for homepage


def _try_playwright_fetch(url: str) -> Optional[str]:
    """Fallback: use Playwright for JavaScript-rendered pages."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=20000)
            html = page.content()
            browser.close()
            return html
    except ImportError:
        logger.info("Playwright not installed, skipping JS rendering fallback")
        return None
    except Exception as e:
        logger.warning(f"Playwright fallback failed for {url}: {e}")
        return None


def scrape_website(url: str, use_playwright_fallback: bool = True, progress_callback=None) -> ScrapedWebsite:
    """
    Main scraping function. Accepts a URL and returns structured website data.

    Args:
        url: The target website URL to scrape.
        use_playwright_fallback: Whether to try Playwright if requests gets thin content.
        progress_callback: Optional callable(message: str) for progress updates.

    Returns:
        ScrapedWebsite with all discovered and scraped pages.
    """
    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    url = url.rstrip("/")

    def _log(msg: str):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _log(f"Starting scrape of {url}")

    session = requests.Session()
    pages = []

    # --- Scrape homepage ---
    _log("Fetching homepage...")
    homepage_html = _fetch_page(url, session)

    if not homepage_html and use_playwright_fallback:
        _log("Trying Playwright fallback for homepage...")
        homepage_html = _try_playwright_fetch(url)

    if not homepage_html:
        _log("Failed to fetch homepage. Returning empty result.")
        return ScrapedWebsite(base_url=url)

    homepage_text = _extract_text(homepage_html)
    company_name = _extract_company_name(homepage_html, url)

    # Check if content is too thin (might be JS-rendered)
    if len(homepage_text) < 100 and use_playwright_fallback:
        _log("Homepage content is thin, trying Playwright fallback...")
        pw_html = _try_playwright_fetch(url)
        if pw_html:
            pw_text = _extract_text(pw_html)
            if len(pw_text) > len(homepage_text):
                homepage_html = pw_html
                homepage_text = pw_text
                company_name = _extract_company_name(pw_html, url)

    pages.append(ScrapedPage(
        url=url,
        title=_extract_title(homepage_html),
        content=homepage_text,
        page_type="homepage",
    ))
    _log(f"Homepage scraped: {len(homepage_text)} chars")

    # --- Discover and scrape linked pages ---
    linked_pages = _discover_links(homepage_html, url)
    _log(f"Discovered {len(linked_pages)} internal pages to scrape")

    for page_url, page_type in linked_pages:
        time.sleep(RATE_LIMIT_DELAY)
        _log(f"Fetching {page_type} page: {page_url}")

        html = _fetch_page(page_url, session)
        if not html:
            continue

        text = _extract_text(html)
        if len(text) < 30:
            _log(f"Skipping thin page: {page_url}")
            continue

        pages.append(ScrapedPage(
            url=page_url,
            title=_extract_title(html),
            content=text,
            page_type=page_type,
        ))
        _log(f"Scraped {page_type}: {len(text)} chars")

    # --- Build combined summary ---
    summary_parts = []
    for page in pages:
        summary_parts.append(f"=== {page.page_type.upper()}: {page.title} ===\n{page.content}")

    raw_summary = "\n\n".join(summary_parts)

    result = ScrapedWebsite(
        base_url=url,
        company_name=company_name,
        pages=pages,
        raw_text_summary=raw_summary,
    )

    _log(f"Scraping complete: {len(pages)} pages, {len(raw_summary)} total chars")
    return result
