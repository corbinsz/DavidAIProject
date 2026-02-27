"""
Email Drafting Module
Generates personalized cold outreach emails using the need analysis results.
References specific details from the prospect's website.
Supports tone/style customization.
"""

import json
import logging
import time

import anthropic

from src.models import NeedAnalysis, EmailDraft

logger = logging.getLogger(__name__)

TONE_DESCRIPTIONS = {
    "professional": "Professional and polished. Business-appropriate language, clear and direct.",
    "conversational": "Friendly and conversational. Warm but still professional. Like talking to a smart colleague.",
    "bold": "Confident and bold. Direct, slightly provocative, pattern-interrupting. Stands out in an inbox.",
    "consultative": "Thoughtful and consultative. Lead with insights and questions. Position as a strategic advisor.",
}

EMAIL_SYSTEM_PROMPT = """You are an expert cold email copywriter for DAVID AI, \
a company that provides world-class AI engineering services to help businesses \
scale intelligence tenfold.

You write outreach emails that:
- Feel personally written, NOT templated or mass-produced
- Reference specific details from the prospect's website to prove research was done
- Lead with value and insight, not a sales pitch
- Are concise (under 200 words for the body)
- Have a single, clear call to action
- Use a subject line that's intriguing but not clickbait (under 60 chars)

DAVID AI's key selling points:
- World-class AI engineering embedded directly into client workflows
- Custom AI solutions (not off-the-shelf tools)
- Proven ability to accelerate business roadmaps with AI
- End-to-end: strategy, development, deployment, and iteration"""

EMAIL_USER_PROMPT = """Write a personalized cold outreach email based on this prospect analysis.

**Prospect Analysis:**
{analysis_json}

**Tone/Style:** {tone}
{tone_description}

**Sender Name:** {sender_name}

---

Return a JSON object with exactly these fields:

{{
  "subject": "Email subject line (under 60 chars, no quotes)",
  "body": "The full email body. Use \\n for line breaks. Start with a personalized opener that references something specific from their website. Include the value proposition. End with a clear CTA (suggest a brief call/meeting). Sign off with the sender name."
}}

Guidelines:
- NEVER start with "I hope this email finds you well" or similar cliches.
- NEVER start with "I noticed your company..." — be more creative.
- DO reference a specific detail from their website (a service, a recent post, their mission, etc.).
- DO make the connection to AI/DAVID AI feel natural, not forced.
- Keep paragraphs short (2-3 sentences max).
- The CTA should be low-friction (e.g., "Worth a 15-minute chat?" not "Schedule a demo").
- Return ONLY the JSON object, no markdown formatting or code blocks."""


def draft_email(
    analysis: NeedAnalysis,
    api_key: str,
    sender_name: str = "The DAVID AI Team",
    tone: str = "professional",
    model: str = "claude-sonnet-4-5-20250929",
) -> EmailDraft:
    """
    Generate a personalized outreach email based on the need analysis.

    Args:
        analysis: The prospect need analysis.
        api_key: Anthropic API key.
        sender_name: Name to sign the email with.
        tone: Email tone - professional, conversational, bold, or consultative.
        model: Claude model to use.

    Returns:
        EmailDraft with subject and body.
    """
    client = anthropic.Anthropic(api_key=api_key)

    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])

    analysis_json = analysis.model_dump_json(indent=2)

    user_prompt = EMAIL_USER_PROMPT.format(
        analysis_json=analysis_json,
        tone=tone,
        tone_description=tone_desc,
        sender_name=sender_name,
    )

    logger.info(f"Generating email draft (tone: {tone})...")

    # Retry with backoff for transient API errors (rate limits, overload, network)
    max_retries = 3
    message = None
    for attempt in range(1, max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=1000,
                system=EMAIL_SYSTEM_PROMPT,
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
        if len(lines) > 2:
            response_text = "\n".join(lines[1:-1])
        else:
            response_text = response_text.strip("`").strip()

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response_text[start:end])
        else:
            raise ValueError(f"LLM did not return valid JSON: {response_text[:200]}")

    draft = EmailDraft(
        subject=data["subject"],
        body=data["body"],
        tone=tone,
    )

    logger.info(f"Email draft generated: \"{draft.subject}\"")
    return draft
