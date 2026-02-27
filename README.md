# DAVID AI Outreach Agent

An AI-powered outreach agent that automates prospecting by scraping a prospect's website, analyzing their business needs and pain points, drafting a personalized outreach email, and sending it via Gmail — all in one end-to-end pipeline.

Built as a Round 2 interview project for [DAVID AI](https://getdavid.ai/).

---

## Architecture

```
URL Input → Web Scraper → LLM Analysis → Email Draft → Review/Confirm → Gmail Send
```

| Component        | Technology                                       |
|------------------|--------------------------------------------------|
| Language         | Python 3.10+                                     |
| Web Scraping     | BeautifulSoup4 + Requests (Playwright fallback)  |
| LLM              | Anthropic Claude (via `anthropic` SDK)            |
| Email Sending    | Gmail SMTP with App Password                     |
| Interface        | Streamlit web UI                                 |
| Data Models      | Pydantic v2                                      |
| Testing          | pytest (69 tests across 6 modules)               |

### Project Structure

```
DavidAIProject/
├── app.py                  # Streamlit UI (main entry point)
├── src/
│   ├── scraper.py          # Web scraping: URL → structured content
│   ├── analyzer.py         # LLM analysis: content → pain points & opportunities
│   ├── email_drafter.py    # Email generation: analysis → personalized email
│   ├── gmail_sender.py     # Gmail SMTP: draft → sent email + CRM logging
│   ├── agent.py            # Pipeline orchestrator (single + batch mode)
│   └── models.py           # Pydantic data models shared across modules
├── tests/
│   ├── test_models.py      # Model validation tests
│   ├── test_scraper.py     # Scraping, extraction, link discovery tests
│   ├── test_analyzer.py    # LLM analysis + JSON parsing tests
│   ├── test_email_drafter.py  # Email drafting + tone tests
│   ├── test_gmail_sender.py   # SMTP send, retry logic, logging tests
│   └── test_agent.py       # Pipeline orchestration + batch tests
├── logs/                   # CRM-style outreach log (generated at runtime)
├── .streamlit/config.toml  # Streamlit theme configuration
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/DavidAIProject.git
cd DavidAIProject
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
ANTHROPIC_API_KEY=sk-ant-...your-key-here
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
SENDER_NAME=Your Name
```

#### Getting a Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to **App passwords** (search "app passwords" in account settings)
4. Generate a new app password for "Mail"
5. Copy the 16-character password into your `.env` file

### 5. Run the App

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### 6. Run Tests

```bash
pytest tests/ -v
```

All 69 tests should pass. Tests use mocks — no API keys or network needed.

---

## How It Works

### Phase 1: Web Scraping (`src/scraper.py`)
- Fetches the homepage and discovers internal pages (About, Services, Blog, etc.) via keyword matching
- Cleans raw HTML by stripping scripts, nav, footer, and other non-content elements
- Falls back to Playwright for JavaScript-rendered sites when content is thin
- Rate-limited (1s between requests) with a max of 8 pages per site

### Phase 2: Need Analysis (`src/analyzer.py`)
- Sends scraped content to Claude with a system prompt positioning the LLM as a senior business development analyst at DAVID AI
- Produces structured JSON: company summary, industry, services, pain points, AI opportunities, value proposition, and recommended outreach angle
- All insights are grounded in evidence from the scraped content
- Includes retry logic with exponential backoff for API rate limits

### Phase 3: Email Drafting (`src/email_drafter.py`)
- Generates a personalized cold outreach email using the analysis
- References specific details from the prospect's website — not a generic template
- Supports 4 tone presets: **professional**, **conversational**, **bold**, **consultative**
- Anti-cliché rules (no "I hope this finds you well"), word limits, low-friction CTA
- User can review, edit, or regenerate the draft before sending

### Phase 4: Gmail Send (`src/gmail_sender.py`)
- Sends via Gmail SMTP with TLS encryption
- Requires explicit confirmation — no accidental sends
- Smart retry logic: retries transient failures (3 attempts), does NOT retry auth or recipient errors
- Logs every attempt to `logs/outreach_log.json` with full CRM-style records

### Phase 5: Email Tracking & Follow-Ups (`app.py` + `src/gmail_sender.py`)
- Manual tracking: mark emails as opened or replied with timestamped status updates
- Follow-up scheduling: set follow-up dates per email, with overdue/upcoming indicators
- Follow-Up Dashboard tab: dedicated view showing overdue and upcoming follow-ups with snooze controls
- Post-send scheduling: after sending an email, optionally set a follow-up date and note
- Notes field: attach free-text notes to any outreach record
- Note: tracking is manual (not pixel-based) because Streamlit cannot host a tracking pixel endpoint. This is a practical and honest approach for a demo — the data model supports automated tracking if a backend is added later.

---

## Features

- **End-to-end automation**: URL in → email sent
- **Streamlit web UI**: Clean, branded interface with light theme
- **Batch mode**: Process multiple prospect URLs in sequence
- **CRM-style logging**: Track all outreach attempts with status, timestamps, and error details
- **Tone customization**: 4 email style presets
- **Email editing**: Review and modify drafts before sending
- **Draft regeneration**: Generate alternative email versions on demand
- **Error handling**: Graceful failures at every stage with retry logic
- **Email tracking**: Mark emails as opened/replied with timestamps
- **Follow-up scheduling**: Set follow-up dates, snooze overdue items, manage pipeline
- **Follow-up dashboard**: Dedicated view for overdue and upcoming follow-ups
- **Test suite**: 69 tests covering all core modules

---

## Environment Variables

| Variable             | Required | Description                          |
|----------------------|----------|--------------------------------------|
| `ANTHROPIC_API_KEY`  | Yes      | Anthropic API key for Claude         |
| `GMAIL_ADDRESS`      | Yes*     | Gmail address for sending emails     |
| `GMAIL_APP_PASSWORD` | Yes*     | Gmail App Password (16 chars)        |
| `SENDER_NAME`        | No       | Display name on sent emails          |

*Required only for sending emails. Scraping and analysis work without Gmail credentials.

---

## Known Limitations

- **JavaScript-heavy sites**: Basic scraping uses `requests` which doesn't execute JavaScript. Playwright fallback is available but must be installed separately (`playwright install chromium`).
- **Rate limiting**: Some sites may block automated requests. The scraper includes a User-Agent header and 1-second delays but cannot bypass aggressive anti-bot measures.
- **Content extraction**: The scraper targets common page structures. Highly unconventional site layouts may yield less useful content.
- **Gmail sending limits**: Gmail has daily sending limits (~500 for regular accounts). This tool is designed for targeted outreach, not bulk email.
- **Single language**: Currently supports English-language websites and email generation only.

---

## Design Decisions

1. **Custom agent loop over LangChain/CrewAI**: For a focused pipeline with 4 clear stages, a custom orchestrator is simpler, more debuggable, and avoids framework overhead.
2. **SMTP over Gmail OAuth2**: App Password auth is faster to set up and sufficient for a demo. OAuth2 would be preferred for production.
3. **Pydantic models**: Ensures structured data flows between pipeline stages with validation.
4. **Separated modules**: Each phase is an independent module that can be tested and used standalone.
5. **Streamlit**: Provides a polished demo UI with minimal code, supporting the visual requirements of the project.

---

## Tech Stack

- **Python 3.10+**
- **Anthropic Claude** (Sonnet) — LLM for analysis and email drafting
- **BeautifulSoup4** — HTML parsing and content extraction
- **Requests** — HTTP client for web scraping
- **Playwright** — Headless browser fallback for JS-rendered sites
- **Streamlit** — Web UI framework
- **Pydantic v2** — Data validation and serialization
- **pytest** — Test framework (69 tests)
- **python-dotenv** — Environment variable management
