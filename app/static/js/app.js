      const input = document.getElementById("queryInput");
      const list = document.getElementById("suggestions");
      const categorySelect = document.getElementById("categorySelect");
      const sortSelect = document.getElementById("sortSelect");
      const languageInput = document.getElementById("languageInput");
      const languageScopeSelect = document.getElementById("languageScopeSelect");
      const strictDubbingInput = document.getElementById("strictDubbingInput");
      const releaseYearInput = document.getElementById("releaseYearInput");
      const maxResultsInput = document.getElementById("maxResultsInput");
      const fileSearchForm = document.getElementById("fileSearchForm");
      const fileSearchAdvancedFilters = document.getElementById("fileSearchAdvancedFilters");
      const fileSearchActiveFilters = document.getElementById("fileSearchActiveFilters");
      const fileResultsToolbar = document.getElementById("fileResultsToolbar");
      const fileResultsToolbarSummary = document.getElementById("fileResultsToolbarSummary");
      const fileResultsVisibleCount = document.getElementById("fileResultsVisibleCount");
      const fileResultsCardsBtn = document.getElementById("fileResultsCardsBtn");
      const fileResultsListBtn = document.getElementById("fileResultsListBtn");
      const fileResultsGrid = document.getElementById("fileResultsGrid");
      const fileResultsEmpty = document.getElementById("fileResultsEmpty");
      const fileSearchModeBtn = document.getElementById("fileSearchModeBtn");
      const tvSearchModeBtn = document.getElementById("tvSearchModeBtn");
      const fileSearchPanel = document.getElementById("fileSearchPanel");
      const tvModePanel = document.getElementById("tvModePanel");
      const tvLookupForm = document.getElementById("tvLookupForm");
      const tvShowName = document.getElementById("tvShowName");
      const tvLookupBtn = document.getElementById("tvLookupBtn");
      const tvStatus = document.getElementById("tvStatus");
      const tvShowSummaryCard = document.getElementById("tvShowSummaryCard");
      const tvLookupInfo = document.getElementById("tvLookupInfo");
      const tvSeasonPicker = document.getElementById("tvSeasonPicker");
      const tvActiveFilters = document.getElementById("tvActiveFilters");
      const tvFilterCategory = document.getElementById("tvFilterCategory");
      const tvFilterLanguage = document.getElementById("tvFilterLanguage");
      const tvFilterLanguageScope = document.getElementById("tvFilterLanguageScope");
      const tvFilterMaxResults = document.getElementById("tvFilterMaxResults");
      const tvFilterStrictDubbing = document.getElementById("tvFilterStrictDubbing");
      const tvSearchBtn = document.getElementById("tvSearchBtn");
      const tvResults = document.getElementById("tvResults");
      const fileResultsBlocks = Array.from(document.querySelectorAll(".file-results-block"));
      const accountStatus = document.getElementById("accountStatus");
      const accountForm = document.getElementById("accountForm");
      const accountLogin = document.getElementById("accountLogin");
      const accountPassword = document.getElementById("accountPassword");
      const accountVerify = document.getElementById("accountVerify");
      const accountClearBtn = document.getElementById("accountClearBtn");
      const downloadForm = document.getElementById("downloadForm");
      const downloadDetailUrl = document.getElementById("downloadDetailUrl");
      const downloadMode = document.getElementById("downloadMode");
      const downloadMediaKind = document.getElementById("downloadMediaKind");
      const downloadKidsTag = document.getElementById("downloadKidsTag");
      const downloadSeriesName = document.getElementById("downloadSeriesName");
      const downloadSeasonNumber = document.getElementById("downloadSeasonNumber");
      const downloadChunkCount = document.getElementById("downloadChunkCount");
      const downloadPriority = document.getElementById("downloadPriority");
      const downloadSettingsForm = document.getElementById("downloadSettingsForm");
      const settingsMaxConcurrent = document.getElementById("settingsMaxConcurrent");
      const settingsDefaultChunks = document.getElementById("settingsDefaultChunks");
      const settingsBandwidth = document.getElementById("settingsBandwidth");
      const downloadStatus = document.getElementById("downloadStatus");
      const downloadJobsEl = document.getElementById("downloadJobs");
      const refreshDownloadsBtn = document.getElementById("refreshDownloadsBtn");
      const clearFinishedBtn = document.getElementById("clearFinishedBtn");
      const downloadSummary = document.getElementById("downloadSummary");
      const downloadWorkerState = document.getElementById("downloadWorkerState");
      const workspaceTabs = Array.from(document.querySelectorAll(".workspace-tab"));
      const tabSections = Array.from(document.querySelectorAll(".tab-section"));
      const queueDialogBackdrop = document.getElementById("queueDialogBackdrop");
      const queueDialogClose = document.getElementById("queueDialogClose");
      const queueDialogCancel = document.getElementById("queueDialogCancel");
      const queueDialogForm = document.getElementById("queueDialogForm");
      const queueDialogTitle = document.getElementById("queueDialogTitle");
      const queueDialogItemTitle = document.getElementById("queueDialogItemTitle");
      const queueDialogMode = document.getElementById("queueDialogMode");
      const queueDialogMediaKind = document.getElementById("queueDialogMediaKind");
      const queueDialogKidsTag = document.getElementById("queueDialogKidsTag");
      const queueDialogSeriesName = document.getElementById("queueDialogSeriesName");
      const queueDialogSeasonNumber = document.getElementById("queueDialogSeasonNumber");
      const queueDialogChunkCount = document.getElementById("queueDialogChunkCount");
      const queueDialogPriority = document.getElementById("queueDialogPriority");
      const queueDialogPreview = document.getElementById("queueDialogPreview");
      const TV_ACTIVE_JOB_KEY = "activeTvSearchJobId";
      const FILE_RESULTS_VIEW_KEY = "fileResultsView";
      const FILE_RESULTS_FILTER_KEY = "fileResultsFilter";
      const FILE_SEARCH_ADVANCED_KEY = "fileSearchAdvancedOpen";
      const ACTIVE_QUEUE_STATUSES = new Set(["queued", "running"]);
      let timer = null;
      let queueDialogState = null;
      let tvLookupState = null;
      let tvResultsState = null;
      let tvResultsFilter = "all";
      let fileResultsView = window.localStorage.getItem(FILE_RESULTS_VIEW_KEY) === "list" ? "list" : "cards";
      let fileResultsFilter = window.localStorage.getItem(FILE_RESULTS_FILTER_KEY) || "all";
      let searchMode = "file";
      let activeTvSearchJobId = window.localStorage.getItem(TV_ACTIVE_JOB_KEY);
      let tvJobPollInFlight = false;
      let tvEpisodeSearchOverrides = new Map();
      let tvEpisodeSearchesInFlight = new Set();
      let tvShowSummarySignature = "";
      let savedResultsState = {
        keys: new Set(),
        itemsByKey: new Map(),
      };
      let activeQueueState = {
        fileJobs: new Map(),
        episodeJobs: new Map(),
        jobsById: new Map(),
      };

      const esc = (value) =>
        String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");

      const stripHtml = (value) =>
        String(value ?? "")
          .replace(/<[^>]+>/g, " ")
          .replace(/\s+/g, " ")
          .trim();

      const truncateText = (value, maxLength = 220) => {
        const text = String(value ?? "").trim();
        if (text.length <= maxLength) return text;
        return `${text.slice(0, Math.max(0, maxLength - 1)).trimEnd()}...`;
      };

      const normalizeQueueTextKey = (value) =>
        String(value ?? "")
          .normalize("NFKD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, " ")
          .trim();

      const normalizeDetailQueueKey = (value) => {
        const raw = String(value ?? "").trim();
        if (!raw) return "";
        try {
          const url = new URL(raw, window.location.origin);
          return `${url.pathname.replace(/\/+$/, "")}${url.search}`.toLowerCase();
        } catch (_) {
          return raw.toLowerCase();
        }
      };

      const buildFileQueueKey = ({ fileId, detailUrl }) => {
        const numericFileId = Number(fileId);
        if (Number.isFinite(numericFileId) && numericFileId > 0) {
          return `id:${numericFileId}`;
        }
        const normalizedUrl = normalizeDetailQueueKey(detailUrl);
        return normalizedUrl ? `url:${normalizedUrl}` : "";
      };

      const buildEpisodeQueueKey = ({ seriesName, seasonNumber, episodeNumber }) => {
        const normalizedSeries = normalizeQueueTextKey(seriesName);
        const season = Number(seasonNumber);
        const episode = Number(episodeNumber);
        if (!normalizedSeries || !Number.isFinite(season) || season <= 0 || !Number.isFinite(episode) || episode <= 0) {
          return "";
        }
        return `${normalizedSeries}:${season}:${episode}`;
      };

      const buildTvEpisodeKey = ({ seasonNumber, episodeNumber }) => {
        const season = Number(seasonNumber);
        const episode = Number(episodeNumber);
        if (!Number.isFinite(season) || season <= 0 || !Number.isFinite(episode) || episode <= 0) {
          return "";
        }
        return `${season}:${episode}`;
      };

      const basenameFromPath = (value) => {
        const raw = String(value ?? "").trim();
        if (!raw) return "";
        const parts = raw.split(/[\\/]+/).filter(Boolean);
        return parts[parts.length - 1] || "";
      };

      const sameStringList = (left, right) => JSON.stringify(Array.isArray(left) ? left : []) === JSON.stringify(Array.isArray(right) ? right : []);

      const buildCurrentTvShowAliasKeys = () => {
        const titleMetadata = tvResultsState?.title_metadata || tvLookupState?.title_metadata || null;
        const candidates = [
          tvResultsState?.show?.name,
          tvLookupState?.show?.name,
          ...(Array.isArray(tvResultsState?.aliases) ? tvResultsState.aliases : []),
          ...(Array.isArray(tvLookupState?.aliases) ? tvLookupState.aliases : []),
          ...(Array.isArray(tvResultsState?.all_search_aliases) ? tvResultsState.all_search_aliases : []),
          ...(Array.isArray(tvLookupState?.all_search_aliases) ? tvLookupState.all_search_aliases : []),
          ...(Array.isArray(tvResultsState?.search_aliases) ? tvResultsState.search_aliases : []),
          ...(Array.isArray(tvLookupState?.search_aliases) ? tvLookupState.search_aliases : []),
          titleMetadata?.canonical_title,
          titleMetadata?.original_title,
          ...(Array.isArray(titleMetadata?.local_titles) ? titleMetadata.local_titles : []),
          ...(Array.isArray(titleMetadata?.aliases) ? titleMetadata.aliases : []),
        ];
        return new Set(candidates.map((value) => normalizeQueueTextKey(value)).filter(Boolean));
      };

      const buildDownloadedTvEpisodesFromJobs = (jobs) => {
        const aliasKeys = buildCurrentTvShowAliasKeys();
        if (!aliasKeys.size) return new Map();

        const downloadedEpisodes = new Map();
        (Array.isArray(jobs) ? jobs : []).forEach((job) => {
          if (String(job?.status || "") !== "done") return;
          if (String(job?.media_kind || "") !== "tv") return;

          const normalizedSeries = normalizeQueueTextKey(job?.series_name);
          if (!normalizedSeries || !aliasKeys.has(normalizedSeries)) return;

          const episodeKey = buildTvEpisodeKey({
            seasonNumber: job?.season_number,
            episodeNumber: job?.episode_number,
          });
          if (!episodeKey) return;

          const label =
            basenameFromPath(job?.save_path) ||
            basenameFromPath(job?.working_path) ||
            String(job?.title || "").trim() ||
            `S${String(job?.season_number || "").padStart(2, "0")}E${String(job?.episode_number || "").padStart(2, "0")}`;

          const current = downloadedEpisodes.get(episodeKey) || [];
          if (!current.includes(label)) {
            current.push(label);
            downloadedEpisodes.set(episodeKey, current);
          }
        });

        return downloadedEpisodes;
      };

      const buildDownloadedEpisodeState = (episode, downloadedFiles) => ({
        ...episode,
        status: "downloaded",
        result_count: 0,
        results: [],
        downloaded_files: Array.isArray(downloadedFiles) ? [...downloadedFiles] : [],
      });

      const buildSavedStateFromItems = (items) => {
        const keys = new Set();
        const itemsByKey = new Map();

        (Array.isArray(items) ? items : []).forEach((item) => {
          const key = buildFileQueueKey({
            fileId: item?.file_id,
            detailUrl: item?.detail_url,
          });
          if (!key) return;
          keys.add(key);
          itemsByKey.set(key, item);
        });

        return { keys, itemsByKey };
      };

      const isSavedResult = ({ fileId, detailUrl }) => {
        const key = buildFileQueueKey({ fileId, detailUrl });
        return key ? savedResultsState.keys.has(key) : false;
      };

      const setSavedStateFromItems = (items) => {
        savedResultsState = buildSavedStateFromItems(items);
        refreshFileSearchResultsUi();
      };

      const upsertSavedStateItem = (item) => {
        const items = Array.from(savedResultsState.itemsByKey.values());
        const nextKey = buildFileQueueKey({ fileId: item?.file_id, detailUrl: item?.detail_url });
        const filtered = items.filter((current) => {
          const currentKey = buildFileQueueKey({ fileId: current?.file_id, detailUrl: current?.detail_url });
          return currentKey !== nextKey;
        });
        if (item && nextKey) {
          filtered.push(item);
        }
        setSavedStateFromItems(filtered);
      };

      const queueButtonLabelForStatus = (status) => (status === "running" ? "Downloading" : "Added to queue");
      const queueBadgeLabelForStatus = (status) => (status === "running" ? "Downloading" : "In queue");

      const choosePreferredActiveJob = (current, candidate) => {
        if (!current) return candidate;
        if (!candidate) return current;
        if (current.status !== "running" && candidate.status === "running") return candidate;
        if (current.status === "running" && candidate.status !== "running") return current;
        return Number(candidate.id || 0) > Number(current.id || 0) ? candidate : current;
      };

      const buildActiveQueueStateFromJobs = (jobs) => {
        const fileJobs = new Map();
        const episodeJobs = new Map();
        const jobsById = new Map();

        (Array.isArray(jobs) ? jobs : []).forEach((job) => {
          const status = String(job?.status || "");
          if (!ACTIVE_QUEUE_STATUSES.has(status)) return;

          jobsById.set(String(job.id), job);

          const fileKey = buildFileQueueKey({ fileId: job.file_id, detailUrl: job.detail_url });
          if (fileKey) {
            fileJobs.set(fileKey, choosePreferredActiveJob(fileJobs.get(fileKey), job));
          }

          const episodeKey = buildEpisodeQueueKey({
            seriesName: job.series_name,
            seasonNumber: job.season_number,
            episodeNumber: job.episode_number,
          });
          if (episodeKey) {
            const current = episodeJobs.get(episodeKey);
            const summary = current || { jobs: [], primaryJob: job, status: status };
            summary.jobs.push(job);
            summary.primaryJob = choosePreferredActiveJob(summary.primaryJob, job);
            summary.status = summary.primaryJob.status;
            episodeJobs.set(episodeKey, summary);
          }
        });

        return { fileJobs, episodeJobs, jobsById };
      };

      const setActiveQueueStateFromJobs = (jobs) => {
        activeQueueState = buildActiveQueueStateFromJobs(jobs);
        const tvDownloadedStateChanged = tvResultsState ? syncTvResultsDownloadedStateFromJobs(jobs) : false;
        refreshFileSearchResultsUi();
        if (tvResultsState) {
          if (tvDownloadedStateChanged) {
            renderTvResults(tvResultsState);
          } else {
            refreshTvResultsQueueUi();
          }
        }
        applyActiveQueueStateToSearchResults();
      };

      const upsertActiveQueueJob = (job) => {
        const jobs = Array.from(activeQueueState.jobsById.values()).filter((item) => String(item.id) !== String(job?.id));
        if (job && ACTIVE_QUEUE_STATUSES.has(String(job.status || ""))) {
          jobs.push(job);
        }
        setActiveQueueStateFromJobs(jobs);
      };

      const formatBytes = (value) => {
        if (value == null || Number.isNaN(Number(value))) return "n/a";
        const num = Number(value);
        const units = ["B", "KB", "MB", "GB", "TB"];
        let idx = 0;
        let current = num;
        while (current >= 1024 && idx < units.length - 1) {
          current /= 1024;
          idx += 1;
        }
        const precision = current >= 10 || idx === 0 ? 0 : 1;
        return `${current.toFixed(precision)} ${units[idx]}`;
      };

      const formatSpeed = (value) => {
        if (value == null || Number.isNaN(Number(value)) || Number(value) <= 0) return "n/a";
        return `${formatBytes(value)}/s`;
      };

      const formatEta = (bytesDownloaded, bytesTotal, speedBps) => {
        const done = Number(bytesDownloaded);
        const total = Number(bytesTotal);
        const speed = Number(speedBps);
        if (!Number.isFinite(done) || !Number.isFinite(total) || !Number.isFinite(speed) || speed <= 0 || done >= total) {
          return "n/a";
        }
        const seconds = Math.floor((total - done) / speed);
        if (!Number.isFinite(seconds) || seconds < 0) return "n/a";
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
      };

      const setActiveTab = (tabName) => {
        const resolved = tabName === "downloads" ? "downloads" : "search";
        workspaceTabs.forEach((tab) => {
          tab.classList.toggle("active", tab.dataset.tab === resolved);
        });
        tabSections.forEach((section) => {
          const showSearch = section.classList.contains("tab-search");
          const showDownloads = section.classList.contains("tab-downloads");
          const visible = (resolved === "search" && showSearch) || (resolved === "downloads" && showDownloads);
          section.style.display = visible ? "" : "none";
        });
        window.location.hash = resolved;
        window.localStorage.setItem("activeWorkspaceTab", resolved);
      };

      workspaceTabs.forEach((tab) => {
        tab.addEventListener("click", () => setActiveTab(tab.dataset.tab || "search"));
      });

      const initialTab = (() => {
        const hash = (window.location.hash || "").replace("#", "").trim();
        if (hash === "search" || hash === "downloads") return hash;
        const saved = window.localStorage.getItem("activeWorkspaceTab");
        if (saved === "search" || saved === "downloads") return saved;
        return "search";
      })();
      setActiveTab(initialTab);

      const renderFileSearchActiveFilters = () => {
        if (!fileSearchActiveFilters) return;

        const parts = [
          `Category ${categorySelect?.value || "video"}`,
          `Language ${languageInput?.value.trim() || "none"}`,
          `Scope ${languageScopeSelect?.value || "any"}`,
          `Sort ${sortSelect?.selectedOptions?.[0]?.textContent?.trim() || sortSelect?.value || "default"}`,
          `Year ${releaseYearInput?.value || "none"}`,
          `Max ${maxResultsInput?.value || "120"}`,
        ];
        if (strictDubbingInput?.checked) {
          parts.push("Strict dubbing");
        }

        fileSearchActiveFilters.innerHTML = `<strong>Active filters:</strong> ${parts.map((part) => `<code>${esc(part)}</code>`).join(" ")}`;
      };

      const setFileResultsView = (view) => {
        fileResultsView = view === "list" ? "list" : "cards";
        if (fileResultsGrid) {
          fileResultsGrid.dataset.view = fileResultsView;
        }
        fileResultsCardsBtn?.classList.toggle("active", fileResultsView === "cards");
        fileResultsListBtn?.classList.toggle("active", fileResultsView === "list");
        window.localStorage.setItem(FILE_RESULTS_VIEW_KEY, fileResultsView);
      };

      const setFileResultsFilter = (filter) => {
        const next = ["all", "unsaved", "saved", "queued", "playable"].includes(String(filter)) ? String(filter) : "all";
        fileResultsFilter = next;
        fileResultsToolbar?.querySelectorAll(".file-results-filter-chip").forEach((btn) => {
          btn.classList.toggle("active", btn.dataset.filter === next);
        });
        window.localStorage.setItem(FILE_RESULTS_FILTER_KEY, fileResultsFilter);
        refreshFileSearchResultsUi();
      };

      const applyCardSavedState = (card, savedItem) => {
        const saveBtn = card.querySelector(".save-btn");
        const savedBadge = card.querySelector(".card-saved-state");

        card.classList.toggle("result-card-saved", Boolean(savedItem));

        if (saveBtn) {
          saveBtn.disabled = Boolean(savedItem);
          saveBtn.textContent = savedItem ? "Saved" : saveBtn.dataset.defaultLabel || "Save pick";
        }
        if (savedBadge) {
          if (savedItem) {
            savedBadge.classList.remove("hidden");
            savedBadge.textContent = "Saved";
            savedBadge.dataset.mode = "saved";
          } else {
            savedBadge.classList.add("hidden");
            savedBadge.textContent = "";
            delete savedBadge.dataset.mode;
          }
        }
      };

      const getFileResultOutcome = (card) => {
        const fileKey = buildFileQueueKey({
          fileId: card.dataset.fileId,
          detailUrl: card.dataset.detailUrl,
        });
        const queueJob = fileKey ? activeQueueState.fileJobs.get(fileKey) || null : null;
        const saved = isSavedResult({ fileId: card.dataset.fileId, detailUrl: card.dataset.detailUrl });
        const playable = card.dataset.isPlayable === "1";
        return {
          fileKey,
          queueJob,
          saved,
          playable,
          queued: Boolean(queueJob),
        };
      };

      const matchesFileResultsFilter = (outcome) => {
        if (fileResultsFilter === "saved") return outcome.saved;
        if (fileResultsFilter === "unsaved") return !outcome.saved;
        if (fileResultsFilter === "queued") return outcome.queued;
        if (fileResultsFilter === "playable") return outcome.playable;
        return true;
      };

      const refreshFileResultsToolbar = (counts) => {
        if (!fileResultsToolbar) return;

        fileResultsToolbarSummary.textContent = `${counts.visible} of ${counts.total} visible for “${fileResultsToolbar.dataset.querySummary || "current search"}”.`;
        fileResultsVisibleCount.textContent = `${counts.visible} shown`;

        fileResultsToolbar.querySelectorAll(".file-results-filter-chip").forEach((btn) => {
          const key = String(btn.dataset.filter || "all");
          const span = btn.querySelector("span");
          if (!span) return;
          if (key === "saved") span.textContent = String(counts.saved);
          else if (key === "unsaved") span.textContent = String(counts.unsaved);
          else if (key === "queued") span.textContent = String(counts.queued);
          else if (key === "playable") span.textContent = String(counts.playable);
          else span.textContent = String(counts.total);
        });
      };

      const refreshFileSearchResultsUi = () => {
        if (!fileResultsGrid) return;

        const cards = Array.from(fileResultsGrid.querySelectorAll(".result-card[data-detail-url], .result-card[data-file-id]"));
        const counts = {
          total: cards.length,
          visible: 0,
          saved: 0,
          unsaved: 0,
          queued: 0,
          playable: 0,
        };

        cards.forEach((card) => {
          const outcome = getFileResultOutcome(card);
          const savedItem = outcome.fileKey ? savedResultsState.itemsByKey.get(outcome.fileKey) || null : null;

          applyCardSavedState(card, savedItem);
          applyCardQueueState(card, outcome.queueJob);

          if (outcome.saved) counts.saved += 1;
          else counts.unsaved += 1;
          if (outcome.queued) counts.queued += 1;
          if (outcome.playable) counts.playable += 1;

          const matches = matchesFileResultsFilter(outcome);
          card.classList.toggle("hidden", !matches);
          if (matches) counts.visible += 1;
        });

        refreshFileResultsToolbar(counts);
        if (fileResultsEmpty) {
          fileResultsEmpty.classList.toggle("hidden", counts.visible > 0);
        }

        bindQueueManageButtons(document);
      };

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
        window.localStorage.setItem("searchMode", searchMode);
      };

      fileSearchModeBtn.addEventListener("click", () => setSearchMode("file"));
      tvSearchModeBtn.addEventListener("click", () => setSearchMode("tv"));

      input.addEventListener("input", () => {
        const q = input.value.trim();
        clearTimeout(timer);
        if (q.length < 2) {
          list.innerHTML = "";
          return;
        }

        timer = setTimeout(async () => {
          try {
            const res = await fetch(`/api/autocomplete?q=${encodeURIComponent(q)}&limit=10`);
            if (!res.ok) return;
            const payload = await res.json();
            list.innerHTML = "";
            for (const suggestion of payload.suggestions || []) {
              const opt = document.createElement("option");
              opt.value = suggestion;
              list.appendChild(opt);
            }
          } catch (_) {
            // Ignore autocomplete failures; main search still works.
          }
        }, 180);
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
        tvResultsFilter = "all";
        tvEpisodeSearchOverrides = new Map();
        tvEpisodeSearchesInFlight = new Set();
        tvLookupState = null;
        updateTvSearchButtonState();
        try {
          const res = await fetch("/api/tv/lookup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ show_name: showName }),
          });
          const data = await res.json();
          if (!res.ok) {
            setTvStatus(data.error || "TV lookup failed.", "error");
            return;
          }
          tvLookupState = {
            ...data,
            all_search_aliases: data.all_search_aliases || data.search_aliases || [],
          };
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
        tvResultsFilter = "all";
        tvEpisodeSearchOverrides = new Map();
        tvEpisodeSearchesInFlight = new Set();
        const maxPerVariantRaw = Number(maxResultsInput.value || 120);
        const maxPerVariant = Number.isFinite(maxPerVariantRaw) && maxPerVariantRaw > 0 ? Math.min(500, maxPerVariantRaw) : 120;
        try {
          const res = await fetch("/api/tv/search-jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
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
            }),
          });
          const data = await res.json();
          if (!res.ok) {
            setTvStatus(data.error || "TV search failed.", "error");
            return;
          }
          setActiveTvSearchJobId(data.id);
          renderTvResults(data);
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
        if (activeTvSearchJobId) {
          window.localStorage.setItem(TV_ACTIVE_JOB_KEY, activeTvSearchJobId);
        } else {
          window.localStorage.removeItem(TV_ACTIVE_JOB_KEY);
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
        try {
          const res = await fetch(`/api/tv/search-jobs/${encodeURIComponent(activeTvSearchJobId)}`);
          const data = await res.json();
          if (!res.ok) {
            if (res.status === 404) {
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
          if (tvLookupState.show) {
            tvLookupInfo.innerHTML = `
              <strong>${esc(tvLookupState.show.name || "")}</strong>
              <span> (${esc(Number(data.total_episodes || 0))} selected episodes, ${esc(formatTvAliasSummary(data.aliases || [], data.search_aliases || []))})</span>
            `;
          }
          renderTvShowSummary(tvLookupState);
          renderTvResults(data);

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
          applyTvResultQueueState(row, fileKey ? activeQueueState.fileJobs.get(fileKey) || null : null);
        });

        tvResults.querySelectorAll(".tv-episode-card[data-queue-episode-key]").forEach((episodeNode) => {
          const key = String(episodeNode.dataset.queueEpisodeKey || "");
          applyEpisodeQueueSummaryState(episodeNode, key ? activeQueueState.episodeJobs.get(key) || null : null);
        });

        bindQueueManageButtons(document);
      };

      const pluralize = (count, singular, plural = `${singular}s`) => (count === 1 ? singular : plural);

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
            const episodeQueueSummary = queueEpisodeKey ? activeQueueState.episodeJobs.get(queueEpisodeKey) || null : null;
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
              const res = await fetch("/api/tv/search-episode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
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
                }),
              });
              const data = await res.json();
              if (!res.ok) {
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
              const res = await fetch("/api/tv/search-episode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
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
                }),
              });
              const data = await res.json();
              if (!res.ok) {
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

      const renderDownloadJobs = (jobs) => {
        if (!Array.isArray(jobs) || jobs.length === 0) {
          downloadJobsEl.innerHTML = `<div class="download-empty">No jobs yet.</div>`;
          return;
        }

        downloadJobsEl.innerHTML = jobs
          .map((job) => {
            const total = job.bytes_total;
            const done = job.bytes_downloaded ?? 0;
            const pct = total && total > 0 ? Math.max(0, Math.min(100, (done / total) * 100)) : 0;
            const canCancel = job.status === "queued" || job.status === "running";
            const canRetry = job.status === "failed" || job.status === "canceled";
            const canMoveTop = job.status === "queued";
            const canRemove = job.status !== "running";
            const title = job.title || job.detail_url;
            const eta = formatEta(done, total, job.speed_bps);
            const savePath = job.save_path ? `<div><strong>Saved:</strong> <code>${esc(job.save_path)}</code></div>` : "";
            const error = job.error ? `<div class="job-error"><strong>Error:</strong> ${esc(job.error)}</div>` : "";
            return `
              <article class="download-job" data-job-id="${esc(job.id)}">
                <div class="job-head">
                  <a href="${esc(job.detail_url)}" target="_blank" rel="noreferrer">${esc(title)}</a>
                  <span class="job-status status-${esc(job.status)}">${esc(job.status)}</span>
                </div>
                <div class="job-progress-wrap">
                  <div class="job-progress"><span style="width: ${pct.toFixed(1)}%"></span></div>
                </div>
                <div class="job-meta">
                  <span><strong>ID:</strong> ${esc(job.id)}</span>
                  <span><strong>Mode:</strong> ${esc(job.preferred_mode)}</span>
                  <span><strong>Type:</strong> ${esc(job.media_kind ?? "n/a")}</span>
                  <span><strong>Kids:</strong> ${job.is_kids ? "yes" : "no"}</span>
                  <span><strong>Dest:</strong> ${esc(job.destination_subpath ?? "manual")}</span>
                  <span><strong>Chunks:</strong> ${esc(job.chunk_count ?? "n/a")}</span>
                  <span><strong>Priority:</strong> ${esc(job.priority)}</span>
                  <span><strong>Attempt:</strong> ${esc(job.attempt_count)}</span>
                  <span><strong>Progress:</strong> ${formatBytes(done)} / ${formatBytes(total)}</span>
                  <span><strong>Speed:</strong> ${formatSpeed(job.speed_bps)}</span>
                  <span><strong>ETA:</strong> ${esc(eta)}</span>
                </div>
                ${savePath}
                ${error}
                <div class="job-actions">
                  ${canCancel ? `<button type="button" class="btn btn-secondary btn-sm" data-action="cancel" data-id="${job.id}">Cancel</button>` : ""}
                  ${canCancel ? `<button type="button" class="btn btn-danger btn-sm" data-action="cancel_complete" data-id="${job.id}">Cancel completely</button>` : ""}
                  ${job.status === "queued" ? `<button type="button" class="btn btn-soft btn-sm" data-action="classify" data-id="${job.id}" data-title="${esc(title)}" data-detail-url="${esc(job.detail_url)}" data-mode="${esc(job.preferred_mode)}" data-media-kind="${esc(job.media_kind || "")}" data-is-kids="${job.is_kids ? "1" : "0"}" data-series-name="${esc(job.series_name || "")}" data-season-number="${esc(job.season_number ?? "")}" data-episode-number="${esc(job.episode_number ?? "")}" data-chunk-count="${esc(job.chunk_count ?? "")}" data-priority="${esc(job.priority)}">Category</button>` : ""}
                  ${canRetry ? `<button type="button" class="btn btn-secondary btn-sm" data-action="retry" data-id="${job.id}">Retry</button>` : ""}
                  ${canMoveTop ? `<button type="button" class="btn btn-secondary btn-sm" data-action="top" data-id="${job.id}">Move top</button>` : ""}
                  ${(job.status === "queued" || job.status === "running") ? `<button type="button" class="btn btn-secondary btn-sm" data-action="priority" data-id="${job.id}" data-priority="${job.priority}">Set priority</button>` : ""}
                  ${canRemove ? `<button type="button" class="btn btn-danger btn-sm" data-action="remove" data-id="${job.id}">Remove job</button>` : ""}
                  ${canRemove ? `<button type="button" class="btn btn-danger btn-sm" data-action="remove_data" data-id="${job.id}">Remove job + data</button>` : ""}
                </div>
              </article>
            `;
          })
          .join("");

        downloadJobsEl.querySelectorAll("button[data-action]").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const action = btn.dataset.action;
            const jobId = Number(btn.dataset.id);
            if (!jobId) return;

            try {
              if (action === "cancel") {
                await fetch(`/api/downloads/${jobId}/cancel`, { method: "POST" });
                setDownloadStatus(`Canceled job #${jobId}.`, "neutral");
              } else if (action === "cancel_complete") {
                await fetch(`/api/downloads/${jobId}/cancel-complete`, { method: "POST" });
                setDownloadStatus(`Canceled job #${jobId} completely.`, "ok");
              } else if (action === "classify") {
                await openQueueDialog({
                  intent: "edit",
                  jobId,
                  detailUrl: btn.dataset.detailUrl || "",
                  title: btn.dataset.title || "",
                  preferredMode: btn.dataset.mode || "premium",
                  mediaKind: btn.dataset.mediaKind || null,
                  isKids: btn.dataset.isKids === "1",
                  seriesName: btn.dataset.seriesName || null,
                  seasonNumber: btn.dataset.seasonNumber ? Number(btn.dataset.seasonNumber) : null,
                  episodeNumber: btn.dataset.episodeNumber ? Number(btn.dataset.episodeNumber) : null,
                  chunkCount: btn.dataset.chunkCount ? Number(btn.dataset.chunkCount) : Number(downloadChunkCount.value || 1),
                  priority: btn.dataset.priority ? Number(btn.dataset.priority) : Number(downloadPriority.value || 0),
                });
                return;
              } else if (action === "retry") {
                await fetch(`/api/downloads/${jobId}/retry`, { method: "POST" });
                setDownloadStatus(`Retried job #${jobId}.`, "ok");
              } else if (action === "top") {
                await fetch(`/api/downloads/${jobId}/top`, { method: "POST" });
                setDownloadStatus(`Moved job #${jobId} to top.`, "ok");
              } else if (action === "remove") {
                const res = await fetch(`/api/downloads/${jobId}`, { method: "DELETE" });
                const data = await res.json();
                if (!res.ok) {
                  setDownloadStatus(data.error || "Failed to remove job.", "error");
                  return;
                }
                setDownloadStatus(`Removed job #${jobId}.`, "ok");
              } else if (action === "remove_data") {
                const res = await fetch(`/api/downloads/${jobId}?with_data=true`, { method: "DELETE" });
                const data = await res.json();
                if (!res.ok) {
                  setDownloadStatus(data.error || "Failed to remove job + data.", "error");
                  return;
                }
                const deletedCount = Array.isArray(data.deleted_paths) ? data.deleted_paths.length : 0;
                setDownloadStatus(`Removed job #${jobId} and deleted ${deletedCount} file(s).`, "ok");
              } else if (action === "priority") {
                const current = Number(btn.dataset.priority || "0");
                const raw = window.prompt("Set priority (-1000..1000):", String(current));
                if (raw == null) return;
                const next = Number(raw);
                if (!Number.isFinite(next)) {
                  setDownloadStatus("Priority must be a number.", "error");
                  return;
                }
                const res = await fetch(`/api/downloads/${jobId}/priority`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ priority: next }),
                });
                const data = await res.json();
                if (!res.ok) {
                  setDownloadStatus(data.error || "Failed to set priority.", "error");
                  return;
                }
                setDownloadStatus(`Priority updated for job #${jobId}.`, "ok");
              }
            } catch (_) {
              setDownloadStatus(`Action failed for job #${jobId}.`, "error");
            } finally {
              await refreshDownloads();
            }
          });
        });
      };

      const refreshDownloads = async () => {
        try {
          const res = await fetch("/api/downloads?limit=200");
          const data = await res.json();
          if (!res.ok) {
            setDownloadStatus(data.error || "Failed to refresh download queue.", "error");
            return;
          }
          const summary = data.summary || {};
          downloadWorkerState.textContent = data.worker_alive ? "Worker: online" : "Worker: offline";
          downloadSummary.textContent = `Queue: ${summary.queued || 0} queued, ${summary.running || 0} running, ${summary.done || 0} done, ${summary.failed || 0} failed, ${summary.canceled || 0} canceled`;
          renderDownloadJobs(data.items || []);
          setActiveQueueStateFromJobs(data.items || []);
        } catch (_) {
          setDownloadStatus("Queue status unavailable.", "error");
        }
      };

      const refreshDownloadSettings = async () => {
        try {
          const res = await fetch("/api/downloads/settings");
          const data = await res.json();
          if (!res.ok) {
            setDownloadStatus(data.error || "Failed to load download settings.", "error");
            return;
          }
          settingsMaxConcurrent.value = data.max_concurrent_jobs ?? 1;
          settingsDefaultChunks.value = data.default_chunk_count ?? 1;
          settingsBandwidth.value = data.bandwidth_limit_kbps ?? 0;
          downloadChunkCount.value = data.default_chunk_count ?? 1;
        } catch (_) {
          setDownloadStatus("Download settings unavailable.", "error");
        }
      };

      const refreshSavedCandidates = async () => {
        if (!fileResultsGrid) return;
        try {
          const res = await fetch("/api/saved?limit=1000");
          const data = await res.json();
          if (!res.ok) return;
          setSavedStateFromItems(data.items || []);
        } catch (_) {
          // Keep file search usable even if saved-state hydration fails.
        }
      };

      const enqueueDownload = async (payload) => {
        try {
          const res = await fetch("/api/downloads", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) {
            if (res.status === 409 && data.duplicate_job) {
              const dup = data.duplicate_job;
              if (ACTIVE_QUEUE_STATUSES.has(String(dup.status || ""))) {
                upsertActiveQueueJob(dup);
              }
              setDownloadStatus(
                `${data.error || "Duplicate download."} Existing job #${dup.id} is ${dup.status}.`,
                "error"
              );
              return {
                ok: false,
                duplicateJob: dup,
                duplicateIsActive: ACTIVE_QUEUE_STATUSES.has(String(dup.status || "")),
              };
            } else if (res.status === 409 && data.requires_confirmation) {
              setDownloadStatus(data.error || "Classification confirmation is required.", "error");
            } else {
              setDownloadStatus(data.error || "Failed to enqueue job.", "error");
            }
            return { ok: false };
          }
          upsertActiveQueueJob(data);
          setDownloadStatus(`Queued #${data.id}: ${data.title || data.detail_url}`, "ok");
          return { ok: true, job: data };
        } catch (_) {
          setDownloadStatus("Failed to enqueue job.", "error");
          return { ok: false };
        }
      };

      const resolveKidsValue = (rawValue) => {
        if (rawValue === "yes") return true;
        if (rawValue === "no") return false;
        return null;
      };

      const buildMediaRoutingPayload = () => {
        const mediaKind = downloadMediaKind.value === "auto" ? null : downloadMediaKind.value;
        const isKids = resolveKidsValue(downloadKidsTag.value);
        const payload = {
          media_kind: mediaKind,
          is_kids: isKids,
          series_name: null,
          season_number: null,
        };
        if (mediaKind === "tv") {
          payload.series_name = downloadSeriesName.value.trim() || null;
          const season = Number(downloadSeasonNumber.value || 0);
          payload.season_number = Number.isFinite(season) && season > 0 ? season : null;
        }
        return payload;
      };

      const queueDialogMediaPayload = () => {
        const mediaKind = queueDialogMediaKind.value === "auto" ? null : queueDialogMediaKind.value;
        const isKids = resolveKidsValue(queueDialogKidsTag.value);
        const seasonValue = Number(queueDialogSeasonNumber.value || 0);
        const episodeValue = Number(queueDialogState?.episodeNumber || 0);
        return {
          media_kind: mediaKind,
          is_kids: isKids,
          series_name: mediaKind === "tv" ? (queueDialogSeriesName.value.trim() || null) : null,
          season_number: mediaKind === "tv" && Number.isFinite(seasonValue) && seasonValue > 0 ? seasonValue : null,
          episode_number: mediaKind === "tv" && Number.isFinite(episodeValue) && episodeValue > 0 ? episodeValue : null,
        };
      };

      const updateQueueDialogMode = () => {
        const isTv = queueDialogMediaKind.value === "tv";
        queueDialogSeriesName.disabled = !isTv;
        queueDialogSeasonNumber.disabled = !isTv;
        if (!isTv) {
          queueDialogSeriesName.value = "";
          queueDialogSeasonNumber.value = "";
        }
      };

      const classifyForQueueDialog = async () => {
        if (!queueDialogState) return;
        const payload = {
          title: queueDialogState.title || "",
          ...queueDialogMediaPayload(),
        };
        try {
          const res = await fetch("/api/media/classify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) {
            queueDialogPreview.textContent = data.error || "Classification preview failed.";
            return;
          }

          const c = data.classification || {};
          if (queueDialogMediaKind.value === "auto" && (c.media_kind === "movie" || c.media_kind === "tv")) {
            queueDialogMediaKind.value = c.media_kind;
            updateQueueDialogMode();
          }
          if (queueDialogKidsTag.value === "auto" && typeof c.is_kids === "boolean") {
            queueDialogKidsTag.value = c.is_kids ? "yes" : "no";
          }
          if (queueDialogMediaKind.value === "tv") {
            if (!queueDialogSeriesName.value && c.series_name) {
              queueDialogSeriesName.value = c.series_name;
            }
            if (!queueDialogSeasonNumber.value && c.season_number) {
              queueDialogSeasonNumber.value = c.season_number;
            }
          }

          const confidence = c.confidence ? ` (${c.confidence})` : "";
          const note = data.requires_confirmation ? " Confirmation required." : "";
          queueDialogPreview.textContent = `Detected: ${c.media_kind || "unknown"}${confidence}. Route: ${data.destination_subpath || "unsorted"}.${note}`;
        } catch (_) {
          queueDialogPreview.textContent = "Classification preview failed.";
        }
      };

      const openQueueDialog = async (config) => {
        queueDialogState = { ...config };
        queueDialogTitle.textContent = config.intent === "edit" ? `Recategorize Job #${config.jobId}` : "Add To Queue";
        queueDialogItemTitle.textContent = config.title || config.detailUrl || "";
        queueDialogMode.value = config.preferredMode || "premium";
        queueDialogMediaKind.value = config.mediaKind || "auto";
        queueDialogKidsTag.value =
          config.isKids === true ? "yes" : config.isKids === false ? "no" : "auto";
        queueDialogSeriesName.value = config.seriesName || "";
        queueDialogSeasonNumber.value = config.seasonNumber ? String(config.seasonNumber) : "";
        queueDialogChunkCount.value = String(config.chunkCount || Number(downloadChunkCount.value || 1) || 1);
        queueDialogPriority.value = String(config.priority || Number(downloadPriority.value || 0) || 0);

        const editMode = config.intent === "edit";
        queueDialogMode.disabled = editMode;
        queueDialogChunkCount.disabled = editMode;
        queueDialogPriority.disabled = editMode;
        updateQueueDialogMode();

        queueDialogBackdrop.classList.remove("hidden");
        await classifyForQueueDialog();
      };

      const setMovieInfoStatus = (statusEl, message, mode = "neutral") => {
        if (!statusEl) return;
        statusEl.textContent = message || "";
        statusEl.dataset.mode = mode;
      };

      const closeQueueDialog = () => {
        queueDialogBackdrop.classList.add("hidden");
        queueDialogState = null;
        queueDialogPreview.textContent = "";
      };

      queueDialogClose.addEventListener("click", closeQueueDialog);
      queueDialogCancel.addEventListener("click", closeQueueDialog);
      queueDialogBackdrop.addEventListener("click", (event) => {
        if (event.target === queueDialogBackdrop) {
          closeQueueDialog();
        }
      });
      [queueDialogMediaKind, queueDialogKidsTag, queueDialogSeriesName, queueDialogSeasonNumber].forEach((el) => {
        el.addEventListener("change", async () => {
          updateQueueDialogMode();
          await classifyForQueueDialog();
        });
      });

      queueDialogForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!queueDialogState) return;
        const mediaPayload = queueDialogMediaPayload();

        if (queueDialogState.intent === "edit") {
          const res = await fetch(`/api/downloads/${queueDialogState.jobId}/classification`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(mediaPayload),
          });
          const data = await res.json();
          if (!res.ok) {
            setDownloadStatus(data.error || "Failed to update category.", "error");
            if (data.destination_subpath) {
              queueDialogPreview.textContent = `Suggested route: ${data.destination_subpath}`;
            }
            return;
          }
          setDownloadStatus(`Updated category for job #${queueDialogState.jobId}.`, "ok");
          closeQueueDialog();
          await refreshDownloads();
          return;
        }

        const payload = {
          detail_url: queueDialogState.detailUrl,
          file_id: queueDialogState.fileId,
          title: queueDialogState.title || null,
          preferred_mode: queueDialogMode.value || "premium",
          chunk_count: Number(queueDialogChunkCount.value || 1),
          priority: Number(queueDialogPriority.value || 0),
          ...mediaPayload,
        };
        const result = await enqueueDownload(payload);
        if (result.ok) {
          closeQueueDialog();
          await refreshDownloads();
        } else if (result.duplicateJob && result.duplicateIsActive) {
          closeQueueDialog();
          await refreshDownloads();
          focusDownloadJob(result.duplicateJob.id);
        }
      });

      document.querySelectorAll(".movie-info-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const cardBody = btn.closest(".card-body");
          const statusEl = cardBody?.querySelector(".movie-info-status");
          const openedTab = window.open("about:blank", "_blank");
          if (openedTab) {
            try {
              openedTab.opener = null;
              openedTab.document.title = "Resolving movie info...";
            } catch (_) {
              // Ignore blank-tab document access issues in stricter browsers.
            }
          }

          btn.disabled = true;
          setMovieInfoStatus(statusEl, "Resolving movie info link...", "neutral");

          try {
            const res = await fetch("/api/movie/info-link", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                title: btn.dataset.title || "",
                primary_year: btn.dataset.primaryYear ? Number(btn.dataset.primaryYear) : null,
                search_query: btn.dataset.searchQuery || null,
                search_title: btn.dataset.searchTitle || null,
              }),
            });
            const data = await res.json();

            if (!res.ok || !data.found || !data.preferred_url) {
              if (openedTab && !openedTab.closed) {
                openedTab.close();
              }
              setMovieInfoStatus(statusEl, data.error || "No movie info link found for this result.", "error");
              return;
            }

            if (openedTab && !openedTab.closed) {
              openedTab.location.replace(data.preferred_url);
            } else {
              const fallbackTab = window.open(data.preferred_url, "_blank");
              if (!fallbackTab) {
                setMovieInfoStatus(statusEl, "Popup was blocked. Allow popups to open movie info links.", "error");
                return;
              }
            }
            setMovieInfoStatus(
              statusEl,
              `Opened info for ${data.resolved_title || btn.dataset.title || "this movie"}.`,
              "ok"
            );
          } catch (_) {
            if (openedTab && !openedTab.closed) {
              openedTab.close();
            }
            setMovieInfoStatus(statusEl, "Movie info lookup failed.", "error");
          } finally {
            btn.disabled = false;
          }
        });
      });

      document.querySelectorAll(".save-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const payload = {
            file_id: btn.dataset.fileId ? Number(btn.dataset.fileId) : null,
            title: btn.dataset.title || null,
            detail_url: btn.dataset.detailUrl,
            size: btn.dataset.size || null,
            duration: btn.dataset.duration || null,
            extension: btn.dataset.extension || null,
            primary_year: btn.dataset.primaryYear ? Number(btn.dataset.primaryYear) : null,
            detected_languages: (btn.dataset.detectedLanguages || "")
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
            has_dub_hint: btn.dataset.hasDubHint === "1",
            has_subtitle_hint: btn.dataset.hasSubtitleHint === "1",
          };

          const res = await fetch("/api/saved", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) {
            alert(`Save failed: ${data.error || "unknown error"}`);
            return;
          }
          upsertSavedStateItem(data);
        });
      });

      document.querySelectorAll(".queue-dialog-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          await openQueueDialog({
            intent: "enqueue",
            detailUrl: btn.dataset.detailUrl,
            fileId: btn.dataset.fileId ? Number(btn.dataset.fileId) : null,
            title: btn.dataset.title || "",
            preferredMode: "premium",
          });
        });
      });

      const setAccountStatus = (text, mode = "neutral") => {
        accountStatus.textContent = text;
        accountStatus.dataset.mode = mode;
      };

      const refreshAccountStatus = async () => {
        try {
          const res = await fetch("/api/account");
          const data = await res.json();
          if (!res.ok) {
            setAccountStatus(`Status error: ${data.error || "unknown error"}`, "error");
            return;
          }
          if (data.configured) {
            accountLogin.value = data.login || "";
            setAccountStatus(`Configured for: ${data.login}`, "ok");
          } else {
            accountLogin.value = "";
            setAccountStatus("Not configured", "neutral");
          }
        } catch (_) {
          setAccountStatus("Status unavailable", "error");
        }
      };

      downloadForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const detailUrl = downloadDetailUrl.value.trim();
        if (!detailUrl) {
          setDownloadStatus("Detail URL is required.", "error");
          return;
        }

        const payload = {
          detail_url: detailUrl,
          preferred_mode: downloadMode.value || "premium",
          chunk_count: Number(downloadChunkCount.value || 1),
          priority: Number(downloadPriority.value || 0),
          ...buildMediaRoutingPayload(),
        };

        const result = await enqueueDownload(payload);
        if (result.ok) {
          downloadDetailUrl.value = "";
          await refreshDownloads();
        } else if (result.duplicateJob && result.duplicateIsActive) {
          await refreshDownloads();
          focusDownloadJob(result.duplicateJob.id);
        }
      });

      refreshDownloadsBtn.addEventListener("click", async () => {
        setDownloadStatus("Refreshing queue...", "neutral");
        await refreshDownloads();
      });

      clearFinishedBtn.addEventListener("click", async () => {
        setDownloadStatus("Clearing finished jobs...", "neutral");
        try {
          const res = await fetch("/api/downloads/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ statuses: ["done", "failed", "canceled"] }),
          });
          const data = await res.json();
          if (!res.ok) {
            setDownloadStatus(data.error || "Failed to clear jobs.", "error");
            return;
          }
          setDownloadStatus(`Cleared ${data.deleted} finished jobs.`, "ok");
          await refreshDownloads();
        } catch (_) {
          setDownloadStatus("Failed to clear finished jobs.", "error");
        }
      });

      fileResultsCardsBtn?.addEventListener("click", () => {
        setFileResultsView("cards");
      });

      fileResultsListBtn?.addEventListener("click", () => {
        setFileResultsView("list");
      });

      fileResultsToolbar?.querySelectorAll(".file-results-filter-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          setFileResultsFilter(btn.dataset.filter || "all");
        });
      });

      fileSearchAdvancedFilters?.addEventListener("toggle", () => {
        window.localStorage.setItem(FILE_SEARCH_ADVANCED_KEY, fileSearchAdvancedFilters.open ? "1" : "0");
      });

      downloadSettingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = {
          max_concurrent_jobs: Number(settingsMaxConcurrent.value || 1),
          default_chunk_count: Number(settingsDefaultChunks.value || 1),
          bandwidth_limit_kbps: Number(settingsBandwidth.value || 0),
        };
        setDownloadStatus("Saving download settings...", "neutral");
        try {
          const res = await fetch("/api/downloads/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) {
            setDownloadStatus(data.error || "Failed to save download settings.", "error");
            return;
          }
          settingsMaxConcurrent.value = data.max_concurrent_jobs;
          settingsDefaultChunks.value = data.default_chunk_count;
          settingsBandwidth.value = data.bandwidth_limit_kbps;
          downloadChunkCount.value = data.default_chunk_count;
          setDownloadStatus(
            `Settings saved: ${data.max_concurrent_jobs} workers, default chunks ${data.default_chunk_count}, bandwidth ${data.bandwidth_limit_kbps} KB/s.`,
            "ok"
          );
        } catch (_) {
          setDownloadStatus("Failed to save download settings.", "error");
        }
      });

      accountForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const login = accountLogin.value.trim();
        const password = accountPassword.value;

        if (!login || !password) {
          setAccountStatus("Login and password are required.", "error");
          return;
        }

        setAccountStatus("Saving credentials...", "neutral");
        try {
          const res = await fetch("/api/account", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              login,
              password,
              verify: accountVerify.checked,
            }),
          });
          const data = await res.json();
          if (!res.ok) {
            setAccountStatus(data.error || "Failed to save credentials.", "error");
            return;
          }
          accountPassword.value = "";
          setAccountStatus(
            data.verified === false
              ? `Saved (not verified): ${data.login}`
              : `Saved for: ${data.login}`,
            "ok"
          );
          await refreshAccountStatus();
        } catch (_) {
          setAccountStatus("Failed to save credentials.", "error");
        }
      });

      accountClearBtn.addEventListener("click", async () => {
        setAccountStatus("Clearing credentials...", "neutral");
        try {
          const res = await fetch("/api/account", { method: "DELETE" });
          const data = await res.json();
          if (!res.ok || !data.cleared) {
            setAccountStatus(data.error || "Failed to clear credentials.", "error");
            return;
          }
          accountPassword.value = "";
          await refreshAccountStatus();
        } catch (_) {
          setAccountStatus("Failed to clear credentials.", "error");
        }
      });

      [categorySelect, sortSelect, languageInput, languageScopeSelect, strictDubbingInput, releaseYearInput, maxResultsInput].forEach((el) => {
        el?.addEventListener("change", () => {
          renderFileSearchActiveFilters();
          syncFileFiltersToTvEditor();
          renderTvActiveFilters();
        });
      });
      languageInput?.addEventListener("input", () => {
        renderFileSearchActiveFilters();
        syncFileFiltersToTvEditor();
        renderTvActiveFilters();
      });
      maxResultsInput?.addEventListener("input", () => {
        renderFileSearchActiveFilters();
        syncFileFiltersToTvEditor();
        renderTvActiveFilters();
      });
      releaseYearInput?.addEventListener("input", renderFileSearchActiveFilters);
      [tvFilterCategory, tvFilterLanguage, tvFilterLanguageScope, tvFilterStrictDubbing, tvFilterMaxResults].forEach((el) => {
        el?.addEventListener("change", () => {
          syncTvEditorToFileFilters();
          renderFileSearchActiveFilters();
          renderTvActiveFilters();
        });
      });
      tvFilterLanguage?.addEventListener("input", () => {
        syncTvEditorToFileFilters();
        renderFileSearchActiveFilters();
        renderTvActiveFilters();
      });
      tvFilterMaxResults?.addEventListener("input", () => {
        syncTvEditorToFileFilters();
        renderFileSearchActiveFilters();
        renderTvActiveFilters();
      });

      const initialMode = (() => {
        const saved = window.localStorage.getItem("searchMode");
        return saved === "tv" ? "tv" : "file";
      })();
      if (fileSearchAdvancedFilters) {
        fileSearchAdvancedFilters.open = window.localStorage.getItem(FILE_SEARCH_ADVANCED_KEY) === "1";
      }
      syncFileFiltersToTvEditor();
      renderFileSearchActiveFilters();
      renderTvActiveFilters();
      setSearchMode(initialMode);
      setFileResultsView(fileResultsView);
      setFileResultsFilter(fileResultsFilter);

      refreshAccountStatus();
      refreshDownloadSettings();
      refreshDownloads();
      refreshSavedCandidates();
      if (activeTvSearchJobId) {
        refreshActiveTvSearchJob({ force: true });
      }
      setInterval(refreshDownloads, 2500);
      setInterval(() => {
        refreshActiveTvSearchJob();
      }, 2500);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          refreshActiveTvSearchJob({ force: true });
        }
      });
