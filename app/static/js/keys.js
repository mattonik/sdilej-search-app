export const TV_ACTIVE_JOB_KEY = "activeTvSearchJobId";
export const FILE_RESULTS_VIEW_KEY = "fileResultsView";
export const FILE_RESULTS_FILTER_KEY = "fileResultsFilter";
export const FILE_SEARCH_ADVANCED_KEY = "fileSearchAdvancedOpen";
export const ACTIVE_QUEUE_STATUSES = new Set(["queued", "running"]);

export const normalizeQueueTextKey = (value) =>
  String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

export const normalizeDetailQueueKey = (value) => {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw, window.location.origin);
    return `${url.pathname.replace(/\/+$/, "")}${url.search}`.toLowerCase();
  } catch (_) {
    return raw.toLowerCase();
  }
};

export const buildFileQueueKey = ({ fileId, detailUrl }) => {
  const numericFileId = Number(fileId);
  if (Number.isFinite(numericFileId) && numericFileId > 0) {
    return `id:${numericFileId}`;
  }
  const normalizedUrl = normalizeDetailQueueKey(detailUrl);
  return normalizedUrl ? `url:${normalizedUrl}` : "";
};

export const buildEpisodeQueueKey = ({ seriesName, seasonNumber, episodeNumber }) => {
  const normalizedSeries = normalizeQueueTextKey(seriesName);
  const season = Number(seasonNumber);
  const episode = Number(episodeNumber);
  if (!normalizedSeries || !Number.isFinite(season) || season <= 0 || !Number.isFinite(episode) || episode <= 0) {
    return "";
  }
  return `${normalizedSeries}:${season}:${episode}`;
};

export const buildTvEpisodeKey = ({ seasonNumber, episodeNumber }) => {
  const season = Number(seasonNumber);
  const episode = Number(episodeNumber);
  if (!Number.isFinite(season) || season <= 0 || !Number.isFinite(episode) || episode <= 0) {
    return "";
  }
  return `${season}:${episode}`;
};

export const sameStringList = (left, right) =>
  JSON.stringify(Array.isArray(left) ? left : []) === JSON.stringify(Array.isArray(right) ? right : []);
