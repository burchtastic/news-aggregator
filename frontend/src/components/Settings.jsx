import React, { useState, useEffect } from "react";
import { api } from "../api.js";

function KeywordManager({ keywords, onChange }) {
  const [input, setInput] = useState("");

  const add = () => {
    const val = input.trim();
    if (val && !keywords.includes(val)) {
      onChange([...keywords, val]);
      setInput("");
    }
  };

  const remove = (kw) => onChange(keywords.filter((k) => k !== kw));

  return (
    <div>
      <div className="keyword-list">
        {keywords.length === 0 && (
          <span style={{ fontSize: 13, color: "#9ca3af" }}>No blocked keywords yet.</span>
        )}
        {keywords.map((kw) => (
          <div key={kw} className="keyword-chip">
            {kw}
            <button onClick={() => remove(kw)} title="Remove">×</button>
          </div>
        ))}
      </div>
      <div className="add-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add keyword…"
        />
        <button className="btn-primary" onClick={add}>Add</button>
      </div>
    </div>
  );
}

function AddSourceForm({ onAdd }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  const handleAdd = () => {
    if (name.trim() && url.trim()) {
      onAdd(name.trim(), url.trim());
      setName("");
      setUrl("");
    }
  };

  return (
    <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Source name" />
      <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="RSS feed URL" />
      <button className="btn-primary" onClick={handleAdd} style={{ justifySelf: "start" }}>
        + Add Source
      </button>
    </div>
  );
}

export default function Settings({ showToast }) {
  const [sources, setSources] = useState([]);
  const [prefs, setPrefs] = useState({
    blocked_sources: [],
    blocked_keywords: [],
    preferred_topics: [],
    email_recipient: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([api.getSources(), api.getPreferences()])
      .then(([srcData, prefsData]) => {
        setSources(srcData.sources || []);
        setPrefs(prefsData);
      })
      .catch((e) => showToast?.("Failed to load settings: " + e.message))
      .finally(() => setLoading(false));
  }, []);

  const savePrefs = async (updated) => {
    setSaving(true);
    try {
      await api.updatePreferences(updated);
      setPrefs(updated);
      showToast?.("✅ Preferences saved");
    } catch (e) {
      showToast?.("Failed to save: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleSource = async (source, field, val) => {
    try {
      await api.updateSource(source.id, { [field]: val });
      setSources((prev) =>
        prev.map((s) => (s.id === source.id ? { ...s, [field]: val ? 1 : 0 } : s))
      );
      showToast?.(`✅ Source "${source.name}" updated`);
    } catch (e) {
      showToast?.("Failed to update source: " + e.message);
    }
  };

  const handleAddSource = async (name, url) => {
    try {
      await api.addSource(name, url);
      const data = await api.getSources();
      setSources(data.sources || []);
      showToast?.(`✅ Added source "${name}"`);
    } catch (e) {
      showToast?.("Failed to add source: " + e.message);
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <p>Loading settings…</p>
      </div>
    );
  }

  const active = sources.filter((s) => !s.blocked);
  const blocked = sources.filter((s) => s.blocked);

  return (
    <div className="settings-grid">
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Settings</h1>

      {/* Email */}
      <div className="settings-section">
        <h3>📧 Email Digest</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="email"
            value={prefs.email_recipient}
            onChange={(e) => setPrefs({ ...prefs, email_recipient: e.target.value })}
            placeholder="recipient@example.com"
          />
          <button
            className="btn-primary"
            disabled={saving}
            onClick={() => savePrefs(prefs)}
          >
            Save
          </button>
        </div>
        <p style={{ fontSize: 12, color: "#6b7280", marginTop: 6 }}>
          Digest sends daily at 6:00 PM ET. Configure Gmail credentials in your .env file.
        </p>
      </div>

      {/* Blocked keywords */}
      <div className="settings-section">
        <h3>🚫 Blocked Keywords</h3>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
          Articles containing these words will be hidden from your feed.
        </p>
        <KeywordManager
          keywords={prefs.blocked_keywords}
          onChange={(kws) => {
            const updated = { ...prefs, blocked_keywords: kws };
            setPrefs(updated);
            savePrefs(updated);
          }}
        />
      </div>

      {/* Active sources */}
      <div className="settings-section">
        <h3>📡 Active Sources ({active.length})</h3>
        <div className="source-list">
          {active.map((s) => (
            <div key={s.id} className={`source-item ${s.active ? "" : "blocked"}`}>
              <div>
                <div className="source-name">{s.name}</div>
                <div className="source-url">{s.url}</div>
              </div>
              <div className="source-actions">
                <button
                  className={`btn-sm ${s.active ? "btn-secondary" : "btn-success"}`}
                  onClick={() => toggleSource(s, "active", !s.active)}
                >
                  {s.active ? "⏸ Pause" : "▶ Resume"}
                </button>
                <button
                  className="btn-sm btn-danger"
                  onClick={() => toggleSource(s, "blocked", true)}
                >
                  🚫 Block
                </button>
              </div>
            </div>
          ))}
        </div>

        <h3 style={{ marginTop: 20 }}>➕ Add RSS Source</h3>
        <AddSourceForm onAdd={handleAddSource} />
      </div>

      {/* Blocked sources */}
      {blocked.length > 0 && (
        <div className="settings-section">
          <h3>🚫 Blocked Sources ({blocked.length})</h3>
          <div className="source-list">
            {blocked.map((s) => (
              <div key={s.id} className="source-item blocked">
                <div>
                  <div className="source-name">{s.name}</div>
                  <div className="source-url">{s.url}</div>
                </div>
                <button
                  className="btn-sm btn-success"
                  onClick={() => toggleSource(s, "blocked", false)}
                >
                  ✓ Unblock
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
