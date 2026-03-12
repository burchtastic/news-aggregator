import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "news.db")

DEFAULT_SOURCES = [
    {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "AP News", "url": "https://rsshub.app/apnews/topics/apf-topnews"},
    {"name": "Capital Gazette", "url": "https://www.capitalgazette.com/arcio/rss/"},
    {"name": "Maryland Matters", "url": "https://marylandmatters.org/feed/"},
    {"name": "Baltimore Banner", "url": "https://thebaltimorebanner.com/feed/"},
    {"name": "Baltimore Sun", "url": "https://www.baltimoresun.com/arcio/rss/"},
    {"name": "WBAL", "url": "https://www.wbal.com/rss"},
    {"name": "MarTech", "url": "https://martech.org/feed/"},
    {"name": "ChiefMartec", "url": "https://chiefmartec.com/feed/"},
    {"name": "Search Engine Land", "url": "https://searchengineland.com/feed"},
    {"name": "HubSpot Blog", "url": "https://blog.hubspot.com/marketing/rss.xml"},
    {"name": "Reddit/marketing", "url": "https://www.reddit.com/r/marketing/.rss"},
    {"name": "Reddit/marketingops", "url": "https://www.reddit.com/r/marketingops/.rss"},
    {"name": "Reddit/digital_marketing", "url": "https://www.reddit.com/r/digital_marketing/.rss"},
    {"name": "Reddit/maryland", "url": "https://www.reddit.com/r/maryland/.rss"},
    {"name": "Reddit/annapolis", "url": "https://www.reddit.com/r/annapolis/.rss"},
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT,
                published_at TEXT,
                content TEXT,
                summary TEXT,
                tags TEXT DEFAULT '[]',
                score REAL DEFAULT 0,
                sentiment TEXT DEFAULT 'neutral',
                feedback INTEGER DEFAULT 0,
                fetched_at TEXT NOT NULL,
                analyzed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                active INTEGER DEFAULT 1,
                blocked INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY DEFAULT 1,
                blocked_sources TEXT DEFAULT '[]',
                blocked_keywords TEXT DEFAULT '[]',
                preferred_topics TEXT DEFAULT '[]',
                email_recipient TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
            CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at DESC);
        """)

        # Seed default sources if none exist
        count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO sources (name, url) VALUES (?, ?)",
                [(s["name"], s["url"]) for s in DEFAULT_SOURCES]
            )

        # Seed default preferences if none exist
        conn.execute(
            "INSERT OR IGNORE INTO user_preferences (id, email_recipient) VALUES (1, ?)",
            (os.getenv("EMAIL_RECIPIENT", ""),)
        )
        conn.commit()
    finally:
        conn.close()


# ── Articles ──────────────────────────────────────────────────────────────────

def insert_article(title, url, source, source_url, published_at, content):
    """Insert a new article. Returns the new row id or None if duplicate."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO articles
               (title, url, source, source_url, published_at, content, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, url, source, source_url, published_at, content, fetched_at)
        )
        conn.commit()
        return cursor.lastrowid if cursor.rowcount else None
    finally:
        conn.close()


def update_article_analysis(article_id, summary, tags, score, sentiment):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE articles
               SET summary=?, tags=?, score=?, sentiment=?, analyzed=1
               WHERE id=?""",
            (summary, json.dumps(tags), score, sentiment, article_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_articles(topic=None, date_from=None, min_score=None, limit=100, offset=0):
    conn = get_connection()
    try:
        query = "SELECT * FROM articles WHERE 1=1"
        params = []

        # Filter out articles from blocked sources
        prefs = get_preferences()
        blocked = json.loads(prefs["blocked_sources"]) if prefs else []
        blocked_kws = json.loads(prefs["blocked_keywords"]) if prefs else []

        if blocked:
            placeholders = ",".join("?" * len(blocked))
            query += f" AND source NOT IN ({placeholders})"
            params.extend(blocked)

        if topic and topic != "All":
            query += " AND tags LIKE ?"
            params.append(f'%"{topic}"%')

        if date_from:
            query += " AND fetched_at >= ?"
            params.append(date_from)

        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)

        query += " ORDER BY fetched_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        articles = [dict(r) for r in rows]

        # Filter blocked keywords in Python
        if blocked_kws:
            def has_blocked_kw(a):
                text = (a.get("title", "") + " " + (a.get("summary", "") or "")).lower()
                return any(kw.lower() in text for kw in blocked_kws)
            articles = [a for a in articles if not has_blocked_kw(a)]

        # Parse JSON fields
        for a in articles:
            a["tags"] = json.loads(a.get("tags") or "[]")

        return articles
    finally:
        conn.close()


def get_article_by_id(article_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if row:
            a = dict(row)
            a["tags"] = json.loads(a.get("tags") or "[]")
            return a
        return None
    finally:
        conn.close()


def set_article_feedback(article_id, feedback):
    conn = get_connection()
    try:
        conn.execute("UPDATE articles SET feedback=? WHERE id=?", (feedback, article_id))
        conn.commit()
    finally:
        conn.close()


def get_unanalyzed_articles(limit=20):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM articles WHERE analyzed=0 ORDER BY fetched_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_articles_for_digest(hours=24):
    conn = get_connection()
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE fetched_at >= ? AND analyzed=1 AND score >= 5
               ORDER BY score DESC""",
            (since,)
        ).fetchall()
        articles = [dict(r) for r in rows]
        for a in articles:
            a["tags"] = json.loads(a.get("tags") or "[]")
        return articles
    finally:
        conn.close()


# ── Sources ───────────────────────────────────────────────────────────────────

def get_sources():
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY name").fetchall()]
    finally:
        conn.close()


def get_active_sources():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sources WHERE active=1 AND blocked=0"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def block_source(source_name: Optional[str] = None, source_url: Optional[str] = None):
    conn = get_connection()
    try:
        if source_name:
            conn.execute("UPDATE sources SET blocked=1 WHERE name=?", (source_name,))
        elif source_url:
            conn.execute("UPDATE sources SET blocked=1 WHERE url=?", (source_url,))
        conn.commit()
    finally:
        conn.close()


def update_source(source_id, active=None, blocked=None):
    conn = get_connection()
    try:
        if active is not None:
            conn.execute("UPDATE sources SET active=? WHERE id=?", (int(active), source_id))
        if blocked is not None:
            conn.execute("UPDATE sources SET blocked=? WHERE id=?", (int(blocked), source_id))
        conn.commit()
    finally:
        conn.close()


def add_source(name, url):
    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO sources (name, url) VALUES (?, ?)", (name, url))
        conn.commit()
    finally:
        conn.close()


# ── Preferences ───────────────────────────────────────────────────────────────

def get_preferences():
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM user_preferences WHERE id=1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def update_preferences(blocked_sources=None, blocked_keywords=None,
                       preferred_topics=None, email_recipient=None):
    conn = get_connection()
    try:
        existing = get_preferences()
        bs = json.dumps(blocked_sources) if blocked_sources is not None else existing.get("blocked_sources", "[]")
        bk = json.dumps(blocked_keywords) if blocked_keywords is not None else existing.get("blocked_keywords", "[]")
        pt = json.dumps(preferred_topics) if preferred_topics is not None else existing.get("preferred_topics", "[]")
        er = email_recipient if email_recipient is not None else existing.get("email_recipient", "")

        conn.execute(
            """INSERT INTO user_preferences (id, blocked_sources, blocked_keywords, preferred_topics, email_recipient)
               VALUES (1, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   blocked_sources=excluded.blocked_sources,
                   blocked_keywords=excluded.blocked_keywords,
                   preferred_topics=excluded.preferred_topics,
                   email_recipient=excluded.email_recipient""",
            (bs, bk, pt, er)
        )
        conn.commit()
    finally:
        conn.close()
