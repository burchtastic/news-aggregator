"""Daily email digest sender via Gmail SMTP."""
import logging
import os
import smtplib
from collections import defaultdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import database as db

logger = logging.getLogger(__name__)

TOPIC_ORDER = [
    "Annapolis",
    "Maryland",
    "Baltimore",
    "US News",
    "Marketing",
    "MarOps",
    "Digital Marketing",
    "SEO",
    "Social Media",
]

SENTIMENT_EMOJI = {
    "positive": "🟢",
    "neutral": "🔵",
    "negative": "🔴",
}


def _build_html(articles: list, generated_at: str) -> str:
    # Group by first tag
    by_topic: dict[str, list] = defaultdict(list)
    untagged = []
    for a in articles:
        tags = a.get("tags", [])
        if tags:
            by_topic[tags[0]].append(a)
        else:
            untagged.append(a)

    # Build topic sections in preferred order
    sections_html = ""
    seen_ids = set()

    for topic in TOPIC_ORDER:
        topic_articles = [a for a in by_topic.get(topic, []) if a["id"] not in seen_ids]
        if not topic_articles:
            continue
        for a in topic_articles:
            seen_ids.add(a["id"])

        articles_html = ""
        for a in topic_articles[:8]:  # max 8 per topic
            sentiment = a.get("sentiment", "neutral")
            emoji = SENTIMENT_EMOJI.get(sentiment, "🔵")
            score = a.get("score", 0)
            summary = a.get("summary", "") or "No summary available."
            pub_date = (a.get("published_at") or "")[:10]

            articles_html += f"""
            <div style="margin-bottom:20px;padding:16px;background:#f9fafb;
                        border-left:4px solid #3b82f6;border-radius:4px;">
              <h3 style="margin:0 0 6px;font-size:16px;">
                <a href="{a['url']}" style="color:#1e40af;text-decoration:none;">
                  {a['title']}
                </a>
              </h3>
              <p style="margin:0 0 8px;font-size:13px;color:#6b7280;">
                {a['source']} &nbsp;·&nbsp; {pub_date} &nbsp;·&nbsp;
                {emoji} {sentiment.capitalize()} &nbsp;·&nbsp; Score: {score}/10
              </p>
              <p style="margin:0;font-size:14px;color:#374151;line-height:1.5;">
                {summary}
              </p>
              <a href="{a['url']}" style="display:inline-block;margin-top:8px;
                font-size:13px;color:#3b82f6;">Read more →</a>
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:32px;">
          <h2 style="margin:0 0 16px;padding:8px 16px;background:#1e40af;
                     color:white;border-radius:4px;font-size:18px;">
            {topic}
          </h2>
          {articles_html}
        </div>"""

    # Any remaining (untagged or extra)
    remaining = [a for a in untagged if a["id"] not in seen_ids]
    if remaining:
        articles_html = ""
        for a in remaining[:5]:
            summary = a.get("summary", "") or ""
            articles_html += f"""
            <div style="margin-bottom:16px;padding:12px;background:#f9fafb;
                        border-left:4px solid #9ca3af;border-radius:4px;">
              <h3 style="margin:0 0 4px;font-size:15px;">
                <a href="{a['url']}" style="color:#1e40af;">{a['title']}</a>
              </h3>
              <p style="margin:0;font-size:13px;color:#6b7280;">{a['source']}</p>
              {f'<p style="margin:4px 0 0;font-size:13px;">{summary}</p>' if summary else ''}
            </div>"""
        sections_html += f"""
        <div style="margin-bottom:32px;">
          <h2 style="margin:0 0 16px;padding:8px 16px;background:#6b7280;
                     color:white;border-radius:4px;font-size:18px;">Other</h2>
          {articles_html}
        </div>"""

    total = len(articles)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f3f4f6;">
  <div style="max-width:680px;margin:0 auto;padding:24px 16px;">

    <!-- Header -->
    <div style="background:#1e3a8a;color:white;padding:24px;border-radius:8px;margin-bottom:24px;
                text-align:center;">
      <h1 style="margin:0 0 4px;font-size:24px;">📰 Daily News Digest</h1>
      <p style="margin:0;opacity:0.8;font-size:14px;">
        {generated_at} &nbsp;·&nbsp; {total} articles curated for you
      </p>
    </div>

    <!-- Content -->
    {sections_html if sections_html else
      '<p style="text-align:center;color:#6b7280;">No high-scoring articles to report today.</p>'}

    <!-- Footer -->
    <div style="text-align:center;padding:16px;color:#9ca3af;font-size:12px;border-top:1px solid #e5e7eb;">
      News Aggregator · Annapolis, MD · Unsubscribe by updating your preferences
    </div>
  </div>
</body>
</html>"""


def build_digest_data(hours: int = 24) -> dict:
    """Return article data for digest preview or sending."""
    articles = db.get_recent_articles_for_digest(hours=hours)
    generated_at = datetime.now().strftime("%A, %B %-d, %Y at %-I:%M %p")
    html = _build_html(articles, generated_at)
    return {
        "articles": articles,
        "article_count": len(articles),
        "generated_at": generated_at,
        "html": html,
    }


def send_digest():
    """Send the nightly email digest via Gmail SMTP."""
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    prefs = db.get_preferences()
    recipient = prefs.get("email_recipient") or os.getenv("EMAIL_RECIPIENT", "")

    if not gmail_user or not gmail_password:
        logger.error("Gmail credentials not configured; skipping digest send")
        return
    if not recipient:
        logger.error("No recipient email configured; skipping digest send")
        return

    digest = build_digest_data()
    if digest["article_count"] == 0:
        logger.info("No articles for digest today; skipping send")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 Daily News Digest — {digest['generated_at']}"
    msg["From"] = gmail_user
    msg["To"] = recipient

    # Plain-text fallback
    plain = f"Daily News Digest — {digest['generated_at']}\n\n"
    for a in digest["articles"][:20]:
        plain += f"{a['title']}\n{a['source']} | {a.get('url', '')}\n"
        if a.get("summary"):
            plain += f"{a['summary']}\n"
        plain += "\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(digest["html"], "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipient, msg.as_string())
        logger.info("Digest sent to %s (%d articles)", recipient, digest["article_count"])
    except Exception as exc:
        logger.error("Failed to send digest: %s", exc)
