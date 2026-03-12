"""RSS feed fetcher — pulls articles from all active sources."""
import re
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from . import database as db
from .claude_api import analyze_article
from .twitter_fetcher import fetch_twitter_accounts

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NewsAggregator/1.0; "
        "+https://github.com/news-aggregator)"
    )
}


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def _get_content(entry) -> str:
    # Try full content first
    content_list = getattr(entry, "content", None)
    if content_list:
        return _strip_html(content_list[0].get("value", ""))
    # Fall back to summary
    summary = getattr(entry, "summary", None)
    if summary:
        return _strip_html(summary)
    return ""


def fetch_feed(source: dict) -> int:
    """Fetch one RSS feed. Returns count of new articles stored."""
    url = source["url"]
    name = source["name"]
    new_count = 0

    try:
        # Use requests for better header control, then parse the text
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as exc:
        logger.warning("Failed to fetch %s (%s): %s", name, url, exc)
        return 0

    if feed.bozo and not feed.entries:
        logger.warning("Malformed feed from %s: %s", name, feed.bozo_exception)
        return 0

    for entry in feed.entries[:30]:  # limit to 30 most recent per feed
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()

        if not title or not link:
            continue

        content = _get_content(entry)
        published_at = _parse_date(entry)

        article_id = db.insert_article(
            title=title,
            url=link,
            source=name,
            source_url=url,
            published_at=published_at,
            content=content[:5000],  # cap stored content
        )

        if article_id:
            new_count += 1

    logger.info("Fetched %d new articles from %s", new_count, name)
    return new_count


def run_fetch_all() -> dict:
    """Fetch all active sources and analyze new articles. Returns a summary."""
    sources = db.get_active_sources()
    total_new = 0

    for source in sources:
        total_new += fetch_feed(source)

    # Fetch Twitter/X accounts (runs only if TWITTER_BEARER_TOKEN is set)
    total_new += fetch_twitter_accounts()

    # Analyze unprocessed articles
    analyzed = analyze_pending_articles()

    return {
        "sources_checked": len(sources),
        "new_articles": total_new,
        "articles_analyzed": analyzed,
    }


def analyze_pending_articles(batch_size: int = 15) -> int:
    """Run Claude analysis on articles that haven't been analyzed yet."""
    unanalyzed = db.get_unanalyzed_articles(limit=batch_size)
    count = 0

    for article in unanalyzed:
        try:
            result = analyze_article(
                title=article["title"],
                content=article.get("content", ""),
                source=article["source"],
            )
            db.update_article_analysis(
                article_id=article["id"],
                summary=result["summary"],
                tags=result["tags"],
                score=result["score"],
                sentiment=result["sentiment"],
            )
            count += 1
        except Exception as exc:
            logger.error("Failed to analyze article %d: %s", article["id"], exc)

    logger.info("Analyzed %d articles", count)
    return count
