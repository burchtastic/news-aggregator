"""Twitter/X fetcher — pulls recent tweets from @BaltimoreBanner."""
import logging
import os
from datetime import datetime, timezone

from . import database as db

logger = logging.getLogger(__name__)

# X accounts to follow
TWITTER_ACCOUNTS = [
    "BaltimoreBanner",
]


def _tweet_url(username: str, tweet_id: str) -> str:
    return f"https://x.com/{username}/status/{tweet_id}"


def fetch_twitter_accounts() -> int:
    """Fetch recent tweets for all tracked accounts. Returns count of new items stored."""
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        logger.debug("TWITTER_BEARER_TOKEN not set — skipping Twitter fetch")
        return 0

    try:
        import tweepy
    except ImportError:
        logger.warning("tweepy not installed — run: pip install tweepy")
        return 0

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
    total_new = 0

    for username in TWITTER_ACCOUNTS:
        try:
            total_new += _fetch_user_tweets(client, username)
        except Exception as exc:
            logger.warning("Failed to fetch tweets for @%s: %s", username, exc)

    return total_new


def _fetch_user_tweets(client, username: str) -> int:
    """Fetch up to 20 recent non-reply, non-retweet tweets for a user."""
    # Look up user ID
    user_resp = client.get_user(username=username)
    if not user_resp.data:
        logger.warning("X user not found: @%s", username)
        return 0

    user_id = user_resp.data.id

    # Fetch recent tweets, exclude replies and retweets
    tweets_resp = client.get_users_tweets(
        id=user_id,
        max_results=20,
        tweet_fields=["created_at", "text", "entities"],
        exclude=["replies", "retweets"],
    )

    if not tweets_resp.data:
        return 0

    new_count = 0
    for tweet in tweets_resp.data:
        tweet_id = str(tweet.id)
        url = _tweet_url(username, tweet_id)
        text = tweet.text or ""

        # Use first line or first 120 chars as title
        first_line = text.split("\n")[0]
        title = first_line[:120] + ("…" if len(first_line) > 120 else "")
        if not title:
            continue

        published_at = (
            tweet.created_at.isoformat()
            if tweet.created_at
            else datetime.now(timezone.utc).isoformat()
        )

        article_id = db.insert_article(
            title=title,
            url=url,
            source=f"@{username} (X)",
            source_url=f"https://x.com/{username}",
            published_at=published_at,
            content=text[:5000],
        )

        if article_id:
            new_count += 1

    logger.info("Fetched %d new tweets from @%s", new_count, username)
    return new_count
