import { basenameFromPath, esc, stripHtml, truncateText } from "./dom-utils.js";
import {
  ACTIVE_QUEUE_STATUSES,
  buildEpisodeQueueKey,
  buildFileQueueKey,
  buildTvEpisodeKey,
  FILE_RESULTS_FILTER_KEY,
  FILE_RESULTS_VIEW_KEY,
  FILE_SEARCH_ADVANCED_KEY,
  normalizeQueueTextKey,
  sameStringList,
  TV_ACTIVE_JOB_KEY,
} from "./keys.js";
import { pluralize, queueBadgeLabelForStatus, queueButtonLabelForStatus } from "./formatters.js";
import {
  clearActiveTvSearchJobId,
  readActiveTvSearchJobId,
  readActiveWorkspaceTab,
  readFileResultsFilter,
  readFileResultsView,
  readFileSearchAdvancedOpen,
  readSearchMode,
  writeActiveTvSearchJobId,
  writeActiveWorkspaceTab,
  writeSearchMode,
} from "./storage-state.js";
import { api } from "./api.js";
import { createRuntimeState } from "./runtime-state.js";
import { initDownloads } from "./downloads.js";
import { initFileSearch } from "./file-search.js";
import { initTvSearch } from "./tv-search.js";
import { initQueueDialog } from "./queue-dialog.js";
import { initWorkspaceTabs } from "./workspace-tabs.js";

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
      const state = createRuntimeState({
        fileResultsView: readFileResultsView(),
        fileResultsFilter: readFileResultsFilter(),
        searchMode: "file",
        activeTvSearchJobId: readActiveTvSearchJobId(),
      });
      let timer = state.timer;
      let tvLookupState = state.tvLookupState;
      let tvResultsState = state.tvResultsState;
      let tvResultsFilter = state.tvResultsFilter;
      let searchMode = state.searchMode;
      let activeTvSearchJobId = state.activeTvSearchJobId;
      let tvJobPollInFlight = state.tvJobPollInFlight;
      let tvEpisodeSearchOverrides = state.tvEpisodeSearchOverrides;
      let tvEpisodeSearchesInFlight = state.tvEpisodeSearchesInFlight;
      let tvShowSummarySignature = state.tvShowSummarySignature;
      let activeQueueState = state.activeQueueState;

      const setDownloadStatus = (text, mode = "neutral") => {
        if (!downloadStatus) return;
        downloadStatus.textContent = text || "";
        downloadStatus.dataset.mode = mode;
      };

      const focusDownloadJob = (jobId) => {
        const job = downloadJobsEl?.querySelector(`[data-job-id="${CSS.escape(String(jobId))}"]`);
        if (!job) {
          setDownloadStatus(`Job #${jobId} is no longer visible in the queue.`, "neutral");
          return false;
        }
        job.scrollIntoView({ behavior: "smooth", block: "center" });
        job.classList.add("job-focused");
        window.setTimeout(() => job.classList.remove("job-focused"), 1200);
        setDownloadStatus(`Showing job #${jobId}.`, "ok");
        return true;
      };

      const applyCardQueueState = (...args) => tvApi?.applyCardQueueState?.(...args);

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
        state.activeQueueState = activeQueueState;
        const tvDownloadedStateChanged = tvResultsState ? tvApi?.syncTvResultsDownloadedStateFromJobs?.(jobs) : false;
        fileSearchApi?.refreshFileSearchResultsUi?.();
        if (tvResultsState && tvApi) {
          if (tvDownloadedStateChanged) {
            tvApi.renderTvResults(tvResultsState);
          } else {
            tvApi.refreshTvResultsQueueUi();
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

      const initialTab = (() => {
        const hash = (window.location.hash || "").replace("#", "").trim();
        if (hash === "search" || hash === "downloads") return hash;
        const saved = readActiveWorkspaceTab();
        if (saved === "search" || saved === "downloads") return saved;
        return "search";
      })();

      let tvApi = null;

      let downloadsApi = null;
      let fileSearchApi = null;
      let openQueueDialog = null;

      const queueDialogApi = initQueueDialog({
        elements: {
          queueDialogBackdrop,
          queueDialogClose,
          queueDialogCancel,
          queueDialogForm,
          queueDialogTitle,
          queueDialogItemTitle,
          queueDialogMode,
          queueDialogMediaKind,
          queueDialogKidsTag,
          queueDialogSeriesName,
          queueDialogSeasonNumber,
          queueDialogChunkCount,
          queueDialogPriority,
          queueDialogPreview,
          downloadChunkCount,
          downloadPriority,
        },
        api,
        setDownloadStatus,
        refreshDownloads: () => downloadsApi?.refreshDownloads?.(),
        enqueueDownload: (payload) => downloadsApi?.enqueueDownload?.(payload),
        focusDownloadJob,
      });
      openQueueDialog = queueDialogApi.openQueueDialog;

      downloadsApi = initDownloads({
        elements: {
          accountStatus,
          accountForm,
          accountLogin,
          accountPassword,
          accountVerify,
          accountClearBtn,
          downloadForm,
          downloadDetailUrl,
          downloadMode,
          downloadMediaKind,
          downloadKidsTag,
          downloadSeriesName,
          downloadSeasonNumber,
          downloadChunkCount,
          downloadPriority,
          downloadSettingsForm,
          settingsMaxConcurrent,
          settingsDefaultChunks,
          settingsBandwidth,
          downloadJobsEl,
          refreshDownloadsBtn,
          clearFinishedBtn,
          downloadSummary,
          downloadWorkerState,
        },
        api,
        setActiveQueueStateFromJobs,
        setDownloadStatus,
        focusDownloadJob,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
      });

      const {
        refreshDownloads,
        refreshDownloadSettings,
        refreshAccountStatus,
      } = downloadsApi;

      fileSearchApi = initFileSearch({
        elements: {
          categorySelect,
          sortSelect,
          languageInput,
          languageScopeSelect,
          strictDubbingInput,
          releaseYearInput,
          maxResultsInput,
          fileSearchAdvancedFilters,
          fileSearchActiveFilters,
          fileResultsToolbar,
          fileResultsToolbarSummary,
          fileResultsVisibleCount,
          fileResultsCardsBtn,
          fileResultsListBtn,
          fileResultsGrid,
          fileResultsEmpty,
        },
        api,
        state,
        applyCardQueueState,
        bindQueueManageButtons,
        getActiveQueueState: () => activeQueueState,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
      });

      const {
        renderFileSearchActiveFilters,
        setFileResultsView,
        setFileResultsFilter,
        refreshSavedCandidates,
      } = fileSearchApi;

      tvApi = initTvSearch({
        elements: {
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
          queryInput: input,
          suggestions: list,
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
        },
        api,
        state,
        setActiveQueueStateFromJobs,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
      });

      const {
        renderTvActiveFilters,
        syncFileFiltersToTvEditor,
        syncTvEditorToFileFilters,
        setSearchMode,
        refreshActiveTvSearchJob,
      } = tvApi;

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
        return readSearchMode();
      })();
      if (fileSearchAdvancedFilters) {
        fileSearchAdvancedFilters.open = readFileSearchAdvancedOpen();
      }
      syncFileFiltersToTvEditor();
      renderFileSearchActiveFilters();
      renderTvActiveFilters();
      initWorkspaceTabs({
        workspaceTabs,
        tabSections,
        initialTab,
        onTabChange: (resolved) => {
          window.location.hash = resolved;
          writeActiveWorkspaceTab(resolved);
        },
      });
      setSearchMode(initialMode);
      setFileResultsView(state.fileResultsView);
      setFileResultsFilter(state.fileResultsFilter);

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
