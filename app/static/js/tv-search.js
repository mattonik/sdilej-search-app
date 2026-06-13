import { basenameFromPath, esc, stripHtml, truncateText } from "./dom-utils.js";
import {
  ACTIVE_QUEUE_STATUSES,
  buildEpisodeQueueKey,
  buildFileQueueKey,
  buildTvEpisodeKey,
  normalizeQueueTextKey,
  sameStringList,
} from "./keys.js";
import { pluralize, queueBadgeLabelForStatus, queueButtonLabelForStatus } from "./formatters.js";
import {
  clearActiveTvSearchJobId,
  writeActiveTvSearchJobId,
  writeSearchMode,
} from "./storage-state.js";

export const initTvSearch = ({
  elements,
  api,
  state,
  setActiveQueueStateFromJobs,
  openQueueDialog,
}) => {
  const {
    categorySelect,
    sortSelect,
    languageInput,
    languageScopeSelect,
    strictDubbingInput,
    releaseYearInput,
    maxResultsInput,
    fileSearchModeBtn,
    tvSearchModeBtn,
    fileSearchPanel,
    tvModePanel,
    queryInput,
    suggestions,
    fileResultsBlocks,
    tvActiveFilters,
    tvShowSummaryCard,
    tvLookupInfo,
    tvSeasonPicker,
    tvLookupForm,
    tvShowName,
    tvSearchBtn,
    tvResults,
    tvFilterCategory,
    tvFilterLanguage,
    tvFilterLanguageScope,
    tvFilterStrictDubbing,
    tvFilterMaxResults,
    tvStatus,
  } = elements;

  let activeTvSearchJobId = state.activeTvSearchJobId;
  let tvLookupState = state.tvLookupState;
  let tvResultsState = state.tvResultsState;
  let tvResultsFilter = state.tvResultsFilter;
  let tvJobPollInFlight = state.tvJobPollInFlight;
  let tvEpisodeSearchOverrides = state.tvEpisodeSearchOverrides;
  let tvEpisodeSearchesInFlight = state.tvEpisodeSearchesInFlight;
  let tvShowSummarySignature = state.tvShowSummarySignature;
  let searchMode = state.searchMode;
  let activeQueueState = state.activeQueueState;

      const renderTvActiveFilters = () => {
        const languageValue = languageInput.value.trim();
        const languageScope = languageScopeSelect.value || "any";
        const strict = Boolean(strictDubbingInput.checked);
        const category = categorySelect.value || "video";
        const maxPerVariantRaw = Number(maxResultsInput.value || 120);
        const maxPerVariant = Number.isFinite(maxPerVariantRaw) && maxPerVariantRaw > 0 ? Math.min(500, maxPerVariantRaw) : 120;
        const languageText = languageValue ? `${languageValue} (${languageScope}${strict ? ", strict" : ""})` : "none";
        tvActiveFilters.innerHTML = `
          <strong>Active filters:</strong>
          Category <code>${esc(category)}</code> |
          Language <code>${esc(languageText)}</code> |
          Max results/episode query <code>${esc(maxPerVariant)}</code>
        `;
      };

      const formatTvAliasSummary = (knownAliases, searchAliases) => {
        const knownCount = Array.isArray(knownAliases) ? knownAliases.length : 0;
        const searchCount = Array.isArray(searchAliases) ? searchAliases.length : 0;
        if (searchCount > 0 && knownCount > 0 && searchCount !== knownCount) {
          return `using ${searchCount} safe search aliases from ${knownCount} known aliases`;
        }
        const count = searchCount || knownCount;
        return `${count} aliases`;
      };

      const renderTvShowSummary = (state) => {
        const show = state?.show || null;
        const metadata = state?.title_metadata || null;
        if (!show && !metadata) {
          tvShowSummarySignature = "";
          tvShowSummaryCard.classList.add("hidden");
          if (tvShowSummaryCard.innerHTML) {
            tvShowSummaryCard.innerHTML = "";
          }
          return;
        }

        const genreValues =
          (Array.isArray(show?.genres) && show.genres.length ? show.genres : null) ||
          (Array.isArray(metadata?.genres) ? metadata.genres : []);
        const summaryText = truncateText(stripHtml(metadata?.summary || show?.summary || ""));
        const premiered = String(show?.premiered || "").trim();
        const premieredLabel = premiered ? premiered.slice(0, 4) : "";
        const metaBits = [premieredLabel, show?.language || "", ...(genreValues || [])].filter(Boolean);
        const hasImage = Boolean(show?.image_url);
        const nextSignature = JSON.stringify({
          imageUrl: show?.image_url || "",
          title: show?.name || metadata?.canonical_title || "",
          originalTitle: metadata?.original_title || "",
          metaBits,
          summaryText,
          hasImage,
        });

        tvShowSummaryCard.classList.remove("hidden");
        tvShowSummaryCard.classList.toggle("text-only", !hasImage);
        if (tvShowSummarySignature === nextSignature) {
          return;
        }
        tvShowSummarySignature = nextSignature;
        tvShowSummaryCard.innerHTML = `
          ${hasImage ? `<img src="${esc(show.image_url)}" alt="${esc(show?.name || metadata?.canonical_title || "Show poster")}" loading="lazy" />` : ""}
          <div class="tv-show-summary-body">
            <div class="tv-show-summary-title-row">
              <strong>${esc(show?.name || metadata?.canonical_title || "")}</strong>
              ${
                metadata?.original_title && metadata.original_title !== show?.name
                  ? `<span>${esc(metadata.original_title)}</span>`
                  : ""
              }
            </div>
            ${metaBits.length ? `<div class="tv-show-summary-meta">${metaBits.map((bit) => `<span>${esc(bit)}</span>`).join("")}</div>` : ""}
            ${summaryText ? `<p>${esc(summaryText)}</p>` : ""}
          </div>
        `;
      };

      const syncFileFiltersToTvEditor = () => {
        if (tvFilterCategory) tvFilterCategory.value = categorySelect.value || "video";
        if (tvFilterLanguage) tvFilterLanguage.value = languageInput.value || "";
        if (tvFilterLanguageScope) tvFilterLanguageScope.value = languageScopeSelect.value || "any";
        if (tvFilterStrictDubbing) tvFilterStrictDubbing.checked = Boolean(strictDubbingInput.checked);
        if (tvFilterMaxResults) tvFilterMaxResults.value = maxResultsInput.value || "120";
      };

      const syncTvEditorToFileFilters = () => {
        if (tvFilterCategory) categorySelect.value = tvFilterCategory.value || "video";
        if (tvFilterLanguage) languageInput.value = tvFilterLanguage.value || "";
        if (tvFilterLanguageScope) languageScopeSelect.value = tvFilterLanguageScope.value || "any";
        if (tvFilterStrictDubbing) strictDubbingInput.checked = Boolean(tvFilterStrictDubbing.checked);
        if (tvFilterMaxResults) maxResultsInput.value = tvFilterMaxResults.value || "120";
      };

      const updateTvSearchButtonState = () => {
        const canSearch =
          Boolean(tvLookupState?.show?.id) &&
          selectedTvSeasons().length > 0 &&
          tvEpisodeSelectionIsValid();
        tvSearchBtn.disabled = !canSearch;
      };

      const setSearchMode = (mode) => {
        searchMode = mode === "tv" ? "tv" : "file";
        state.searchMode = searchMode;
        const tvActive = searchMode === "tv";
        fileSearchModeBtn.classList.toggle("active", !tvActive);
        tvSearchModeBtn.classList.toggle("active", tvActive);
        fileSearchPanel.classList.toggle("hidden", tvActive);
        tvModePanel.classList.toggle("hidden", !tvActive);
        fileResultsBlocks.forEach((node) => {
          node.classList.toggle("hidden", tvActive);
        });
        if (tvActive) {
          renderTvActiveFilters();
          updateTvSearchButtonState();
        }
        writeSearchMode(searchMode);
      };

      fileSearchModeBtn.addEventListener("click", () => setSearchMode("file"));
      tvSearchModeBtn.addEventListener("click", () => setSearchMode("tv"));

      queryInput?.addEventListener("input", () => {
        const q = queryInput.value.trim();
        clearTimeout(timer);
        if (q.length < 2) {
          suggestions.innerHTML = "";
          return;
        }

        timer = setTimeout(async () => {
          try {
            const { ok, data: payload } = await api.autocomplete(q, 10);
            if (!ok) return;
            suggestions.innerHTML = "";
            for (const suggestion of payload.suggestions || []) {
              const opt = document.createElement("option");
              opt.value = suggestion;
              suggestions.appendChild(opt);
            }
          } catch (_) {
            // Ignore autocomplete failures; main search still works.
          }
        }, 180);
        state.timer = timer;
      });

      const runTvLookup = async () => {
        const showName = tvShowName.value.trim();
        if (!showName) {
          setTvStatus("Show name is required.", "error");
          return;
        }
        setActiveTvSearchJobId(null);
        setTvStatus("Loading show metadata and seasons...", "neutral");
        tvLookupInfo.textContent = "";
        tvSeasonPicker.innerHTML = "";
        tvResults.innerHTML = "";
        renderTvShowSummary(null);
        tvResultsState = null;
        state.tvResultsState = tvResultsState;
        tvResultsFilter = "all";
        state.tvResultsFilter = tvResultsFilter;
        tvEpisodeSearchOverrides = new Map();
        state.tvEpisodeSearchOverrides = tvEpisodeSearchOverrides;
        tvEpisodeSearchesInFlight = new Set();
        state.tvEpisodeSearchesInFlight = tvEpisodeSearchesInFlight;
        tvLookupState = null;
        state.tvLookupState = tvLookupState;
        updateTvSearchButtonState();
        try {
          const { ok, data } = await api.tvLookup({ show_name: showName });
          if (!ok) {
            setTvStatus(data.error || "TV lookup failed.", "error");
            return;
          }
          tvLookupState = {
            ...data,
            all_search_aliases: data.all_search_aliases || data.search_aliases || [],
          };
          state.tvLookupState = tvLookupState;
          const show = data.show || {};
          tvLookupInfo.innerHTML = `
            <strong>${esc(show.name || showName)}</strong>
            <span> (${esc(data.season_count || 0)} seasons, ${esc(data.episode_count || 0)} episodes, ${esc(formatTvAliasSummary(data.aliases || [], data.search_aliases || []))}, source: ${esc(show.source || "tvmaze")})</span>
          `;
          renderTvShowSummary(tvLookupState);
          renderTvSeasonPicker(data.seasons || []);
          setTvStatus("Seasons loaded. Select seasons and run search.", "ok");
          updateTvSearchButtonState();
        } catch (_) {
          tvLookupState = null;
          state.tvLookupState = tvLookupState;
          renderTvShowSummary(null);
          updateTvSearchButtonState();
          setTvStatus("TV lookup failed.", "error");
        }
      };

      tvLookupForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await runTvLookup();
      });

      tvSearchBtn.addEventListener("click", async () => {
        if (!tvLookupState || !tvLookupState.show) {
          setTvStatus("Load a TV show first.", "error");
          return;
        }
        const seasons = selectedTvSeasons();
        if (!seasons.length) {
          setTvStatus("Select at least one season.", "error");
          return;
        }
        if (!tvEpisodeSelectionIsValid()) {
          setTvStatus("For seasons in 'Selected episodes' mode, choose at least one episode.", "error");
          return;
        }
        const episodesBySeason = selectedTvEpisodesBySeason();

        setTvStatus("Starting background TV search...", "neutral");
        tvResults.innerHTML = "";
        tvResultsState = null;
        state.tvResultsState = tvResultsState;
        tvResultsFilter = "all";
        state.tvResultsFilter = tvResultsFilter;
        tvEpisodeSearchOverrides = new Map();
        state.tvEpisodeSearchOverrides = tvEpisodeSearchOverrides;
        tvEpisodeSearchesInFlight = new Set();
        state.tvEpisodeSearchesInFlight = tvEpisodeSearchesInFlight;
        const maxPerVariantRaw = Number(maxResultsInput.value || 120);
        const maxPerVariant = Number.isFinite(maxPerVariantRaw) && maxPerVariantRaw > 0 ? Math.min(500, maxPerVariantRaw) : 120;
        try {
          const { ok, data } = await api.createTvSearchJob({
              show_id: tvLookupState.show.id,
              show_name: tvLookupState.show.name || tvShowName.value.trim(),
              seasons,
              episodes_by_season: episodesBySeason,
              aliases: tvLookupState.aliases || [],
              title_metadata: tvLookupState.title_metadata || null,
              category: categorySelect.value || "video",
              language: languageInput.value.trim() || null,
              language_scope: languageScopeSelect.value || "any",
              strict_dubbing: Boolean(strictDubbingInput.checked),
              max_results_per_variant: maxPerVariant,
          });
          if (!ok) {
            setTvStatus(data.error || "TV search failed.", "error");
            return;
          }
          setActiveTvSearchJobId(data.id);
          try {
            renderTvResults(data);
          } catch (error) {
            console.error("TV search render failed", error);
            setTvStatus("TV render failed.", "error");
            return;
          }
          setTvStatus(`TV search job #${data.id} queued in the background.`, "ok");
          await refreshActiveTvSearchJob({ force: true });
        } catch (_) {
          setTvStatus("TV search failed.", "error");
        }
      });

      const setDownloadStatus = (text, mode = "neutral") => {
        downloadStatus.textContent = text;
        downloadStatus.dataset.mode = mode;
      };

      const setTvStatus = (text, mode = "neutral") => {
        tvStatus.textContent = text;
        tvStatus.dataset.mode = mode;
      };

      const setActiveTvSearchJobId = (jobId) => {
        activeTvSearchJobId = jobId ? String(jobId) : null;
        state.activeTvSearchJobId = activeTvSearchJobId;
        if (activeTvSearchJobId) {
          writeActiveTvSearchJobId(activeTvSearchJobId);
        } else {
          clearActiveTvSearchJobId();
        }
      };

      const selectedTvSeasons = () =>
        Array.from(tvSeasonPicker.querySelectorAll("input.tv-season-check:checked"))
          .map((el) => Number(el.value))
          .filter((value) => Number.isFinite(value) && value > 0);

      const selectedTvEpisodesBySeason = () => {
        const selected = {};
        tvSeasonPicker.querySelectorAll(".tv-season-select").forEach((row) => {
          const seasonNumber = Number(row.dataset.seasonNumber || 0);
          if (!Number.isFinite(seasonNumber) || seasonNumber < 1) return;
          const seasonChecked = Boolean(row.querySelector("input.tv-season-check")?.checked);
          if (!seasonChecked) return;
          const mode = row.querySelector("select.tv-episode-mode")?.value || "all";
          if (mode !== "selected") return;
          const episodes = Array.from(row.querySelectorAll("input.tv-episode-check:checked"))
            .map((el) => Number(el.value))
            .filter((value) => Number.isFinite(value) && value > 0)
            .sort((a, b) => a - b);
          selected[String(seasonNumber)] = Array.from(new Set(episodes));
        });
        return selected;
      };

      const tvEpisodeSelectionIsValid = () => {
        const selectedSeasons = selectedTvSeasons();
        if (!selectedSeasons.length) return false;
        let valid = true;
        tvSeasonPicker.querySelectorAll(".tv-season-select").forEach((row) => {
          const seasonChecked = Boolean(row.querySelector("input.tv-season-check")?.checked);
          if (!seasonChecked) return;
          const mode = row.querySelector("select.tv-episode-mode")?.value || "all";
          if (mode !== "selected") return;
          const selectedEpisodeCount = row.querySelectorAll("input.tv-episode-check:checked").length;
          if (selectedEpisodeCount < 1) {
            valid = false;
          }
        });
        return valid;
      };

      const refreshActiveTvSearchJob = async ({ force = false } = {}) => {
        if (!activeTvSearchJobId || tvJobPollInFlight) return;
        if (!force && document.visibilityState === "hidden") return;

        tvJobPollInFlight = true;
        state.tvJobPollInFlight = tvJobPollInFlight;
        try {
          const { ok, status, data } = await api.getTvSearchJob(activeTvSearchJobId);
          if (!ok) {
            if (status === 404) {
              setActiveTvSearchJobId(null);
            }
            setTvStatus(data.error || "TV search job is unavailable.", "error");
            return;
          }

          tvLookupState = {
            show: data.show || tvLookupState?.show || null,
            title_metadata: data.title_metadata || tvLookupState?.title_metadata || null,
            aliases: data.aliases || tvLookupState?.aliases || [],
            all_search_aliases: data.all_search_aliases || tvLookupState?.all_search_aliases || data.search_aliases || [],
            search_aliases: data.search_aliases || tvLookupState?.search_aliases || [],
            seasons: data.seasons || tvLookupState?.seasons || [],
          };
          state.tvLookupState = tvLookupState;
          if (tvLookupState.show) {
            tvLookupInfo.innerHTML = `
              <strong>${esc(tvLookupState.show.name || "")}</strong>
              <span> (${esc(Number(data.total_episodes || 0))} selected episodes, ${esc(formatTvAliasSummary(data.aliases || [], data.search_aliases || []))})</span>
            `;
          }
          renderTvShowSummary(tvLookupState);
          try {
            renderTvResults(data);
          } catch (error) {
            console.error("TV search refresh render failed", error);
            setTvStatus("TV render failed.", "error");
            return;
          }

          const completed = Number(data.completed_episodes || 0);
          const total = Number(data.total_episodes || 0);
          if (data.status === "done") {
            setTvStatus(`TV search complete: ${completed}/${total} episodes processed.`, "ok");
            setActiveTvSearchJobId(null);
          } else if (data.status === "failed") {
            setTvStatus(data.error || "TV search failed.", "error");
            setActiveTvSearchJobId(null);
          } else if (data.status === "canceled") {
            setTvStatus("TV search canceled.", "neutral");
            setActiveTvSearchJobId(null);
          } else {
            setTvStatus(`TV search running: ${completed}/${total} episodes processed.`, "neutral");
          }
        } catch (_) {
          setTvStatus("TV search job refresh failed.", "error");
        } finally {
          tvJobPollInFlight = false;
          state.tvJobPollInFlight = tvJobPollInFlight;
        }
      };

      const captureTvResultsUiState = () => {
        const openSeasonKeys = new Set(
          Array.from(tvResults.querySelectorAll("details.tv-season[open]"))
            .map((node) => String(node.dataset.seasonKey || ""))
            .filter(Boolean)
        );
        const openAlternativeKeys = new Set(
          Array.from(tvResults.querySelectorAll("details.tv-episode-alternatives[open]"))
            .map((node) => String(node.dataset.episodeKey || ""))
            .filter(Boolean)
        );
        const openSearchDetailKeys = new Set(
          Array.from(tvResults.querySelectorAll("details.tv-episode-search-details[open]"))
            .map((node) => String(node.dataset.episodeKey || ""))
            .filter(Boolean)
        );

        let scrollAnchor = null;
        const anchorCandidates = Array.from(tvResults.querySelectorAll(".tv-episode-card[data-episode-key], details.tv-season[data-season-key]"));
        for (const node of anchorCandidates) {
          const rect = node.getBoundingClientRect();
          if (rect.bottom <= 0) continue;
          scrollAnchor = node.dataset.episodeKey
            ? { kind: "episode", key: String(node.dataset.episodeKey), top: rect.top }
            : { kind: "season", key: String(node.dataset.seasonKey), top: rect.top };
          break;
        }

        return { openSeasonKeys, openAlternativeKeys, openSearchDetailKeys, scrollAnchor };
      };

      const restoreTvResultsUiState = (state) => {
        if (!state) return;

        tvResults.querySelectorAll("details.tv-season[data-season-key]").forEach((node) => {
          node.open = state.openSeasonKeys.has(String(node.dataset.seasonKey || ""));
        });
        tvResults.querySelectorAll("details.tv-episode-alternatives[data-episode-key]").forEach((node) => {
          node.open = state.openAlternativeKeys.has(String(node.dataset.episodeKey || ""));
        });
        tvResults.querySelectorAll("details.tv-episode-search-details[data-episode-key]").forEach((node) => {
          node.open = state.openSearchDetailKeys.has(String(node.dataset.episodeKey || ""));
        });

        if (!state.scrollAnchor) return;

        const anchorSelector =
          state.scrollAnchor.kind === "episode"
            ? `.tv-episode-card[data-episode-key="${state.scrollAnchor.key}"]`
            : `details.tv-season[data-season-key="${state.scrollAnchor.key}"]`;
        const anchorNode = tvResults.querySelector(anchorSelector);
        if (!anchorNode) return;

        const rect = anchorNode.getBoundingClientRect();
        const delta = rect.top - state.scrollAnchor.top;
        if (Math.abs(delta) > 1) {
          window.scrollBy(0, delta);
        }
      };

      const applyCardQueueState = (card, job) => {
        const queueBtn = card.querySelector(".queue-dialog-btn");
        const manageBtn = card.querySelector(".queue-manage-btn");
        const stateEl = card.querySelector(".card-queue-state");

        card.classList.remove("queue-active", "queue-running", "queue-queued");

        if (!job) {
          if (queueBtn) {
            queueBtn.disabled = false;
            queueBtn.textContent = queueBtn.dataset.defaultLabel || "Add to queue...";
          }
          if (manageBtn) {
            manageBtn.classList.add("hidden");
            manageBtn.dataset.jobId = "";
          }
          if (stateEl) {
            stateEl.classList.add("hidden");
            stateEl.textContent = "";
            delete stateEl.dataset.mode;
          }
          return;
        }

        card.classList.add("queue-active", `queue-${job.status}`);
        if (queueBtn) {
          queueBtn.disabled = true;
          queueBtn.textContent = queueButtonLabelForStatus(job.status);
        }
        if (manageBtn) {
          manageBtn.classList.remove("hidden");
          manageBtn.dataset.jobId = String(job.id);
        }
        if (stateEl) {
          stateEl.classList.remove("hidden");
          stateEl.dataset.mode = job.status;
          stateEl.textContent = `${queueBadgeLabelForStatus(job.status)} as job #${job.id}`;
        }
      };

      const applyTvResultQueueState = (row, job) => {
        const queueBtn = row.querySelector(".tv-queue-btn");
        const manageBtn = row.querySelector(".tv-manage-btn");
        const stateEl = row.querySelector(".tv-result-queue-state");

        row.classList.remove("queue-active", "queue-running", "queue-queued");

        if (!job) {
          if (queueBtn) {
            queueBtn.disabled = false;
            queueBtn.textContent = queueBtn.dataset.defaultLabel || "Add to queue...";
          }
          if (manageBtn) {
            manageBtn.classList.add("hidden");
            manageBtn.dataset.jobId = "";
          }
          if (stateEl) {
            stateEl.classList.add("hidden");
            stateEl.textContent = "";
            delete stateEl.dataset.mode;
          }
          return;
        }

        row.classList.add("queue-active", `queue-${job.status}`);
        if (queueBtn) {
          queueBtn.disabled = true;
          queueBtn.textContent = queueButtonLabelForStatus(job.status);
        }
        if (manageBtn) {
          manageBtn.classList.remove("hidden");
          manageBtn.dataset.jobId = String(job.id);
        }
        if (stateEl) {
          stateEl.classList.remove("hidden");
          stateEl.dataset.mode = job.status;
          stateEl.textContent = `${queueBadgeLabelForStatus(job.status)} as job #${job.id}`;
        }
      };

      const applyEpisodeQueueSummaryState = (episodeNode, summary) => {
        const badge = episodeNode.querySelector(".tv-episode-queue-badge");
        episodeNode.classList.remove("queue-active", "queue-running", "queue-queued");
        if (!badge) return;

        if (!summary || !Array.isArray(summary.jobs) || summary.jobs.length === 0) {
          badge.classList.add("hidden");
          badge.textContent = "";
          delete badge.dataset.mode;
          return;
        }

        const label = queueBadgeLabelForStatus(summary.status);
        const suffix = summary.jobs.length > 1 ? ` (${summary.jobs.length})` : "";
        episodeNode.classList.add("queue-active", `queue-${summary.status}`);
        badge.classList.remove("hidden");
        badge.dataset.mode = summary.status;
        badge.textContent = `${label}${suffix}`;
      };

      const applyActiveQueueStateToSearchResults = () => {
        tvResults.querySelectorAll(".tv-result-item[data-detail-url], .tv-result-item[data-file-id]").forEach((row) => {
          const fileKey = buildFileQueueKey({
            fileId: row.dataset.fileId,
            detailUrl: row.dataset.detailUrl,
          });
          applyTvResultQueueState(row, fileKey ? state.activeQueueState.fileJobs.get(fileKey) || null : null);
        });

        tvResults.querySelectorAll(".tv-episode-card[data-queue-episode-key]").forEach((episodeNode) => {
          const key = String(episodeNode.dataset.queueEpisodeKey || "");
          applyEpisodeQueueSummaryState(episodeNode, key ? state.activeQueueState.episodeJobs.get(key) || null : null);
        });

        bindQueueManageButtons(document);
      };

      const syncTvResultsDownloadedStateFromJobs = (jobs) => {
        if (!tvResultsState) return false;

        const downloadedEpisodes = buildDownloadedTvEpisodesFromJobs(jobs);
        if (!downloadedEpisodes.size) return false;

        let changed = false;

        if (Array.isArray(tvResultsState.seasons)) {
          tvResultsState.seasons = tvResultsState.seasons.map((season) => {
            if (!Array.isArray(season?.episodes)) return season;

            let seasonChanged = false;
            const nextEpisodes = season.episodes.map((episode) => {
              const episodeKey = buildTvEpisodeKey({
                seasonNumber: episode?.season_number,
                episodeNumber: episode?.episode_number,
              });
              const downloadedFiles = episodeKey ? downloadedEpisodes.get(episodeKey) : null;
              if (!downloadedFiles) return episode;

              const alreadyDownloaded =
                String(episode?.status || "") === "downloaded" && sameStringList(episode?.downloaded_files, downloadedFiles);
              if (alreadyDownloaded) return episode;

              seasonChanged = true;
              changed = true;
              return buildDownloadedEpisodeState(episode, downloadedFiles);
            });

            return seasonChanged ? { ...season, episodes: nextEpisodes } : season;
          });
        }

        Array.from(tvEpisodeSearchOverrides.entries()).forEach(([episodeKey, episode]) => {
          const downloadedFiles = downloadedEpisodes.get(String(episodeKey));
          if (!downloadedFiles) return;

          const alreadyDownloaded =
            String(episode?.status || "") === "downloaded" && sameStringList(episode?.downloaded_files, downloadedFiles);
          if (alreadyDownloaded) return;

          tvEpisodeSearchOverrides.set(episodeKey, buildDownloadedEpisodeState(episode, downloadedFiles));
          changed = true;
        });

        return changed;
      };

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
        if (tvResultsFilter === "matches") return outcome.hasMatches;
        if (tvResultsFilter === "queued") return outcome.hasActiveQueue;
        if (tvResultsFilter === "downloaded") return outcome.isDownloaded;
        if (tvResultsFilter === "unmatched") return outcome.isNoMatch;
        return true;
      };

      const buildTvResultsStatsHtml = (overview) => `
        <span><strong>${esc(overview.totalEpisodes)}</strong> episodes searched</span>
        <span><strong>${esc(overview.matchedEpisodes)}</strong> with matches</span>
        <span><strong>${esc(overview.queuedEpisodes)}</strong> in queue</span>
        <span><strong>${esc(overview.downloadedEpisodes)}</strong> already downloaded</span>
        <span><strong>${esc(overview.noMatchEpisodes)}</strong> without matches</span>
      `;

      const buildTvResultsFilterChipsHtml = (overview) => {
        const chips = [
          { key: "all", label: "All", count: overview.totalEpisodes },
          { key: "matches", label: "With matches", count: overview.matchedEpisodes },
          { key: "queued", label: "In queue", count: overview.queuedEpisodes },
          { key: "downloaded", label: "Downloaded", count: overview.downloadedEpisodes },
          { key: "unmatched", label: "No matches", count: overview.noMatchEpisodes },
        ];

        return chips
          .map(
            (chip) => `
              <button
                type="button"
                class="tv-results-filter-chip btn btn-pill${tvResultsFilter === chip.key ? " active" : ""}"
                data-filter="${esc(chip.key)}"
              >
                ${esc(chip.label)}
                <span>${esc(chip.count)}</span>
              </button>
            `
          )
          .join("");
      };

      const buildTvResultsToolbarHtml = (overview) => {
        return `
          <section class="tv-results-toolbar" aria-label="TV results filters">
            <div class="tv-results-stats">${buildTvResultsStatsHtml(overview)}</div>
            <div class="tv-results-filters">${buildTvResultsFilterChipsHtml(overview)}</div>
          </section>
        `;
      };

      const buildTvResultsViewModel = (payload) => {
        const seasons = payload?.seasons || [];
        const completed = Number(payload?.completed_episodes || 0);
        const total = Number(payload?.total_episodes || 0);
        const resultCount = Number(payload?.result_count || 0);
        const status = String(payload?.status || "");
        const allSearchAliases =
          (Array.isArray(payload?.all_search_aliases) && payload.all_search_aliases.length ? payload.all_search_aliases : null) ||
          (Array.isArray(tvLookupState?.all_search_aliases) && tvLookupState.all_search_aliases.length ? tvLookupState.all_search_aliases : null) ||
          (Array.isArray(payload?.search_aliases) ? payload.search_aliases : []);
        const activeSearchAliases = Array.isArray(payload?.search_aliases) ? payload.search_aliases : [];
        const bannerMessage =
          status === "done"
            ? `Search complete. ${completed}/${total} episodes processed, ${resultCount} files found. No more results are coming.`
            : status === "failed"
              ? `Search failed after ${completed}/${total} episodes. ${payload?.error || "Check the status above for details."}`
              : status === "canceled"
                ? `Search canceled at ${completed}/${total} processed episodes. No more results are coming.`
                : status === "running"
                  ? `Search running in the background. ${completed}/${total} episodes processed, ${resultCount} files found so far.`
                  : status === "queued"
                    ? `Search queued in the background. ${completed}/${total} episodes processed so far.`
                    : "";
        const bannerHtml = bannerMessage
          ? `<div class="tv-results-banner" data-mode="${esc(status || "neutral")}" aria-live="polite">${esc(bannerMessage)}</div>`
          : "";

        const seasonViewModels = (Array.isArray(seasons) ? seasons : []).map((season) => {
          const episodeViewModels = (season.episodes || []).map((episode) => {
            const episodeKey = buildTvEpisodeKey({
              seasonNumber: episode.season_number ?? season.season_number ?? "",
              episodeNumber: episode.episode_number ?? "",
            });
            const effectiveEpisode = tvEpisodeSearchOverrides.get(episodeKey) || episode;
            const queueEpisodeKey = buildEpisodeQueueKey({
              seriesName: payload?.show?.name || "",
              seasonNumber: effectiveEpisode.season_number ?? season.season_number ?? "",
              episodeNumber: effectiveEpisode.episode_number ?? "",
            });
            const episodeQueueSummary = queueEpisodeKey ? state.activeQueueState.episodeJobs.get(queueEpisodeKey) || null : null;
            const outcome = getTvEpisodeOutcome(effectiveEpisode, episodeQueueSummary);
            return {
              episodeKey,
              effectiveEpisode,
              queueEpisodeKey,
              episodeQueueSummary,
              outcome,
              bestResult: Array.isArray(effectiveEpisode.results) ? effectiveEpisode.results[0] || null : null,
              alternativeResults: Array.isArray(effectiveEpisode.results) ? effectiveEpisode.results.slice(1) : [],
            };
          });

          const stats = episodeViewModels.reduce(
            (acc, viewModel) => {
              acc.totalEpisodes += 1;
              if (viewModel.outcome.hasMatches) acc.matchedEpisodes += 1;
              if (viewModel.outcome.hasActiveQueue) {
                acc.queuedEpisodes += 1;
                acc.queueStatus =
                  acc.queueStatus === "running" || viewModel.episodeQueueSummary?.status === "running" ? "running" : "queued";
              }
              if (viewModel.outcome.isDownloaded) acc.downloadedEpisodes += 1;
              if (viewModel.outcome.isNoMatch) acc.noMatchEpisodes += 1;
              return acc;
            },
            { totalEpisodes: 0, matchedEpisodes: 0, queuedEpisodes: 0, downloadedEpisodes: 0, noMatchEpisodes: 0, queueStatus: "" }
          );

          return {
            ...season,
            episodeViewModels,
            visibleEpisodeViewModels: episodeViewModels.filter((viewModel) => matchesTvResultsFilter(viewModel.outcome)),
            stats,
          };
        });

        const overview = seasonViewModels.reduce(
          (acc, season) => {
            acc.totalEpisodes += season.stats.totalEpisodes;
            acc.matchedEpisodes += season.stats.matchedEpisodes;
            acc.queuedEpisodes += season.stats.queuedEpisodes;
            acc.downloadedEpisodes += season.stats.downloadedEpisodes;
            acc.noMatchEpisodes += season.stats.noMatchEpisodes;
            return acc;
          },
          { totalEpisodes: 0, matchedEpisodes: 0, queuedEpisodes: 0, downloadedEpisodes: 0, noMatchEpisodes: 0 }
        );
        const visibleSeasons = seasonViewModels.filter((season) => season.visibleEpisodeViewModels.length > 0);

        return {
          completed,
          total,
          resultCount,
          status,
          allSearchAliases,
          activeSearchAliases,
          bannerHtml,
          seasonViewModels,
          overview,
          visibleSeasons,
        };
      };

      const buildTvSeasonSummaryBits = (season) => {
        const seasonSummaryBits = [
          `${season.stats.matchedEpisodes} matched`,
          `${season.stats.queuedEpisodes} in queue`,
          `${season.stats.downloadedEpisodes} downloaded`,
          `${season.stats.noMatchEpisodes} no matches`,
        ];
        if (tvResultsFilter !== "all" && season.visibleEpisodeViewModels.length !== season.stats.totalEpisodes) {
          seasonSummaryBits.unshift(`${season.visibleEpisodeViewModels.length} shown`);
        }
        return seasonSummaryBits;
      };

      const renderTvResultItem = ({
        item,
        queueEpisodeKey,
        showName,
        seasonNumber,
        episodeNumber,
        actionLabel,
        isPrimary = false,
        showQueries = false,
      }) => `
        <article
          class="tv-result-item${isPrimary ? " tv-result-primary" : ""}"
          data-file-id="${esc(item.file_id ?? "")}"
          data-detail-url="${esc(item.detail_url)}"
          data-queue-episode-key="${esc(queueEpisodeKey)}"
        >
          ${isPrimary ? `<div class="tv-best-result-label">${esc(actionLabel === "Add best to queue" ? "Best match" : "Match")}</div>` : ""}
          <div class="tv-result-head">
            <a href="${esc(item.detail_url)}" target="_blank" rel="noreferrer">${esc(item.title)}</a>
            <span class="tv-result-meta">Lang score: ${esc(item.language_priority ?? 0)} | ${esc(item.size || "n/a")}</span>
          </div>
          <div class="tv-result-submeta">
            <span>Year: ${esc(item.primary_year ?? "n/a")}</span>
            <span>Ext: ${esc(item.extension || "n/a")}</span>
            ${showQueries ? `<span>Queries: ${esc((item.query_hits || []).join(", ") || "n/a")}</span>` : ""}
          </div>
          <div class="tv-result-queue-state hidden" aria-live="polite"></div>
          <div class="tv-result-actions">
            <button
              type="button"
              class="tv-queue-btn queue-action-btn btn btn-primary btn-sm"
              data-default-label="${esc(actionLabel)}"
              data-file-id="${esc(item.file_id ?? "")}"
              data-title="${esc(item.title)}"
              data-detail-url="${esc(item.detail_url)}"
              data-series-name="${esc(showName || "")}"
              data-season-number="${esc(seasonNumber ?? "")}"
              data-episode-number="${esc(episodeNumber ?? "")}"
            >
              ${esc(actionLabel)}
            </button>
            <button type="button" class="tv-manage-btn btn btn-secondary btn-sm hidden" data-job-id="">Manage</button>
          </div>
        </article>
      `;

      const renderTvSearchDetails = ({
        episodeKey,
        payload,
        seasonNumber,
        effectiveEpisode,
        allSearchAliases,
        activeSearchAliases,
      }) => {
        if (effectiveEpisode.status === "downloaded") {
          return "";
        }
        const canExpandAliases =
          Array.isArray(allSearchAliases) &&
          Array.isArray(activeSearchAliases) &&
          allSearchAliases.length > activeSearchAliases.length;
        const hasQueryDetails =
          (Array.isArray(effectiveEpisode.query_variants) && effectiveEpisode.query_variants.length > 0) ||
          (Array.isArray(effectiveEpisode.query_errors) && effectiveEpisode.query_errors.length > 0);
        const showAliasControls = canExpandAliases || effectiveEpisode.alias_mode === "all";

        if (!showAliasControls && !hasQueryDetails) {
          return "";
        }

        const aliasActionLabel = tvEpisodeSearchesInFlight.has(episodeKey)
          ? "Searching all aliases..."
          : effectiveEpisode.alias_mode === "all"
            ? `Refresh all aliases (${allSearchAliases.length})`
            : `Search all aliases (${allSearchAliases.length})`;

        return `
          <details class="tv-episode-search-details" data-episode-key="${esc(episodeKey)}">
            <summary>Search details</summary>
            <div class="tv-episode-search-panel">
              ${
                showAliasControls
                  ? `
                    <div class="tv-episode-actions">
                      <button
                        type="button"
                        class="tv-episode-alias-btn btn btn-soft btn-sm"
                        data-episode-key="${esc(episodeKey)}"
                        data-show-id="${esc(payload?.show?.id ?? "")}"
                        data-show-name="${esc(payload?.show?.name || "")}"
                        data-season-number="${esc(effectiveEpisode.season_number ?? seasonNumber ?? "")}"
                        data-episode-number="${esc(effectiveEpisode.episode_number ?? "")}"
                        data-episode-name="${esc(effectiveEpisode.episode_name || "")}"
                        data-airdate="${esc(effectiveEpisode.airdate || "")}"
                        ${tvEpisodeSearchesInFlight.has(episodeKey) ? "disabled" : ""}
                      >
                        ${esc(aliasActionLabel)}
                      </button>
                      ${
                        effectiveEpisode.alias_mode === "all"
                          ? `<span class="tv-episode-action-note">Showing results from all ${esc(allSearchAliases.length)} safe aliases.</span>`
                          : `<span class="tv-episode-action-note">Default search used ${esc(activeSearchAliases.length)} of ${esc(allSearchAliases.length)} safe aliases.</span>`
                      }
                    </div>
                  `
                  : ""
              }
              ${
                effectiveEpisode.query_variants && effectiveEpisode.query_variants.length
                  ? `<div class="tv-query-list">Queries: ${(effectiveEpisode.query_variants || []).map((query) => `<code>${esc(query)}</code>`).join(" ")}</div>`
                  : ""
              }
              ${
                effectiveEpisode.query_errors && effectiveEpisode.query_errors.length
                  ? `<div class="job-error">${esc(effectiveEpisode.query_errors.join(" | "))}</div>`
                  : ""
              }
            </div>
          </details>
        `;
      };

      const bindTvResultsToolbar = () => {
        tvResults.querySelectorAll(".tv-results-filter-chip").forEach((btn) => {
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";
          btn.addEventListener("click", () => {
            const nextFilter = String(btn.dataset.filter || "all");
            if (tvResultsFilter === nextFilter) return;
            tvResultsFilter = nextFilter;
            if (tvResultsState) renderTvResults(tvResultsState);
          });
        });
      };

      const bindTvEpisodeSearchAnywayButtons = () => {
        tvResults.querySelectorAll(".tv-episode-search-anyway-btn").forEach((btn) => {
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";
          btn.addEventListener("click", async () => {
            const episodeKey = String(btn.dataset.episodeKey || "");
            if (!episodeKey || tvEpisodeSearchesInFlight.has(episodeKey)) return;

            const seasonNumber = Number(btn.dataset.seasonNumber || 0);
            const episodeNumber = Number(btn.dataset.episodeNumber || 0);
            if (!Number.isFinite(seasonNumber) || seasonNumber <= 0 || !Number.isFinite(episodeNumber) || episodeNumber <= 0) {
              return;
            }

            tvEpisodeSearchesInFlight.add(episodeKey);
            if (tvResultsState) renderTvResults(tvResultsState);
            setTvStatus(`Searching anyway for S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}...`, "neutral");

            try {
              const { ok, data } = await api.searchTvEpisode({
                  show_id: Number(btn.dataset.showId || 0),
                  show_name: btn.dataset.showName || "",
                  season_number: seasonNumber,
                  episode_number: episodeNumber,
                  episode_name: btn.dataset.episodeName || null,
                  airdate: btn.dataset.airdate || null,
                  aliases: tvLookupState?.aliases || [],
                  title_metadata: tvLookupState?.title_metadata || null,
                  category: tvResultsState?.category || categorySelect.value || "video",
                  language: tvResultsState?.language || (languageInput.value.trim() || null),
                  language_scope: tvResultsState?.language_scope || languageScopeSelect.value || "any",
                  strict_dubbing:
                    typeof tvResultsState?.strict_dubbing === "boolean"
                      ? Boolean(tvResultsState.strict_dubbing)
                      : Boolean(strictDubbingInput.checked),
                  max_results_per_variant:
                    Number(tvResultsState?.max_results_per_variant || maxResultsInput.value || 120) || 120,
                  alias_mode: "optimized",
                  force_search: true,
              });
              if (!ok) {
                setTvStatus(data.error || "Episode search failed.", "error");
                return;
              }

              if (data.episode) {
                tvEpisodeSearchOverrides.set(episodeKey, data.episode);
              }
              tvLookupState = {
                ...(tvLookupState || {}),
                show: data.show || tvLookupState?.show || null,
                title_metadata: data.title_metadata || tvLookupState?.title_metadata || null,
                aliases: data.aliases || tvLookupState?.aliases || [],
                all_search_aliases: data.all_search_aliases || tvLookupState?.all_search_aliases || [],
                search_aliases: data.search_aliases || tvLookupState?.search_aliases || [],
              };
              renderTvShowSummary(tvLookupState);
              setTvStatus(
                `Searched S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")} even though it was already downloaded.`,
                "ok"
              );
            } catch (_) {
              setTvStatus("Episode search failed.", "error");
            } finally {
              tvEpisodeSearchesInFlight.delete(episodeKey);
              if (tvResultsState) renderTvResults(tvResultsState);
            }
          });
        });
      };

      const focusDownloadJob = (jobId) => {
        if (!jobId) {
          setDownloadStatus("No matching queue job was found.", "neutral");
          return;
        }

        setActiveTab("downloads");
        window.setTimeout(() => {
          const target = downloadJobsEl.querySelector(`[data-job-id="${jobId}"]`);
          if (!target) {
            setDownloadStatus(`Job #${jobId} is no longer visible in the queue.`, "neutral");
            return;
          }
          target.scrollIntoView({ behavior: "smooth", block: "center" });
          target.classList.add("queue-job-highlight");
          window.setTimeout(() => target.classList.remove("queue-job-highlight"), 1800);
          setDownloadStatus(`Showing job #${jobId}.`, "ok");
        }, 80);
      };

      const bindQueueManageButtons = (root = document) => {
        root.querySelectorAll(".queue-manage-btn, .tv-manage-btn").forEach((btn) => {
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";
          btn.addEventListener("click", () => {
            const jobId = Number(btn.dataset.jobId || 0);
            focusDownloadJob(jobId);
          });
        });
      };

      const renderTvSeasonPicker = (seasons) => {
        if (!Array.isArray(seasons) || seasons.length === 0) {
          tvSeasonPicker.innerHTML = "<div class='download-empty'>No seasons found.</div>";
          updateTvSearchButtonState();
          return;
        }
        tvSeasonPicker.innerHTML = `
          <div class="tv-season-toolbar">
            <button type="button" id="tvSelectAllSeasons" class="btn btn-secondary btn-sm">Select all</button>
            <button type="button" id="tvSelectNoSeasons" class="btn btn-secondary btn-sm">Clear</button>
          </div>
          <div class="tv-season-grid">
            ${seasons
              .map(
                (season) => `
                  <section class="tv-season-select" data-season-number="${season.season_number}">
                    <label class="tv-season-item">
                      <input class="tv-season-check" type="checkbox" value="${season.season_number}" />
                      Season ${season.season_number} (${season.episode_count} episodes)
                    </label>
                    <label class="tv-episode-mode-label">
                      Search mode
                      <select class="tv-episode-mode">
                        <option value="all" selected>All episodes in season</option>
                        <option value="selected">Selected episodes only</option>
                      </select>
                    </label>
                    <div class="tv-episode-picker hidden">
                      <div class="tv-episode-picker-toolbar">
                        <button type="button" class="tv-episode-select-all btn btn-secondary btn-sm">All episodes</button>
                        <button type="button" class="tv-episode-select-none btn btn-secondary btn-sm">Clear</button>
                      </div>
                      <div class="tv-episode-grid">
                        ${(season.episodes || [])
                          .map(
                            (episode) => `
                              <label class="tv-episode-item">
                                <input class="tv-episode-check" type="checkbox" value="${episode.number}" />
                                ${esc(episode.episode_code || `E${String(episode.number || "").padStart(2, "0")}`)} ${esc(episode.name || "")}
                              </label>
                            `
                          )
                          .join("")}
                      </div>
                    </div>
                  </section>
                `
              )
              .join("")}
          </div>
        `;

        const updateSeasonRowsState = () => {
          tvSeasonPicker.querySelectorAll(".tv-season-select").forEach((row) => {
            const seasonChecked = Boolean(row.querySelector("input.tv-season-check")?.checked);
            const mode = row.querySelector("select.tv-episode-mode")?.value || "all";
            const picker = row.querySelector(".tv-episode-picker");
            picker?.classList.toggle("hidden", !(seasonChecked && mode === "selected"));
          });
        };

        document.getElementById("tvSelectAllSeasons")?.addEventListener("click", () => {
          tvSeasonPicker.querySelectorAll("input.tv-season-check").forEach((el) => {
            el.checked = true;
          });
          updateSeasonRowsState();
          updateTvSearchButtonState();
        });
        document.getElementById("tvSelectNoSeasons")?.addEventListener("click", () => {
          tvSeasonPicker.querySelectorAll("input.tv-season-check").forEach((el) => {
            el.checked = false;
          });
          updateSeasonRowsState();
          updateTvSearchButtonState();
        });
        tvSeasonPicker.querySelectorAll("input.tv-season-check").forEach((el) => {
          el.addEventListener("change", () => {
            updateSeasonRowsState();
            updateTvSearchButtonState();
          });
        });
        tvSeasonPicker.querySelectorAll("select.tv-episode-mode").forEach((el) => {
          el.addEventListener("change", () => {
            updateSeasonRowsState();
            updateTvSearchButtonState();
          });
        });
        tvSeasonPicker.querySelectorAll("input.tv-episode-check").forEach((el) => {
          el.addEventListener("change", () => {
            updateTvSearchButtonState();
          });
        });
        tvSeasonPicker.querySelectorAll(".tv-episode-select-all").forEach((btn) => {
          btn.addEventListener("click", () => {
            btn
              .closest(".tv-episode-picker")
              ?.querySelectorAll("input.tv-episode-check")
              .forEach((el) => {
                el.checked = true;
              });
            updateTvSearchButtonState();
          });
        });
        tvSeasonPicker.querySelectorAll(".tv-episode-select-none").forEach((btn) => {
          btn.addEventListener("click", () => {
            btn
              .closest(".tv-episode-picker")
              ?.querySelectorAll("input.tv-episode-check")
              .forEach((el) => {
                el.checked = false;
              });
            updateTvSearchButtonState();
          });
        });
        updateSeasonRowsState();
        updateTvSearchButtonState();
      };

      const bindTvQueueButtons = () => {
        tvResults.querySelectorAll("button.tv-queue-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            await openQueueDialog({
              intent: "enqueue",
              detailUrl: btn.dataset.detailUrl,
              fileId: btn.dataset.fileId ? Number(btn.dataset.fileId) : null,
              title: btn.dataset.title || "",
              preferredMode: "premium",
              mediaKind: "tv",
              seriesName: btn.dataset.seriesName || null,
              seasonNumber: btn.dataset.seasonNumber ? Number(btn.dataset.seasonNumber) : null,
              episodeNumber: btn.dataset.episodeNumber ? Number(btn.dataset.episodeNumber) : null,
            });
          });
        });
      };

      const bindTvEpisodeAliasButtons = () => {
        tvResults.querySelectorAll(".tv-episode-alias-btn").forEach((btn) => {
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";
          btn.addEventListener("click", async () => {
            const episodeKey = String(btn.dataset.episodeKey || "");
            if (!episodeKey || tvEpisodeSearchesInFlight.has(episodeKey)) return;

            const seasonNumber = Number(btn.dataset.seasonNumber || 0);
            const episodeNumber = Number(btn.dataset.episodeNumber || 0);
            if (!Number.isFinite(seasonNumber) || seasonNumber <= 0 || !Number.isFinite(episodeNumber) || episodeNumber <= 0) {
              return;
            }

            tvEpisodeSearchesInFlight.add(episodeKey);
            if (tvResultsState) renderTvResults(tvResultsState);
            setTvStatus(`Searching all aliases for S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}...`, "neutral");

            try {
              const { ok, data } = await api.searchTvEpisode({
                  show_id: Number(btn.dataset.showId || 0),
                  show_name: btn.dataset.showName || "",
                  season_number: seasonNumber,
                  episode_number: episodeNumber,
                  episode_name: btn.dataset.episodeName || null,
                  airdate: btn.dataset.airdate || null,
                  aliases: tvLookupState?.aliases || [],
                  title_metadata: tvLookupState?.title_metadata || null,
                  category: tvResultsState?.category || categorySelect.value || "video",
                  language: tvResultsState?.language || (languageInput.value.trim() || null),
                  language_scope: tvResultsState?.language_scope || languageScopeSelect.value || "any",
                  strict_dubbing:
                    typeof tvResultsState?.strict_dubbing === "boolean"
                      ? Boolean(tvResultsState.strict_dubbing)
                      : Boolean(strictDubbingInput.checked),
                  max_results_per_variant:
                    Number(tvResultsState?.max_results_per_variant || maxResultsInput.value || 120) || 120,
                  alias_mode: "all",
              });
              if (!ok) {
                setTvStatus(data.error || "Expanded episode search failed.", "error");
                return;
              }

              if (data.episode) {
                tvEpisodeSearchOverrides.set(episodeKey, data.episode);
              }
              tvLookupState = {
                ...(tvLookupState || {}),
                show: data.show || tvLookupState?.show || null,
                title_metadata: data.title_metadata || tvLookupState?.title_metadata || null,
                aliases: data.aliases || tvLookupState?.aliases || [],
                all_search_aliases: data.all_search_aliases || tvLookupState?.all_search_aliases || [],
                search_aliases: data.search_aliases || tvLookupState?.search_aliases || [],
              };
              setTvStatus(
                `Expanded ${data.episode?.episode_code || `S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}`} using all aliases.`,
                "ok"
              );
            } catch (_) {
              setTvStatus("Expanded episode search failed.", "error");
            } finally {
              tvEpisodeSearchesInFlight.delete(episodeKey);
              if (tvResultsState) renderTvResults(tvResultsState);
            }
          });
        });
      };

      const renderTvResults = (payload) => {
        tvResultsState = payload;
        const viewModel = buildTvResultsViewModel(payload);
        const { bannerHtml, seasonViewModels, visibleSeasons, overview, allSearchAliases, activeSearchAliases } = viewModel;
        const uiState = captureTvResultsUiState();
        const toolbarHtml = buildTvResultsToolbarHtml(overview);

        if (seasonViewModels.length === 0) {
          tvResults.innerHTML = `
            ${bannerHtml}
            ${toolbarHtml}
            <div class='download-empty'>No results found for selected seasons.</div>
          `;
          bindTvResultsToolbar();
          return;
        }

        if (visibleSeasons.length === 0) {
          tvResults.innerHTML = `
            ${bannerHtml}
            ${toolbarHtml}
            <div class='download-empty'>No episodes match the current filter.</div>
          `;
          bindTvResultsToolbar();
          return;
        }

        const seasonHtml = visibleSeasons
          .map((season) => {
            const seasonRows = season.visibleEpisodeViewModels
              .map((viewModel) => {
                const { episodeKey, effectiveEpisode, queueEpisodeKey, outcome, bestResult, alternativeResults } = viewModel;
                const resultsLabel = `${outcome.resultCount} ${pluralize(outcome.resultCount, "result")}`;
                const bestResultHtml = bestResult
                  ? renderTvResultItem({
                      item: bestResult,
                      queueEpisodeKey,
                      showName: payload?.show?.name || "",
                      seasonNumber: effectiveEpisode.season_number ?? season.season_number ?? "",
                      episodeNumber: effectiveEpisode.episode_number ?? "",
                      actionLabel: "Add best to queue",
                      isPrimary: true,
                    })
                  : outcome.isDownloaded
                    ? `
                        <div class="tv-episode-empty" data-mode="downloaded">
                          <div class="tv-downloaded-summary">
                            <strong>Already downloaded</strong>
                            <span>
                              ${esc((effectiveEpisode.downloaded_files || [])[0] || "Matching episode file found locally.")}
                              ${
                                Array.isArray(effectiveEpisode.downloaded_files) && effectiveEpisode.downloaded_files.length > 1
                                  ? `<em>+ ${esc(effectiveEpisode.downloaded_files.length - 1)} more</em>`
                                  : ""
                              }
                            </span>
                          </div>
                          <div class="tv-episode-actions">
                            <button
                              type="button"
                              class="tv-episode-search-anyway-btn btn btn-secondary btn-sm"
                              data-episode-key="${esc(episodeKey)}"
                              data-show-id="${esc(payload?.show?.id ?? "")}"
                              data-show-name="${esc(payload?.show?.name || "")}"
                              data-season-number="${esc(effectiveEpisode.season_number ?? season.season_number ?? "")}"
                              data-episode-number="${esc(effectiveEpisode.episode_number ?? "")}"
                              data-episode-name="${esc(effectiveEpisode.episode_name || "")}"
                              data-airdate="${esc(effectiveEpisode.airdate || "")}"
                              ${tvEpisodeSearchesInFlight.has(episodeKey) ? "disabled" : ""}
                            >
                              ${esc(tvEpisodeSearchesInFlight.has(episodeKey) ? "Searching..." : "Search anyway")}
                            </button>
                          </div>
                        </div>
                      `
                  : `<div class="tv-episode-empty" data-mode="${esc(outcome.status)}">${
                      outcome.status === "running"
                        ? "Episode search is running..."
                      : outcome.status === "pending" || outcome.status === "queued"
                          ? "Waiting in background queue..."
                          : "No matches yet."
                    }</div>`;
                const alternativesHtml = alternativeResults.length
                  ? `
                      <details class="tv-episode-alternatives" data-episode-key="${esc(episodeKey)}">
                        <summary>Show ${esc(alternativeResults.length)} ${esc(pluralize(alternativeResults.length, "alternative"))}</summary>
                        <div class="tv-result-list tv-result-alternatives">
                          ${alternativeResults
                            .map((item) =>
                              renderTvResultItem({
                                item,
                                queueEpisodeKey,
                                showName: payload?.show?.name || "",
                                seasonNumber: effectiveEpisode.season_number ?? season.season_number ?? "",
                                episodeNumber: effectiveEpisode.episode_number ?? "",
                                actionLabel: "Add to queue...",
                                showQueries: true,
                              })
                            )
                            .join("")}
                        </div>
                      </details>
                    `
                  : "";

                return `
                  <article
                    class="tv-episode-card"
                    data-episode-key="${esc(episodeKey)}"
                    data-queue-episode-key="${esc(queueEpisodeKey)}"
                  >
                    <div class="tv-episode-summary">
                      <div class="tv-episode-heading">
                        <div class="tv-episode-title-row">
                          <span class="tv-episode-code">${esc(effectiveEpisode.episode_code)}</span>
                          <span class="tv-episode-name">${esc(effectiveEpisode.episode_name || "")}</span>
                        </div>
                        <div class="tv-episode-meta-row">
                          <span class="tv-episode-status" data-mode="${esc(outcome.status)}">${esc(outcome.status || "pending")}</span>
                          <span class="tv-summary-count">${esc(resultsLabel)}</span>
                          <span class="tv-episode-queue-badge hidden"></span>
                        </div>
                      </div>
                    </div>
                    ${bestResultHtml}
                    <div class="tv-episode-secondary">
                      ${alternativesHtml}
                      ${renderTvSearchDetails({
                        episodeKey,
                        payload,
                        seasonNumber: season.season_number,
                        effectiveEpisode,
                        allSearchAliases,
                        activeSearchAliases,
                      })}
                    </div>
                  </article>
                `;
              })
              .join("");

            const seasonSummaryBits = buildTvSeasonSummaryBits(season);
            const seasonQueueBadge =
              season.stats.queuedEpisodes > 0
                ? `<span class="tv-season-queue-badge" data-mode="${esc(season.stats.queueStatus || "queued")}">${esc(queueBadgeLabelForStatus(season.stats.queueStatus || "queued"))} (${esc(season.stats.queuedEpisodes)})</span>`
                : `<span class="tv-season-queue-badge hidden"></span>`;

            return `
              <details class="tv-season" data-season-key="${esc(season.season_number)}">
                <summary>
                  Season ${esc(season.season_number)}
                  <span class="tv-summary-count">${seasonSummaryBits.map((bit) => esc(bit)).join(" · ")}</span>
                  ${seasonQueueBadge}
                </summary>
                <div class="tv-season-body">${seasonRows || "<div class='download-empty'>No episode metadata for this season.</div>"}</div>
              </details>
            `;
          })
          .join("");
        tvResults.innerHTML = `
          ${bannerHtml}
          ${toolbarHtml}
          ${seasonHtml}
          <div class="download-empty tv-results-empty hidden">No episodes match the current filter.</div>
        `;

        restoreTvResultsUiState(uiState);
        bindTvResultsToolbar();
        bindTvQueueButtons();
        bindTvEpisodeSearchAnywayButtons();
        bindTvEpisodeAliasButtons();
        applyActiveQueueStateToSearchResults();
      };

      const refreshTvResultsQueueUi = () => {
        if (!tvResultsState || !tvResults.querySelector(".tv-results-toolbar")) return;

        const viewModel = buildTvResultsViewModel(tvResultsState);
        if (!viewModel.seasonViewModels.length) return;

        const seasonMap = new Map(viewModel.seasonViewModels.map((season) => [String(season.season_number), season]));
        const episodeMap = new Map();
        viewModel.seasonViewModels.forEach((season) => {
          season.episodeViewModels.forEach((episodeViewModel) => {
            episodeMap.set(String(episodeViewModel.episodeKey), episodeViewModel);
          });
        });

        const visibleSeasonKeys = new Set(viewModel.visibleSeasons.map((season) => String(season.season_number)));
        const renderedSeasonKeys = new Set(
          Array.from(tvResults.querySelectorAll("details.tv-season[data-season-key]"))
            .map((node) => String(node.dataset.seasonKey || ""))
            .filter(Boolean)
        );
        const missingVisibleSeason = Array.from(visibleSeasonKeys).some((key) => !renderedSeasonKeys.has(key));
        if (missingVisibleSeason) {
          renderTvResults(tvResultsState);
          return;
        }

        const toolbar = tvResults.querySelector(".tv-results-toolbar");
        if (toolbar) {
          const stats = toolbar.querySelector(".tv-results-stats");
          const filters = toolbar.querySelector(".tv-results-filters");
          if (stats) {
            stats.innerHTML = buildTvResultsStatsHtml(viewModel.overview);
          }
          if (filters) {
            filters.innerHTML = buildTvResultsFilterChipsHtml(viewModel.overview);
          }
          bindTvResultsToolbar();
        }

        tvResults.querySelectorAll(".tv-episode-card[data-episode-key]").forEach((episodeNode) => {
          const episodeKey = String(episodeNode.dataset.episodeKey || "");
          const episodeViewModel = episodeMap.get(episodeKey);
          if (!episodeViewModel) return;
          episodeNode.hidden = !matchesTvResultsFilter(episodeViewModel.outcome);
        });

        tvResults.querySelectorAll("details.tv-season[data-season-key]").forEach((seasonNode) => {
          const seasonKey = String(seasonNode.dataset.seasonKey || "");
          const season = seasonMap.get(seasonKey);
          if (!season) return;

          seasonNode.hidden = !visibleSeasonKeys.has(seasonKey);

          const summaryCount = seasonNode.querySelector(":scope > summary .tv-summary-count");
          if (summaryCount) {
            summaryCount.textContent = buildTvSeasonSummaryBits(season).join(" · ");
          }

          const queueBadge = seasonNode.querySelector(":scope > summary .tv-season-queue-badge");
          if (queueBadge) {
            if (season.stats.queuedEpisodes > 0) {
              queueBadge.classList.remove("hidden");
              queueBadge.dataset.mode = season.stats.queueStatus || "queued";
              queueBadge.textContent = `${queueBadgeLabelForStatus(season.stats.queueStatus || "queued")} (${season.stats.queuedEpisodes})`;
            } else {
              queueBadge.classList.add("hidden");
              queueBadge.textContent = "";
              delete queueBadge.dataset.mode;
            }
          }
        });

        const emptyState = tvResults.querySelector(".tv-results-empty");
        if (emptyState) {
          emptyState.classList.toggle("hidden", viewModel.visibleSeasons.length > 0);
        }
      };

  return {
    renderTvActiveFilters,
    formatTvAliasSummary,
    renderTvShowSummary,
    syncFileFiltersToTvEditor,
    syncTvEditorToFileFilters,
    updateTvSearchButtonState,
    setSearchMode,
    setTvStatus,
    setActiveTvSearchJobId,
    selectedTvSeasons,
    selectedTvEpisodesBySeason,
    tvEpisodeSelectionIsValid,
    refreshActiveTvSearchJob,
    captureTvResultsUiState,
    restoreTvResultsUiState,
    applyCardQueueState,
    applyTvResultQueueState,
    syncTvResultsDownloadedStateFromJobs,
    matchesTvResultsFilter,
    buildTvResultsStatsHtml,
    buildTvResultsFilterChipsHtml,
    buildTvResultsToolbarHtml,
    buildTvResultsViewModel,
    buildTvSeasonSummaryBits,
    renderTvResultItem,
    renderTvSearchDetails,
    bindTvResultsToolbar,
    bindTvEpisodeSearchAnywayButtons,
    renderTvSeasonPicker,
    bindTvQueueButtons,
    bindTvEpisodeAliasButtons,
    renderTvResults,
    refreshTvResultsQueueUi,
  };
};
