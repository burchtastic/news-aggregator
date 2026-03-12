"""Claude API integration for article analysis.

Uses claude-sonnet-4-0 (claude-sonnet-4-20250514) as specified by the user.
"""
import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

# User requested claude-sonnet-4-20250514 → alias: claude-sonnet-4-0
MODEL = "claude-sonnet-4-0"

VALID_TAGS = [
    "US News",
    "Maryland",
    "Annapolis",
    "Baltimore",
    "Marketing",
    "MarOps",
    "Digital Marketing",
    "SEO",
    "Social Media",
]

SYSTEM_PROMPT = (
    "You are an expert news analyst. Your job is to analyze news articles and "
    "return structured JSON. Respond ONLY with valid JSON — no markdown, no explanation."
)


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


def analyze_article(title: str, content: str, source: str) -> dict:
    """
    Analyze an article with Claude and return a dict with:
      - summary: 2-sentence summary string
      - tags: list of topic tags from VALID_TAGS
      - score: int 1-10 relevance for a digital marketing ops professional in Annapolis MD
      - sentiment: "positive" | "neutral" | "negative"
    """
    client = _get_client()

    content_preview = (content or "")[:2000]

    prompt = f"""Analyze this news article and return a JSON object with exactly these fields:

1. "summary": A 2-sentence summary of the article.
2. "tags": An array of relevant topic tags chosen ONLY from this list:
   {json.dumps(VALID_TAGS)}
   Include 1-3 tags that best apply. Use an empty array if none apply.
3. "score": An integer from 1 to 10 representing the relevance of this article
   for a digital marketing operations professional based in Annapolis, MD.
   10 = extremely relevant (local MD news + marketing ops), 1 = not relevant at all.
4. "sentiment": One of "positive", "neutral", or "negative".

Article details:
Title: {title}
Source: {source}
Content: {content_preview}

Return ONLY the JSON object with those 4 fields. Example format:
{{"summary": "Sentence one. Sentence two.", "tags": ["Marketing", "SEO"], "score": 7, "sentiment": "neutral"}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)

    # Validate and sanitize
    summary = str(result.get("summary", "")).strip()
    tags = [t for t in result.get("tags", []) if t in VALID_TAGS]
    score = max(1, min(10, int(result.get("score", 5))))
    sentiment = result.get("sentiment", "neutral")
    if sentiment not in ("positive", "neutral", "negative"):
        sentiment = "neutral"

    return {
        "summary": summary,
        "tags": tags,
        "score": score,
        "sentiment": sentiment,
    }
