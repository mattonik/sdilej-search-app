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
import { createTvViewHelpers } from "./tv-view.js";
import { buildTvEpisodeOutcome, formatTvAliasSummary, matchesTvResultsFilter } from "./tv-state.js";

export const initTvSearch = ({
  elements,
  api,
  state,
  setActiveQueueStateFromJobs,
  applyTvResultQueueState,
  applyEpisodeQueueSummaryState,
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

  const tvView = createTvViewHelpers({
    state,
    getTvEpisodeOutcome: buildTvEpisodeOutcome,
    matchesTvResultsFilter: (outcome) => matchesTvResultsFilter(outcome, state.tvResultsFilter),
    buildActiveSearchAliases: (payload) => {
      const aliases = [
        ...(Array.isArray(payload?.all_search_aliases) ? payload.all_search_aliases : []),
        ...(Array.isArray(payload?.search_aliases) ? payload.search_aliases : []),
      ];
      return Array.from(new Set(aliases.filter(Boolean)));
    },
  });

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

      const buildTvResultsStatsHtml = tvView.buildTvResultsStatsHtml;
      const buildTvResultsFilterChipsHtml = tvView.buildTvResultsFilterChipsHtml;
      const buildTvResultsToolbarHtml = tvView.buildTvResultsToolbarHtml;
      const buildTvResultsViewModel = tvView.buildTvResultsViewModel;
      const buildTvSeasonSummaryBits = tvView.buildTvSeasonSummaryBits;
      const renderTvResultItem = tvView.renderTvResultItem;
      const renderTvSearchDetails = tvView.renderTvSearchDetails;

      const bindTvResultsToolbar = () => {

        tvResults.querySelectorAll(".tv-results-filter-chip").forEach((btn) => {
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";
          btn.addEventListener("click", () => {
            const nextFilter = String(btn.dataset.filter || "all");
            if (tvResultsFilter === nextFilter) return;
            tvResultsFilter = nextFilter;
            state.tvResultsFilter = tvResultsFilter;
            if (tvResultsState) renderTvResults(tvResultsState);
          });
        });
      };

      const bindTvEpisodeSearchAnywayButtons = () => {
        if (tvResults.dataset.searchAnywayBound === "1") return;
        tvResults.dataset.searchAnywayBound = "1";
        tvResults.addEventListener("click", async (event) => {
          const path = typeof event.composedPath === "function" ? event.composedPath() : [];
          const btn =
            path.find((node) => node instanceof Element && node.classList.contains("tv-episode-search-anyway-btn")) ||
            (event.target instanceof Element ? event.target.closest(".tv-episode-search-anyway-btn") : null);
          if (!btn || !tvResults.contains(btn)) return;

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
              tvEpisodeSearchOverrides.set(episodeKey, { ...data.episode, _manualSearchOverride: true });
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
        }, true);
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
        tvResults.querySelectorAll(".tv-episode-alias-btn, .tv-episode-search-anyway-btn").forEach((btn) => {
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

            const forceSearch = btn.dataset.forceSearch === "1";

            tvEpisodeSearchesInFlight.add(episodeKey);
            if (tvResultsState) renderTvResults(tvResultsState);
            setTvStatus(
              forceSearch
                ? `Searching anyway for S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}...`
                : `Searching all aliases for S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}...`,
              "neutral"
            );

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
                  alias_mode: forceSearch ? "optimized" : "all",
                  force_search: forceSearch,
              });
              if (!ok) {
                setTvStatus(data.error || "Expanded episode search failed.", "error");
                return;
              }

              if (data.episode) {
                tvEpisodeSearchOverrides.set(episodeKey, { ...data.episode, _manualSearchOverride: true });
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
                forceSearch
                  ? `Searched ${data.episode?.episode_code || `S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}`} even though it was already downloaded.`
                  : `Expanded ${data.episode?.episode_code || `S${String(seasonNumber).padStart(2, "0")}E${String(episodeNumber).padStart(2, "0")}`} using all aliases.`,
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
                              class="tv-episode-search-anyway-btn tv-episode-alias-btn btn btn-secondary btn-sm"
                              data-episode-key="${esc(episodeKey)}"
                              data-show-id="${esc(payload?.show?.id ?? "")}"
                              data-show-name="${esc(payload?.show?.name || "")}"
                              data-season-number="${esc(effectiveEpisode.season_number ?? season.season_number ?? "")}"
                              data-episode-number="${esc(effectiveEpisode.episode_number ?? "")}"
                              data-episode-name="${esc(effectiveEpisode.episode_name || "")}"
                              data-airdate="${esc(effectiveEpisode.airdate || "")}"
                              data-force-search="1"
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
