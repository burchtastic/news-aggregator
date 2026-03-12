import React, { useState } from "react";
import { api } from "../api.js";

const SENTIMENT_LABEL = { positive: "▲", neutral: "●", negative: "▼" };
const SENTIMENT_COLOR = { positive: "#16a34a", neutral: "#2563eb", negative: "#dc2626" };

function ScoreBadge({ score }) {
  const cls = score >= 7 ? "high" : score <= 3 ? "low" : "";
  return <span className={`score-badge ${cls}`}>{score}/10</span>;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

export default function ArticleCard({ article, onBlock, showToast }) {
  const [feedback, setFeedback] = useState(article.feedback ?? 0);
  const [blocked, setBlocked] = useState(false);

  const handleFeedback = async (val) => {
    const next = feedback === val ? 0 : val;
    try {
      await api.setFeedback(article.id, next);
      setFeedback(next);
    } catch (e) {
      showToast?.("Failed to save feedback");
    }
  };

  const handleBlock = async () => {
    try {
      await api.blockSource(article.source);
      setBlocked(true);
      showToast?.(`🚫 Blocked "${article.source}"`);
      onBlock?.(article.source);
    } catch (e) {
      showToast?.("Failed to block source: " + e.message);
    }
  };

  if (blocked) return null;

  const sentiment = article.sentiment || "neutral";
  const tags = article.tags || [];

  return (
    <div className="article-card">
      <h2 className="article-title">
        <a href={article.url} target="_blank" rel="noopener noreferrer">
          {article.title}
        </a>
      </h2>

      <div className="article-meta">
        <strong>{article.source}</strong>
        <span>·</span>
        <span>{formatDate(article.published_at || article.fetched_at)}</span>
        {article.analyzed ? (
          <>
            <span>·</span>
            <span
              style={{ color: SENTIMENT_COLOR[sentiment], fontWeight: 600, fontSize: 13 }}
              title={`Sentiment: ${sentiment}`}
            >
              {SENTIMENT_LABEL[sentiment]} {sentiment}
            </span>
          </>
        ) : (
          <span style={{ color: "#9ca3af", fontStyle: "italic" }}>analyzing…</span>
        )}
      </div>

      {article.summary ? (
        <p className="article-summary">{article.summary}</p>
      ) : article.content ? (
        <p className="article-summary" style={{ color: "#6b7280", fontStyle: "italic" }}>
          {article.content.slice(0, 200)}…
        </p>
      ) : null}

      <div className="article-footer">
        <div className="article-tags">
          {tags.map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>

        <div className="article-actions">
          {article.analyzed && <ScoreBadge score={article.score} />}

          <button
            className={`thumb-btn ${feedback === 1 ? "active-up" : ""}`}
            onClick={() => handleFeedback(1)}
            title="Thumbs up"
          >👍</button>

          <button
            className={`thumb-btn ${feedback === -1 ? "active-down" : ""}`}
            onClick={() => handleFeedback(-1)}
            title="Thumbs down"
          >👎</button>

          <button
            className="btn-secondary btn-sm"
            onClick={handleBlock}
            title={`Block all articles from "${article.source}"`}
          >
            🚫 Block source
          </button>
        </div>
      </div>
    </div>
  );
}
