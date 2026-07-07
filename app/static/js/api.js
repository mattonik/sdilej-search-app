const readJson = async (response, requestUrl) => {
  const data = await response.json();
  if (!response.ok && data && typeof data === "object") {
    data.status = response.status;
    data.request_url = requestUrl;
  }
  return { ok: response.ok, status: response.status, data };
};

const buildNetworkErrorPayload = (error, requestUrl) => ({
  error: "Network request failed.",
  error_code: "network_error",
  retryable: true,
  hint: "Check the browser console, local app health, and network connectivity.",
  details: error?.message || String(error || "unknown network error"),
  request_url: requestUrl,
  status: 0,
});

const jsonRequest = async (url, options = {}) => {
  try {
    return await readJson(await fetch(url, options), url);
  } catch (error) {
    return { ok: false, status: 0, data: buildNetworkErrorPayload(error, url) };
  }
};

export const api = {
  autocomplete(q, limit = 10) {
    return jsonRequest(`/api/autocomplete?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`);
  },
  tvLookup(payload) {
    return jsonRequest("/api/tv/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  createTvSearchJob(payload) {
    return jsonRequest("/api/tv/search-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getTvSearchJob(jobId) {
    return jsonRequest(`/api/tv/search-jobs/${encodeURIComponent(jobId)}`);
  },
  searchTvEpisode(payload) {
    return jsonRequest("/api/tv/search-episode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  cancelDownloadJob(jobId) {
    return jsonRequest(`/api/downloads/${jobId}/cancel`, { method: "POST" });
  },
  cancelDownloadJobComplete(jobId) {
    return jsonRequest(`/api/downloads/${jobId}/cancel-complete`, { method: "POST" });
  },
  retryDownloadJob(jobId) {
    return jsonRequest(`/api/downloads/${jobId}/retry`, { method: "POST" });
  },
  moveDownloadJobToTop(jobId) {
    return jsonRequest(`/api/downloads/${jobId}/top`, { method: "POST" });
  },
  deleteDownloadJob(jobId, { withData = false } = {}) {
    return jsonRequest(`/api/downloads/${jobId}${withData ? "?with_data=true" : ""}`, { method: "DELETE" });
  },
  updateDownloadJobPriority(jobId, payload) {
    return jsonRequest(`/api/downloads/${jobId}/priority`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  listDownloads(limit = 200) {
    return jsonRequest(`/api/downloads?limit=${encodeURIComponent(limit)}`);
  },
  listMovieDiscoveryGenres(language = "sk-SK") {
    return jsonRequest(`/api/discovery/movie-genres?language=${encodeURIComponent(language)}`);
  },
  discoverMovies(params) {
    const query = new URLSearchParams(params || {});
    return jsonRequest(`/api/discovery/movies?${query.toString()}`);
  },
  scanMissingTv(payload) {
    return jsonRequest("/api/library/tv/missing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  listLocalTvShows({ q = "", isKids = false, limit = 12 } = {}) {
    return jsonRequest(
      `/api/library/tv/shows?q=${encodeURIComponent(q)}&is_kids=${encodeURIComponent(isKids ? "true" : "false")}&limit=${encodeURIComponent(limit)}`
    );
  },
  listKidsCatalogShows() {
    return jsonRequest("/api/kids-catalog/shows");
  },
  getKidsCatalogShow(slug) {
    return jsonRequest(`/api/kids-catalog/shows/${encodeURIComponent(slug)}`);
  },
  resolveKidsCatalogEpisode(payload) {
    return jsonRequest("/api/kids-catalog/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getDownloadSettings() {
    return jsonRequest("/api/downloads/settings");
  },
  listSaved(limit = 1000) {
    return jsonRequest(`/api/saved?limit=${encodeURIComponent(limit)}`);
  },
  enqueueDownload(payload) {
    return jsonRequest("/api/downloads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  classifyMedia(payload) {
    return jsonRequest("/api/media/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  updateDownloadClassification(jobId, payload) {
    return jsonRequest(`/api/downloads/${jobId}/classification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  resolveMovieInfoLink(payload) {
    return jsonRequest("/api/movie/info-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  saveCandidate(payload) {
    return jsonRequest("/api/saved", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getAccount() {
    return jsonRequest("/api/account");
  },
  getYoutubeAuth() {
    return jsonRequest("/api/youtube-auth");
  },
  clearDownloads(payload) {
    return jsonRequest("/api/downloads/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  updateDownloadSettings(payload) {
    return jsonRequest("/api/downloads/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  setAccount(payload) {
    return jsonRequest("/api/account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  deleteAccount() {
    return jsonRequest("/api/account", { method: "DELETE" });
  },
  setYoutubeAuth(payload) {
    return jsonRequest("/api/youtube-auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  deleteYoutubeAuth() {
    return jsonRequest("/api/youtube-auth", { method: "DELETE" });
  },
};
