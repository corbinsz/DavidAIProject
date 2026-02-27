"""
Need Analysis Module
Uses Claude to analyze scraped website content and identify the prospect's
pain points, gaps, and opportunities where DAVID AI's services add value.
"""

import json
import logging
import time

import anthropic

from src.models import ScrapedWebsite, NeedAnalysis

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a senior business development analyst at DAVID AI, \
a company that provides world-class AI engineering services to help businesses \
scale intelligence tenfold. DAVID AI specializes in:

- AI transformation and strategy consulting
- Custom AI/ML model development and deployment
- Workflow automation powered by AI
- Data pipeline engineering and analytics
- AI-powered product features and integrations
- LLM application development (chatbots, agents, RAG systems)

Your job is to analyze a prospective client's website content and produce a \
structured analysis that will be used to craft a personalized outreach email.

Be specific and insightful. Reference actual details from the website—avoid \
generic observations. Think like a consultant identifying real opportunities, \
not a salesperson pushing features."""

ANALYSIS_USER_PROMPT = """Analyze the following website content for a prospective client. \
Produce a detailed JSON analysis.

**Website URL:** {url}
**Company Name (detected):** {company_name}

**Scraped Content:**
{content}

---

Return a JSON object with exactly these fields:

{{
  "company_name": "The company's actual name",
  "company_summary": "2-3 sentence summary of what the company does, their market, and their scale",
  "industry": "Their primary industry/vertical",
  "services_offered": ["List of their main products/services based on website content"],
  "pain_points": [
    "Specific pain point 1 - explain why this is likely a challenge for them based on what you see",
    "Specific pain point 2 - be concrete, reference what you observed on their site",
    "Specific pain point 3 - connect to their industry context"
  ],
  "ai_opportunities": [
    "Specific AI opportunity 1 - how DAVID AI could help, tied to their actual business",
    "Specific AI opportunity 2 - practical use case with expected impact",
    "Specific AI opportunity 3 - strategic advantage they could gain"
  ],
  "value_proposition": "A tailored 2-3 sentence value proposition explaining why DAVID AI is the right partner for this specific company. Reference their actual situation.",
  "recommended_angle": "The single best angle of approach for the outreach email. What topic will resonate most? What pain point is most urgent? What's the hook?"
}}

Important guidelines:
- Every pain point and opportunity must be grounded in evidence from the scraped content.
- If the website content is limited, acknowledge that and make reasonable inferences based on the industry.
- Be specific about HOW AI/automation would help—don't just say "AI could improve efficiency."
- The recommended_angle should be the most compelling single hook for the outreach email.
- Return ONLY the JSON object, no markdown formatting or code blocks."""


def analyze_prospect(
    scraped: ScrapedWebsite,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
) -> NeedAnalysis:
    """
    Analyze scraped website content using Claude to identify prospect needs.

    Args:
        scraped: The scraped website data.
        api_key: Anthropic API key.
        model: Claude model to use.

    Returns:
        NeedAnalysis with structured analysis results.
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Truncate content if needed to stay within token limits
    content = scraped.raw_text_summary
    if len(content) > 15000:
        content = content[:15000] + "\n\n... [content truncated for analysis]"

    user_prompt = ANALYSIS_USER_PROMPT.format(
        url=scraped.base_url,
        company_name=scraped.company_name,
        content=content,
    )

    logger.info(f"Sending analysis request to Claude ({model})...")

    # Retry with backoff for transient API errors (rate limits, overload, network)
    max_retries = 3
    message = None
    for attempt in range(1, max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=2000,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            logger.warning(f"Anthropic API error (attempt {attempt}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)

    response_text = message.content[0].text.strip()

    # Parse JSON response - handle potential markdown wrapping
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Strip opening ```json and closing ``` lines
        if len(lines) > 2:
            response_text = "\n".join(lines[1:-1])
        else:
            response_text = response_text.strip("`").strip()

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response: {response_text[:500]}")
        # Attempt a more lenient parse
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response_text[start:end])
        else:
            raise ValueError(f"LLM did not return valid JSON: {response_text[:200]}")

    analysis = NeedAnalysis(**data)
    logger.info(f"Analysis complete for {analysis.company_name}")
    return analysis
