const BASE = "/api";

async function req(method, path, body) {
  const opts = {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  // Articles
  getArticles: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
    ).toString();
    return req("GET", `/articles${qs ? "?" + qs : ""}`);
  },
  setFeedback: (id, feedback) =>
    req("POST", `/articles/${id}/feedback`, { feedback }),

  // Sources
  getSources: () => req("GET", "/sources"),
  blockSource: (source_name) => req("POST", "/sources/block", { source_name }),
  updateSource: (id, data) => req("PUT", `/sources/${id}`, data),
  addSource: (name, url) => req("POST", "/sources", { name, url }),

  // Digest
  getDigestPreview: () => req("GET", "/digest/preview"),
  sendDigest: () => req("POST", "/digest/send"),

  // Fetch
  runFetch: () => req("POST", "/run-fetch"),
  runFetchSync: () => req("POST", "/run-fetch/sync"),

  // Preferences
  getPreferences: () => req("GET", "/preferences"),
  updatePreferences: (data) => req("PUT", "/preferences", data),

  // Stats
  getStats: () => req("GET", "/stats"),
};
