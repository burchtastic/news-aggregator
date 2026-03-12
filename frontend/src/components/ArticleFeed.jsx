import React, { useState, useEffect, useCallback } from "react";
import ArticleCard from "./ArticleCard.jsx";
import { api } from "../api.js";

const TOPICS = [
  "All",
  "Annapolis",
  "Maryland",
  "Baltimore",
  "US News",
  "Marketing",
  "MarOps",
  "Digital Marketing",
  "SEO",
  "Social Media",
];

const MIN_SCORE_OPTIONS = [
  { label: "Any score", value: "" },
  { label: "Score ≥ 5",  value: "5" },
  { label: "Score ≥ 7",  value: "7" },
  { label: "Score ≥ 9",  value: "9" },
];

function StatsBar({ stats }) {
  if (!stats) return null;
  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-value">{stats.total_articles ?? "—"}</div>
        <div className="stat-label">Total Articles</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{stats.analyzed_articles ?? "—"}</div>
        <div className="stat-label">Analyzed</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{stats.active_sources ?? "—"}</div>
        <div className="stat-label">Active Sources</div>
      </div>
      <div className="stat-card">
        <div className="stat-value">{stats.avg_score ?? "—"}</div>
        <div className="stat-label">Avg Score</div>
      </div>
    </div>
  );
}

export default function ArticleFeed({ showToast }) {
  const [articles, setArticles] = useState([]);
  const [stats, setStats] = useState(null);
  const [topic, setTopic] = useState("All");
  const [minScore, setMinScore] = useState("");
  const [loading, setLoading] = useState(true);
  const [blockedSources, setBlockedSources] = useState(new Set());

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (topic !== "All") params.topic = topic;
      if (minScore) params.min_score = minScore;
      params.limit = 100;

      const [data, statsData] = await Promise.all([
        api.getArticles(params),
        api.getStats(),
      ]);
      setArticles(data.articles || []);
      setStats(statsData);
    } catch (e) {
      showToast?.("Failed to load articles: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [topic, minScore]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  const handleBlock = (sourceName) => {
    setBlockedSources((prev) => new Set([...prev, sourceName]));
    setArticles((prev) => prev.filter((a) => a.source !== sourceName));
  };

  const visibleArticles = articles.filter(
    (a) => !blockedSources.has(a.source)
  );

  return (
    <div>
      <StatsBar stats={stats} />

      {/* Topic tabs */}
      <div className="topic-tabs">
        {TOPICS.map((t) => (
          <button
            key={t}
            className={`topic-tab ${topic === t ? "active" : ""}`}
            onClick={() => setTopic(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="feed-controls">
        <select
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        >
          {MIN_SCORE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <span className="spacer" />
        <span style={{ fontSize: 13, color: "#6b7280" }}>
          {loading ? "Loading…" : `${visibleArticles.length} articles`}
        </span>
        <button className="btn-secondary btn-sm" onClick={loadArticles}>
          ↺ Refresh
        </button>
      </div>

      {/* Article list */}
      {loading ? (
        <div className="loading-state">
          <div className="loading-spinner" />
          <p>Loading articles…</p>
        </div>
      ) : visibleArticles.length === 0 ? (
        <div className="empty-state">
          <p style={{ fontSize: 48, marginBottom: 12 }}>📭</p>
          <p style={{ fontWeight: 600, marginBottom: 8 }}>No articles yet</p>
          <p style={{ fontSize: 14 }}>
            Click <strong>⟳ Fetch Now</strong> in the top bar to pull articles from all sources.
          </p>
        </div>
      ) : (
        <div className="article-list">
          {visibleArticles.map((a) => (
            <ArticleCard
              key={a.id}
              article={a}
              onBlock={handleBlock}
              showToast={showToast}
            />
          ))}
        </div>
      )}
    </div>
  );
}
