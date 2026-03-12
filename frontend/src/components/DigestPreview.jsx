import React, { useState, useEffect, useRef } from "react";
import { api } from "../api.js";

export default function DigestPreview({ showToast }) {
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const iframeRef = useRef(null);

  const loadPreview = async () => {
    setLoading(true);
    try {
      const data = await api.getDigestPreview();
      setDigest(data);
    } catch (e) {
      showToast?.("Failed to load digest: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPreview();
  }, []);

  // Write HTML into the iframe when digest changes
  useEffect(() => {
    if (!digest?.html || !iframeRef.current) return;
    const doc = iframeRef.current.contentDocument;
    doc.open();
    doc.write(digest.html);
    doc.close();
  }, [digest?.html]);

  const handleSend = async () => {
    if (sending) return;
    setSending(true);
    try {
      await api.sendDigest();
      showToast?.("✅ Digest queued for delivery!");
    } catch (e) {
      showToast?.("Failed to send digest: " + e.message);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <p>Generating digest preview…</p>
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
            📧 Tonight's Digest Preview
          </h1>
          {digest && (
            <p style={{ fontSize: 14, color: "#6b7280" }}>
              {digest.article_count} articles · Generated {digest.generated_at}
            </p>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-secondary" onClick={loadPreview}>
            ↺ Refresh
          </button>
          <button
            className="btn-primary"
            onClick={handleSend}
            disabled={sending || !digest?.article_count}
          >
            {sending ? "Sending…" : "📤 Send Now"}
          </button>
        </div>
      </div>

      {!digest?.article_count ? (
        <div className="empty-state card" style={{ padding: "48px 24px" }}>
          <p style={{ fontSize: 48, marginBottom: 12 }}>📭</p>
          <p style={{ fontWeight: 600, marginBottom: 8 }}>No articles for tonight's digest</p>
          <p style={{ fontSize: 14 }}>
            Articles need a score of 5 or higher and must have been fetched in the last 24 hours.
            Try fetching articles first using the <strong>⟳ Fetch Now</strong> button.
          </p>
        </div>
      ) : (
        <div className="digest-preview-frame">
          <iframe
            ref={iframeRef}
            title="Digest Preview"
            sandbox="allow-same-origin"
          />
        </div>
      )}

      {/* Article table summary */}
      {digest?.articles?.length > 0 && (
        <div className="settings-section" style={{ marginTop: 24 }}>
          <h3>📋 Articles in this digest ({digest.article_count})</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                  <th style={{ textAlign: "left", padding: "8px 12px", color: "#374151" }}>Title</th>
                  <th style={{ textAlign: "left", padding: "8px 12px", color: "#374151" }}>Source</th>
                  <th style={{ textAlign: "center", padding: "8px 12px", color: "#374151" }}>Score</th>
                  <th style={{ textAlign: "left", padding: "8px 12px", color: "#374151" }}>Tags</th>
                </tr>
              </thead>
              <tbody>
                {digest.articles.map((a) => (
                  <tr
                    key={a.id}
                    style={{ borderBottom: "1px solid #f3f4f6" }}
                  >
                    <td style={{ padding: "8px 12px" }}>
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "#1e40af", fontWeight: 500 }}
                      >
                        {a.title.length > 60 ? a.title.slice(0, 60) + "…" : a.title}
                      </a>
                    </td>
                    <td style={{ padding: "8px 12px", color: "#6b7280" }}>{a.source}</td>
                    <td style={{ padding: "8px 12px", textAlign: "center" }}>
                      <span
                        style={{
                          background: a.score >= 7 ? "#dcfce7" : "#dbeafe",
                          color: a.score >= 7 ? "#16a34a" : "#1e40af",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 999,
                        }}
                      >
                        {a.score}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px" }}>
                      {(a.tags || []).map((t) => (
                        <span
                          key={t}
                          style={{
                            background: "#dbeafe",
                            color: "#1e40af",
                            fontSize: 11,
                            fontWeight: 600,
                            padding: "2px 6px",
                            borderRadius: 999,
                            marginRight: 4,
                          }}
                        >
                          {t}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
