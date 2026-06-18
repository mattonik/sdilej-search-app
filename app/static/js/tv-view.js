import { esc, stripHtml, truncateText } from "./dom-utils.js";
import { pluralize, queueBadgeLabelForStatus } from "./formatters.js";
import { buildTvEpisodeKey } from "./keys.js";

export const createTvViewHelpers = ({
  state,
  buildActiveSearchAliases,
}) => {
  const buildTvResultsStatsHtml = (overview) => `
    <span><strong>${esc(overview.totalEpisodes)}</strong> episodes searched</span>
    <span><strong>${esc(overview.matchedEpisodes)}</strong> with matches</span>
    <span><strong>${esc(overview.queuedEpisodes)}</strong> in queue</span>
    <span><strong>${esc(overview.downloadedEpisodes)}</strong> downloaded</span>
    <span><strong>${esc(overview.noMatchEpisodes)}</strong> no matches</span>
  `;

  const buildTvResultsFilterChipsHtml = (overview) => {
    const chips = [
      { key: "all", label: `All (${overview.totalEpisodes})`, count: overview.totalEpisodes },
      { key: "matches", label: `With matches (${overview.matchedEpisodes})`, count: overview.matchedEpisodes },
      { key: "queued", label: `In queue (${overview.queuedEpisodes})`, count: overview.queuedEpisodes },
      { key: "downloaded", label: `Downloaded (${overview.downloadedEpisodes})`, count: overview.downloadedEpisodes },
      { key: "unmatched", label: `No matches (${overview.noMatchEpisodes})`, count: overview.noMatchEpisodes },
    ];
    return chips
      .map(
        (chip) =>
          `<button type="button" class="tv-results-filter-chip btn btn-pill${state.tvResultsFilter === chip.key ? " active" : ""}" data-filter="${esc(chip.key)}">${esc(chip.label)}</button>`
      )
      .join("");
  };

  const buildTvResultsToolbarHtml = (overview) => `
    <div class="tv-results-toolbar">
      <div class="tv-results-stats">${buildTvResultsStatsHtml(overview)}</div>
      <div class="tv-results-filters">${buildTvResultsFilterChipsHtml(overview)}</div>
    </div>
  `;

  const buildTvSeasonSummaryBits = (season) => [
    `${season.stats.matchedEpisodes} matched`,
    `${season.stats.queuedEpisodes} in queue`,
    `${season.stats.downloadedEpisodes} downloaded`,
    `${season.stats.noMatchEpisodes} no matches`,
  ];

  const parseSizeToBytes = (size) => {
    const text = String(size || "").trim();
    if (!text) return null;
    const match = text.match(/^([\d,.]+)\s*([kmgtp]?i?b)?$/i);
    if (!match) return null;
    const value = Number(match[1].replace(/,/g, ""));
    if (!Number.isFinite(value)) return null;
    const unit = String(match[2] || "B").toUpperCase();
    const multipliers = {
      B: 1,
      KB: 1024,
      KIB: 1024,
      MB: 1024 ** 2,
      MIB: 1024 ** 2,
      GB: 1024 ** 3,
      GIB: 1024 ** 3,
      TB: 1024 ** 4,
      TIB: 1024 ** 4,
      PB: 1024 ** 5,
      PIB: 1024 ** 5,
    };
    const multiplier = multipliers[unit] || 1;
    return value * multiplier;
  };

  const sortTvResults = (results, sortMode) => {
    const items = Array.isArray(results) ? results : [];
    const decorated = items.map((item, index) => ({
      item,
      index,
      sizeBytes: parseSizeToBytes(item?.size),
      languageScore: Number(item?.language_score ?? 0) || 0,
    }));

    const compareBySize = (left, right, direction) => {
      const leftSize = left.sizeBytes;
      const rightSize = right.sizeBytes;
      if (leftSize == null && rightSize == null) return 0;
      if (leftSize == null) return 1;
      if (rightSize == null) return -1;
      if (leftSize === rightSize) return 0;
      return direction === "asc" ? leftSize - rightSize : rightSize - leftSize;
    };

    const next = decorated.sort((left, right) => {
      if (sortMode === "size_asc" || sortMode === "size_desc") {
        const sizeComparison = compareBySize(left, right, sortMode === "size_asc" ? "asc" : "desc");
        if (sizeComparison !== 0) return sizeComparison;
      }

      if (sortMode === "best") {
        if (left.index !== right.index) return left.index - right.index;
      } else {
        if (left.languageScore !== right.languageScore) return right.languageScore - left.languageScore;
        if (left.index !== right.index) return left.index - right.index;
      }

      const leftTitle = String(left.item?.title || "");
      const rightTitle = String(right.item?.title || "");
      if (leftTitle !== rightTitle) return leftTitle.localeCompare(rightTitle);
      return left.index - right.index;
    });

    return next.map((entry) => entry.item);
  };

  const renderTvResultItem = ({
    item,
    queueEpisodeKey,
    showName,
    seasonNumber,
    episodeNumber,
    actionLabel,
    sortMode = "best",
    showQueries = false,
    isPrimary = false,
  }) => {
    const resultKey = item?.detail_url || item?.file_id || `${showName}-${seasonNumber}-${episodeNumber}-${item?.title || ""}`;
    const queryHits = Array.isArray(item?.query_hits) ? Array.from(new Set(item.query_hits.filter(Boolean))) : [];
    const playableLabel = item?.playable ? "Playable" : "Not playable";
    const sizeLabel = item?.size ? `Size: ${item.size}` : "Size: n/a";
    const queueActionClass = isPrimary ? "btn btn-primary" : "btn btn-secondary";
    const queryHtml = showQueries && queryHits.length ? `<div class="tv-result-queries">Queries: ${esc(queryHits.join(", "))}</div>` : "";
    return `
      <article
        class="tv-result-item${isPrimary ? " tv-result-item-primary" : ""}"
        data-result-key="${esc(resultKey)}"
        ${item?.detail_url ? `data-detail-url="${esc(item.detail_url)}"` : ""}
        ${item?.file_id ? `data-file-id="${esc(item.file_id)}"` : ""}
      >
          <div class="tv-result-main">
          <div class="tv-result-title-row">
            <a href="${esc(item?.detail_url || "#")}" target="_blank" rel="noreferrer">${esc(item?.title || "")}</a>
            ${item?.year ? `<span>Year: ${esc(item.year)}</span>` : `<span>Year: n/a</span>`}
          </div>
          <div class="tv-result-meta-row">
            <span>Lang score: ${esc(item?.language_score ?? 0)}</span>
            <span class="tv-result-size">${esc(sizeLabel)}</span>
            <span>Ext: ${esc(item?.extension || "n/a")}</span>
            <span>${esc(playableLabel)}</span>
          </div>
          ${queryHtml}
        </div>
        <div class="tv-result-actions">
          <button
            type="button"
            class="tv-queue-btn ${queueActionClass}"
            data-detail-url="${esc(item?.detail_url || "")}"
            data-file-id="${esc(item?.file_id || "")}"
            data-title="${esc(item?.title || "")}"
            data-series-name="${esc(showName || "")}"
            data-season-number="${esc(seasonNumber || "")}"
            data-episode-number="${esc(episodeNumber || "")}"
            data-default-label="${esc(actionLabel)}"
          >
            ${esc(actionLabel)}
          </button>
          <button
            type="button"
            class="tv-copy-link-btn btn btn-secondary btn-sm"
            data-copy-value="${esc(item?.detail_url || "")}"
            data-copy-label="Copy link"
          >
            Copy link
          </button>
          <button
            type="button"
            class="queue-manage-btn btn btn-secondary btn-sm hidden"
            data-job-id=""
            aria-label="Manage queue item"
          >
            Manage
          </button>
        </div>
        <div class="tv-result-queue-state hidden" data-mode=""></div>
      </article>
    `;
  };

  const renderTvSearchDetails = ({ episodeKey, payload, seasonNumber, effectiveEpisode, allSearchAliases, activeSearchAliases }) => `
    <details class="tv-episode-search-details" data-episode-key="${esc(episodeKey)}">
      <summary>Search details</summary>
      <div class="tv-episode-search-details-body">
        <div class="tv-search-details-grid">
          <div>
            <strong>Episode</strong>
            <span>${esc(effectiveEpisode.episode_code || `S${String(seasonNumber).padStart(2, "0")}E${String(effectiveEpisode.episode_number || "").padStart(2, "0")}`)}</span>
          </div>
          <div>
            <strong>Episode title</strong>
            <span>${esc(effectiveEpisode.episode_name || "n/a")}</span>
          </div>
          <div>
            <strong>Search aliases</strong>
            <span>${esc((activeSearchAliases || []).join(", ") || "none")}</span>
          </div>
          <div>
            <strong>All aliases</strong>
            <span>${esc((allSearchAliases || []).join(", ") || "none")}</span>
          </div>
        </div>
      </div>
    </details>
  `;

  const getTvEpisodeOutcome = (episode, episodeQueueSummary) => {
    const status = String(episode?.status || "pending");
    const resultCount = Number(episode?.result_count || 0);
    const hasMatches = resultCount > 0;
    const hasActiveQueue = Boolean(episodeQueueSummary && Array.isArray(episodeQueueSummary.jobs) && episodeQueueSummary.jobs.length);
    const isDownloaded = status === "downloaded";
    const isNoMatch = !hasMatches && ["done", "failed", "canceled"].includes(status);
    return { status, resultCount, hasMatches, hasActiveQueue, isNoMatch, isDownloaded };
  };

  const matchesTvResultsFilter = (outcome) => {
    if (state.tvResultsFilter === "matches") return outcome.hasMatches;
    if (state.tvResultsFilter === "queued") return outcome.hasActiveQueue;
    if (state.tvResultsFilter === "downloaded") return outcome.isDownloaded;
    if (state.tvResultsFilter === "unmatched") return outcome.isNoMatch;
    return true;
  };

  const buildTvResultsViewModel = (payload) => {
    const seasons = Array.isArray(payload?.seasons) ? payload.seasons : [];
    const allSearchAliases = buildActiveSearchAliases(payload);
    const activeSearchAliases = Array.isArray(payload?.search_aliases) && payload.search_aliases.length ? payload.search_aliases : allSearchAliases;
      const seasonViewModels = seasons.map((season) => {
        const episodeViewModels = (Array.isArray(season.episodes) ? season.episodes : []).map((episode) => {
          const queueEpisodeKey = buildTvEpisodeKey({
            seasonNumber: episode?.season_number,
            episodeNumber: episode?.episode_number,
          });
          const episodeQueueSummary = state.activeQueueState.episodeJobs.get(queueEpisodeKey) || null;
          const effectiveEpisode = state.tvEpisodeSearchOverrides.get(
            `${season.season_number}:${episode?.episode_number}`
          ) || episode;
          const outcome = getTvEpisodeOutcome(effectiveEpisode, episodeQueueSummary);
          const sortMode = state.tvEpisodeResultSorts.get(`${season.season_number}:${episode?.episode_number}`) || "best";
          const results = sortTvResults(Array.isArray(effectiveEpisode?.results) ? effectiveEpisode.results : [], sortMode);
          const bestResult = results[0] || null;
          const alternativeResults = results.slice(1);
        return {
          episodeKey: `${season.season_number}:${episode?.episode_number}`,
          queueEpisodeKey,
          effectiveEpisode,
          outcome,
          sortMode,
          bestResult,
          alternativeResults,
          episodeQueueSummary,
        };
      });

      const stats = episodeViewModels.reduce(
        (acc, item) => {
          acc.totalEpisodes += 1;
          if (item.outcome.hasMatches) acc.matchedEpisodes += 1;
          if (item.outcome.hasActiveQueue) acc.queuedEpisodes += 1;
          if (item.outcome.isDownloaded) acc.downloadedEpisodes += 1;
          if (item.outcome.isNoMatch) acc.noMatchEpisodes += 1;
          return acc;
        },
        { totalEpisodes: 0, matchedEpisodes: 0, queuedEpisodes: 0, downloadedEpisodes: 0, noMatchEpisodes: 0, queueStatus: "queued" }
      );

      return {
        season_number: season.season_number,
        season,
        episodeViewModels,
        visibleEpisodeViewModels: episodeViewModels.filter((vm) => matchesTvResultsFilter(vm.outcome)),
        stats,
      };
    });

    const visibleSeasons = seasonViewModels.filter((season) => season.visibleEpisodeViewModels.length > 0);
    const totalEpisodes = seasonViewModels.reduce((acc, season) => acc + season.stats.totalEpisodes, 0);
    const matchedEpisodes = seasonViewModels.reduce((acc, season) => acc + season.stats.matchedEpisodes, 0);
    const queuedEpisodes = seasonViewModels.reduce((acc, season) => acc + season.stats.queuedEpisodes, 0);
    const downloadedEpisodes = seasonViewModels.reduce((acc, season) => acc + season.stats.downloadedEpisodes, 0);
    const noMatchEpisodes = seasonViewModels.reduce((acc, season) => acc + season.stats.noMatchEpisodes, 0);

    return {
      bannerHtml: "",
      seasonViewModels,
      visibleSeasons,
      overview: { totalEpisodes, matchedEpisodes, queuedEpisodes, downloadedEpisodes, noMatchEpisodes },
      allSearchAliases,
      activeSearchAliases,
    };
  };

  return {
    buildTvResultsStatsHtml,
    buildTvResultsFilterChipsHtml,
    buildTvResultsToolbarHtml,
    buildTvResultsViewModel,
    buildTvSeasonSummaryBits,
    renderTvResultItem,
    renderTvSearchDetails,
    getTvEpisodeOutcome,
    matchesTvResultsFilter,
  };
};
