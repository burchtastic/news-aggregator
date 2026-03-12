import React, { useState } from "react";
import { Link, NavLink, Routes, Route, useNavigate } from "react-router-dom";
import ArticleFeed from "./components/ArticleFeed.jsx";
import Settings from "./components/Settings.jsx";
import DigestPreview from "./components/DigestPreview.jsx";
import { api } from "./api.js";

function Toast({ message, onClose }) {
  React.useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);
  return <div className="toast">{message}</div>;
}

export default function App() {
  const [toast, setToast] = useState(null);
  const [fetching, setFetching] = useState(false);
  const navigate = useNavigate();

  const showToast = (msg) => setToast(msg);

  const handleFetch = async () => {
    if (fetching) return;
    setFetching(true);
    showToast("⏳ Fetching articles...");
    try {
      const result = await api.runFetchSync();
      showToast(
        `✅ Fetched ${result.new_articles} new articles, analyzed ${result.articles_analyzed}`
      );
      // Trigger feed refresh via navigation
      navigate("/", { replace: true });
    } catch (e) {
      showToast("❌ Fetch failed: " + e.message);
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="app-layout">
      <nav className="navbar">
        <Link to="/" className="navbar-brand">📰 NewsAgg</Link>
        <div className="navbar-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}
          >
            Feed
          </NavLink>
          <NavLink
            to="/digest"
            className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}
          >
            Digest Preview
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}
          >
            Settings
          </NavLink>
        </div>
        <div className="navbar-actions">
          <button
            className="btn-primary"
            onClick={handleFetch}
            disabled={fetching}
            style={{ fontSize: "13px", padding: "6px 14px" }}
          >
            {fetching ? "Fetching…" : "⟳ Fetch Now"}
          </button>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<ArticleFeed showToast={showToast} />} />
          <Route path="/digest" element={<DigestPreview showToast={showToast} />} />
          <Route path="/settings" element={<Settings showToast={showToast} />} />
        </Routes>
      </main>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
