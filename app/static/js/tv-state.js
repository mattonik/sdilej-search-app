import { buildEpisodeQueueKey, buildTvEpisodeKey, sameStringList } from "./keys.js";

export const buildTvEpisodeOutcome = (episode, episodeQueueSummary) => {
  const status = String(episode?.status || "pending");
  const resultCount = Number(episode?.result_count || 0);
  const hasMatches = resultCount > 0;
  const hasActiveQueue = Boolean(episodeQueueSummary && Array.isArray(episodeQueueSummary.jobs) && episodeQueueSummary.jobs.length);
  const isDownloaded = status === "downloaded";
  const isNoMatch = !hasMatches && ["done", "failed", "canceled"].includes(status);
  return { status, resultCount, hasMatches, hasActiveQueue, isNoMatch, isDownloaded };
};

export const matchesTvResultsFilter = (outcome, filter) => {
  if (filter === "matches") return outcome.hasMatches;
  if (filter === "queued") return outcome.hasActiveQueue;
  if (filter === "downloaded") return outcome.isDownloaded;
  if (filter === "unmatched") return outcome.isNoMatch;
  return true;
};

export const formatTvAliasSummary = (knownAliases, searchAliases) => {
  const knownCount = Array.isArray(knownAliases) ? knownAliases.length : 0;
  const searchCount = Array.isArray(searchAliases) ? searchAliases.length : 0;
  if (searchCount > 0 && knownCount > 0 && searchCount !== knownCount) {
    return `using ${searchCount} safe search aliases from ${knownCount} known aliases`;
  }
  const count = searchCount || knownCount;
  return `${count} aliases`;
};

export const buildDownloadedEpisodeState = (episode, downloadedFiles) => ({
  ...episode,
  status: "downloaded",
  result_count: 0,
  query_variants: [],
  query_errors: [],
  results: [],
  downloaded_files: Array.from(new Set(downloadedFiles || [])),
});

export const buildDownloadedTvEpisodesFromJobs = (jobs, tvLookupState, tvResultsState) => {
  const downloadedEpisodes = new Map();
  if (!Array.isArray(jobs) || !tvLookupState || !tvResultsState) return downloadedEpisodes;

  const showName = String(tvLookupState?.show?.name || "").trim().toLowerCase();
  const aliases = [
    showName,
    ...(Array.isArray(tvLookupState?.aliases) ? tvLookupState.aliases : []),
    ...(Array.isArray(tvLookupState?.search_aliases) ? tvLookupState.search_aliases : []),
    ...(Array.isArray(tvLookupState?.all_search_aliases) ? tvLookupState.all_search_aliases : []),
  ]
    .filter(Boolean)
    .map((value) => String(value).trim().toLowerCase());
  const aliasKeys = new Set(aliases);

  jobs
    .filter((job) => String(job?.status || "") === "done")
    .forEach((job) => {
      const seriesName = String(job?.series_name || "").trim().toLowerCase();
      if (!seriesName) return;
      if (aliasKeys.size && !aliasKeys.has(seriesName)) return;

      const downloaded = Array.isArray(job?.downloaded_files) ? job.downloaded_files : [];
      const seasonNumber = Number(job?.season_number || 0);
      const episodeNumber = Number(job?.episode_number || 0);
      const queueEpisodeKey = buildEpisodeQueueKey({
        seriesName: job?.series_name,
        seasonNumber,
        episodeNumber,
      });
      const episodeKey = buildTvEpisodeKey({
        seasonNumber,
        episodeNumber,
      });
      if (!queueEpisodeKey && !episodeKey) return;
      const current = downloadedEpisodes.get(queueEpisodeKey || episodeKey) || [];
      const merged = Array.from(new Set([...current, ...downloaded].filter(Boolean)));
      downloadedEpisodes.set(queueEpisodeKey || episodeKey, merged);
    });

  return downloadedEpisodes;
};

export const sameTvDownloadedEpisodeState = (episode, downloadedFiles) =>
  String(episode?.status || "") === "downloaded" && sameStringList(episode?.downloaded_files, downloadedFiles);
