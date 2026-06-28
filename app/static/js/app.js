import { esc, stripHtml, truncateText } from "./dom-utils.js";
import {
  FILE_RESULTS_FILTER_KEY,
  FILE_RESULTS_VIEW_KEY,
  FILE_SEARCH_ADVANCED_KEY,
  TV_ACTIVE_JOB_KEY,
} from "./keys.js";
import { pluralize } from "./formatters.js";
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
import { createQueueUiHelpers } from "./queue-ui.js";
import { createStatusController } from "./status-ui.js";
import { initTvSearch } from "./tv-search.js";
import { initQueueDialog } from "./queue-dialog.js";
import { initWorkspaceTabs } from "./workspace-tabs.js";
import { initKidsCatalog } from "./kids-catalog.js";
import { initLibraryManagement } from "./library-management.js";
import { initMovieDiscovery } from "./movie-discovery.js";

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
      const movieDiscoveryPanel = document.getElementById("movieDiscoveryPanel");
      const movieDiscoveryForm = document.getElementById("movieDiscoveryForm");
      const movieDiscoveryMode = document.getElementById("movieDiscoveryMode");
      const movieDiscoveryWindow = document.getElementById("movieDiscoveryWindow");
      const movieDiscoveryGenre = document.getElementById("movieDiscoveryGenre");
      const movieDiscoveryYear = document.getElementById("movieDiscoveryYear");
      const movieDiscoveryLimit = document.getElementById("movieDiscoveryLimit");
      const movieDiscoveryStatus = document.getElementById("movieDiscoveryStatus");
      const movieDiscoveryResults = document.getElementById("movieDiscoveryResults");
      const fileSearchPanel = document.getElementById("fileSearchPanel");
      const musicSearchPanel = document.getElementById("musicSearchPanel");
      const musicSearchForm = document.getElementById("musicSearchForm");
      const musicSearchQuery = document.getElementById("musicSearchQuery");
      const musicSearchSort = document.getElementById("musicSearchSort");
      const musicSearchMaxResults = document.getElementById("musicSearchMaxResults");
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
      const libraryTvMissingForm = document.getElementById("libraryTvMissingForm");
      const libraryTvShowName = document.getElementById("libraryTvShowName");
      const libraryStatus = document.getElementById("libraryStatus");
      const libraryTvMissingResults = document.getElementById("libraryTvMissingResults");
      const youtubeQuickForm = document.getElementById("youtubeQuickForm");
      const youtubeQuickUrl = document.getElementById("youtubeQuickUrl");
      const youtubeQuickSubmit = document.getElementById("youtubeQuickSubmit");
      const downloadForm = document.getElementById("downloadForm");
      const downloadSourceType = document.getElementById("downloadSourceType");
      const downloadDetailUrl = document.getElementById("downloadDetailUrl");
      const downloadModeLabel = document.getElementById("downloadModeLabel");
      const downloadMode = document.getElementById("downloadMode");
      const downloadDestinationPreset = document.getElementById("downloadDestinationPreset");
      const downloadDestinationPreview = document.getElementById("downloadDestinationPreview");
      const downloadMediaKind = document.getElementById("downloadMediaKind");
      const downloadKidsTag = document.getElementById("downloadKidsTag");
      const downloadSeriesName = document.getElementById("downloadSeriesName");
      const downloadSeasonNumber = document.getElementById("downloadSeasonNumber");
      const downloadChunkCountLabel = document.getElementById("downloadChunkCountLabel");
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
      const openAccountTabBtn = document.getElementById("openAccountTabBtn");
      const kidsCatalogLoadBtn = document.getElementById("kidsCatalogLoadBtn");
      const kidsCatalogFilter = document.getElementById("kidsCatalogFilter");
      const kidsCatalogStatus = document.getElementById("kidsCatalogStatus");
      const kidsCatalogShows = document.getElementById("kidsCatalogShows");
      const kidsCatalogEpisodes = document.getElementById("kidsCatalogEpisodes");
      const workspaceTabs = Array.from(document.querySelectorAll(".workspace-tab"));
      const tabSections = Array.from(document.querySelectorAll(".tab-section"));
      const queueDialogBackdrop = document.getElementById("queueDialogBackdrop");
      const queueDialogClose = document.getElementById("queueDialogClose");
      const queueDialogCancel = document.getElementById("queueDialogCancel");
      const queueDialogForm = document.getElementById("queueDialogForm");
      const queueDialogTitle = document.getElementById("queueDialogTitle");
      const queueDialogItemTitle = document.getElementById("queueDialogItemTitle");
      const queueDialogMode = document.getElementById("queueDialogMode");
      const queueDialogDestinationPreset = document.getElementById("queueDialogDestinationPreset");
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
      const downloadStatusController = createStatusController(downloadStatus);
      const setDownloadStatus = downloadStatusController.setStatus;
      const queueUi = createQueueUiHelpers({
        downloadJobsEl,
        setDownloadStatus,
      });
      const {
        focusDownloadJob,
        bindQueueManageButtons,
        applyCardQueueState,
        applyTvResultQueueState,
        applyEpisodeQueueSummaryState,
        buildActiveQueueStateFromJobs,
      } = queueUi;

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
        if (hash === "search" || hash === "downloads" || hash === "library" || hash === "account") return hash;
        const saved = readActiveWorkspaceTab();
        if (saved === "search" || saved === "downloads" || saved === "library" || saved === "account") return saved;
        return "search";
      })();

      let setWorkspaceTab = null;
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
          queueDialogDestinationPreset,
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
          youtubeQuickForm,
          youtubeQuickUrl,
          youtubeQuickSubmit,
          downloadForm,
          downloadSourceType,
          downloadDetailUrl,
          downloadModeLabel,
          downloadMode,
          downloadDestinationPreset,
          downloadDestinationPreview,
          downloadMediaKind,
          downloadKidsTag,
          downloadSeriesName,
          downloadSeasonNumber,
          downloadChunkCountLabel,
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
          openAccountTabBtn,
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

      initKidsCatalog({
        elements: {
          kidsCatalogLoadBtn,
          kidsCatalogFilter,
          kidsCatalogStatus,
          kidsCatalogShows,
          kidsCatalogEpisodes,
        },
        api,
        enqueueDownload: (payload) => downloadsApi?.enqueueDownload?.(payload),
        refreshDownloads: () => downloadsApi?.refreshDownloads?.(),
        focusDownloadJob,
      });

      initMovieDiscovery({
        elements: {
          movieDiscoveryPanel,
          movieDiscoveryForm,
          movieDiscoveryMode,
          movieDiscoveryWindow,
          movieDiscoveryGenre,
          movieDiscoveryYear,
          movieDiscoveryLimit,
          movieDiscoveryStatus,
          movieDiscoveryResults,
        },
        api,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
      });

      initLibraryManagement({
        elements: {
          libraryTvMissingForm,
          libraryTvShowName,
          libraryStatus,
          libraryTvMissingResults,
        },
        api,
        setWorkspaceTab: (...args) => setWorkspaceTab?.(...args),
        getTvApi: () => tvApi,
      });

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
          musicSearchPanel,
          musicSearchForm,
          musicSearchQuery,
          musicSearchSort,
          musicSearchMaxResults,
          categorySelect,
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
          downloadStatus,
          tvStatus,
        },
        api,
        state,
        setActiveQueueStateFromJobs,
        applyTvResultQueueState,
        applyEpisodeQueueSummaryState,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
      });

      const {
        renderTvActiveFilters,
        syncFileFiltersToTvEditor,
        syncTvEditorToFileFilters,
        syncTvResultsDownloadedStateFromJobs,
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
      const workspaceTabsApi = initWorkspaceTabs({
        workspaceTabs,
        tabSections,
        initialTab,
        onTabChange: (resolved) => {
          window.location.hash = resolved;
          writeActiveWorkspaceTab(resolved);
        },
      });
      setWorkspaceTab = workspaceTabsApi.setActiveTab;
      openAccountTabBtn?.addEventListener("click", () => setWorkspaceTab?.("account"));
      setSearchMode(initialMode);
      setFileResultsView(state.fileResultsView);
      setFileResultsFilter(state.fileResultsFilter);

      refreshAccountStatus();
      refreshDownloadSettings();
      refreshDownloads({ notifyOnFailure: true });
      refreshSavedCandidates();
      if (activeTvSearchJobId) {
        refreshActiveTvSearchJob({ force: true });
      }
      setInterval(() => {
        refreshDownloads({ notifyOnFailure: true });
      }, 2500);
      setInterval(() => {
        refreshActiveTvSearchJob();
      }, 2500);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          refreshActiveTvSearchJob({ force: true });
        }
      });
