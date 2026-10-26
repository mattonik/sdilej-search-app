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
      const audioPreferenceSelect = document.getElementById("audioPreferenceSelect");
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
      const musicSearchModeBtn = document.getElementById("musicSearchModeBtn");
      const discoverySearchModeBtn = document.getElementById("discoverySearchModeBtn");
      const kidsSearchModeBtn = document.getElementById("kidsSearchModeBtn");
      const searchModeHint = document.getElementById("searchModeHint");
      const movieDiscoveryPanel = document.getElementById("movieDiscoveryPanel");
      const movieDiscoveryForm = document.getElementById("movieDiscoveryForm");
      const movieDiscoveryMode = document.getElementById("movieDiscoveryMode");
      const movieDiscoveryWindow = document.getElementById("movieDiscoveryWindow");
      const movieDiscoveryGenre = document.getElementById("movieDiscoveryGenre");
      const movieDiscoveryYear = document.getElementById("movieDiscoveryYear");
      const movieDiscoveryLimit = document.getElementById("movieDiscoveryLimit");
      const movieDiscoveryStatus = document.getElementById("movieDiscoveryStatus");
      const movieDiscoveryResults = document.getElementById("movieDiscoveryResults");
      const movieDiscoverySourceBtn = document.getElementById("movieDiscoverySourceBtn");
      const sdilejPopularSourceBtn = document.getElementById("sdilejPopularSourceBtn");
      const movieDiscoverySourcePanel = document.getElementById("movieDiscoverySourcePanel");
      const sdilejPopularSourcePanel = document.getElementById("sdilejPopularSourcePanel");
      const sdilejPopularFilter = document.getElementById("sdilejPopularFilter");
      const sdilejPopularType = document.getElementById("sdilejPopularType");
      const sdilejPopularSort = document.getElementById("sdilejPopularSort");
      const sdilejPopularRefreshBtn = document.getElementById("sdilejPopularRefreshBtn");
      const sdilejPopularStatus = document.getElementById("sdilejPopularStatus");
      const sdilejPopularResults = document.getElementById("sdilejPopularResults");
      const fileSearchPanel = document.getElementById("fileSearchPanel");
      const musicSearchPanel = document.getElementById("musicSearchPanel");
      const musicSearchForm = document.getElementById("musicSearchForm");
      const musicSearchQuery = document.getElementById("musicSearchQuery");
      const musicSearchSort = document.getElementById("musicSearchSort");
      const musicSearchMaxResults = document.getElementById("musicSearchMaxResults");
      const musicQueueAllBtn = document.getElementById("musicQueueAllBtn");
      const musicAlbumQueueStatus = document.getElementById("musicAlbumQueueStatus");
      const tvModePanel = document.getElementById("tvModePanel");
      const tvLookupForm = document.getElementById("tvLookupForm");
      const tvShowName = document.getElementById("tvShowName");
      const tvLookupBtn = document.getElementById("tvLookupBtn");
      const tvStatus = document.getElementById("tvStatus");
      const tvShowSummaryCard = document.getElementById("tvShowSummaryCard");
      const tvShowMatches = document.getElementById("tvShowMatches");
      const tvLookupInfo = document.getElementById("tvLookupInfo");
      const tvSeasonPicker = document.getElementById("tvSeasonPicker");
      const tvActiveFilters = document.getElementById("tvActiveFilters");
      const tvFilterCategory = document.getElementById("tvFilterCategory");
      const tvFilterLanguage = document.getElementById("tvFilterLanguage");
      const tvFilterLanguageScope = document.getElementById("tvFilterLanguageScope");
      const tvFilterAudioPreference = document.getElementById("tvFilterAudioPreference");
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
      const youtubeAuthStatus = document.getElementById("youtubeAuthStatus");
      const youtubeAuthForm = document.getElementById("youtubeAuthForm");
      const youtubeAuthMode = document.getElementById("youtubeAuthMode");
      const youtubeCookiesPath = document.getElementById("youtubeCookiesPath");
      const youtubeCookiesText = document.getElementById("youtubeCookiesText");
      const youtubeCookiesBrowser = document.getElementById("youtubeCookiesBrowser");
      const youtubeAuthClearBtn = document.getElementById("youtubeAuthClearBtn");
      const youtubeAuthTestUrl = document.getElementById("youtubeAuthTestUrl");
      const youtubeAuthTestBtn = document.getElementById("youtubeAuthTestBtn");
      const libraryTvMissingForm = document.getElementById("libraryTvMissingForm");
      const libraryTvShowName = document.getElementById("libraryTvShowName");
      const libraryStatus = document.getElementById("libraryStatus");
      const libraryTvMissingResults = document.getElementById("libraryTvMissingResults");
      const libraryTvModeBtn = document.getElementById("libraryTvModeBtn");
      const libraryKidsModeBtn = document.getElementById("libraryKidsModeBtn");
      const libraryMusicModeBtn = document.getElementById("libraryMusicModeBtn");
      const libraryTvPanel = document.getElementById("libraryTvPanel");
      const libraryMusicPanel = document.getElementById("libraryMusicPanel");
      const libraryFolderHeading = document.getElementById("libraryFolderHeading");
      const libraryFolderHint = document.getElementById("libraryFolderHint");
      const libraryFolderKind = document.getElementById("libraryFolderKind");
      const libraryFoldersScanBtn = document.getElementById("libraryFoldersScanBtn");
      const libraryFolderResults = document.getElementById("libraryFolderResults");
      const libraryDeepScanResults = document.getElementById("libraryDeepScanResults");
      const libraryMusicFoldersScanBtn = document.getElementById("libraryMusicFoldersScanBtn");
      const libraryMusicFolderResults = document.getElementById("libraryMusicFolderResults");
      const libraryMusicDeepScanResults = document.getElementById("libraryMusicDeepScanResults");
      const downloadForm = document.getElementById("downloadForm");
      const downloadSourceType = document.getElementById("downloadSourceType");
      const downloadDetailUrl = document.getElementById("downloadDetailUrl");
      const downloadModeLabel = document.getElementById("downloadModeLabel");
      const downloadMode = document.getElementById("downloadMode");
      const downloadDestinationPreset = document.getElementById("downloadDestinationPreset");
      const downloadDestinationPreview = document.getElementById("downloadDestinationPreview");
      const downloadMediaKind = document.getElementById("downloadMediaKind");
      const downloadKidsTag = document.getElementById("downloadKidsTag");
      const downloadTvFields = document.getElementById("downloadTvFields");
      const downloadSeriesName = document.getElementById("downloadSeriesName");
      const downloadSeriesSuggestions = document.getElementById("downloadSeriesSuggestions");
      const downloadSeasonNumber = document.getElementById("downloadSeasonNumber");
      const downloadPlaylistLabel = document.getElementById("downloadPlaylistLabel");
      const downloadPlaylist = document.getElementById("downloadPlaylist");
      const downloadYoutubeAccessHint = document.getElementById("downloadYoutubeAccessHint");
      const openYoutubeSettingsBtn = document.getElementById("openYoutubeSettingsBtn");
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
      const downloadNavBadge = document.getElementById("downloadNavBadge");
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
      const state = {
        timer: null,
        tvLookupState: null,
        tvResultsState: null,
        tvResultsFilter: "all",
        tvEpisodeResultsSortMode: "best",
        fileResultsView: readFileResultsView(),
        fileResultsFilter: readFileResultsFilter(),
        searchMode: "file",
        activeTvSearchJobId: readActiveTvSearchJobId(),
        tvJobPollInFlight: false,
        tvEpisodeSearchOverrides: new Map(),
        tvEpisodeSearchesInFlight: new Set(),
        tvShowSummarySignature: "",
        savedResultsState: {
          keys: new Set(),
          itemsByKey: new Map(),
        },
        activeQueueState: {
          fileJobs: new Map(),
          episodeJobs: new Map(),
          jobsById: new Map(),
        },
      };
      let tvResultsState = state.tvResultsState;
      let activeTvSearchJobId = state.activeTvSearchJobId;
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
        if (hash === "search" || hash === "downloads" || hash === "library" || hash === "settings") return hash;
        if (hash === "account") return "settings";
        const saved = readActiveWorkspaceTab();
        if (saved === "search" || saved === "downloads" || saved === "library" || saved === "settings") return saved;
        if (saved === "account") return "settings";
        return "search";
      })();

      let setWorkspaceTab = null;
      let activeWorkspaceTab = initialTab;
      let workspaceTabsReady = false;
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
          youtubeAuthStatus,
          youtubeAuthForm,
          youtubeAuthMode,
          youtubeCookiesPath,
          youtubeCookiesText,
          youtubeCookiesBrowser,
          youtubeAuthClearBtn,
          youtubeAuthTestUrl,
          youtubeAuthTestBtn,
          downloadForm,
          downloadSourceType,
          downloadDetailUrl,
          downloadModeLabel,
          downloadMode,
          downloadDestinationPreset,
          downloadDestinationPreview,
          downloadMediaKind,
          downloadKidsTag,
          downloadTvFields,
          downloadSeriesName,
          downloadSeriesSuggestions,
          downloadSeasonNumber,
          downloadPlaylistLabel,
          downloadPlaylist,
          downloadYoutubeAccessHint,
          openYoutubeSettingsBtn,
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
          downloadNavBadge,
        },
        api,
        setActiveQueueStateFromJobs,
        setDownloadStatus,
        focusDownloadJob,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
        openYoutubeSettings: () => {
          const details = document.getElementById("youtubeAuthDetails");
          if (details) details.open = true;
          setWorkspaceTab?.("settings");
          window.requestAnimationFrame(() => {
            details?.scrollIntoView({ behavior: "smooth", block: "start" });
          });
        },
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
          movieDiscoverySourceBtn,
          sdilejPopularSourceBtn,
          movieDiscoverySourcePanel,
          sdilejPopularSourcePanel,
          sdilejPopularFilter,
          sdilejPopularType,
          sdilejPopularSort,
          sdilejPopularRefreshBtn,
          sdilejPopularStatus,
          sdilejPopularResults,
        },
        api,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
        openTvSearch: async (showName) => {
          if (!showName || !tvApi) return;
          tvApi.setSearchMode("tv");
          tvShowName.value = showName;
          await tvApi.runTvLookup();
        },
      });

      initLibraryManagement({
        elements: {
          libraryTvMissingForm,
          libraryTvShowName,
          libraryStatus,
          libraryTvMissingResults,
          libraryTvModeBtn,
          libraryKidsModeBtn,
          libraryMusicModeBtn,
          libraryTvPanel,
          libraryMusicPanel,
          libraryFolderHeading,
          libraryFolderHint,
          libraryFolderKind,
          libraryFoldersScanBtn,
          libraryFolderResults,
          libraryDeepScanResults,
          libraryMusicFoldersScanBtn,
          libraryMusicFolderResults,
          libraryMusicDeepScanResults,
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
          audioPreferenceSelect,
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
          musicQueueAllBtn,
          musicAlbumQueueStatus,
          categorySelect,
        },
        api,
        state,
        applyCardQueueState,
        bindQueueManageButtons,
        getActiveQueueState: () => activeQueueState,
        openQueueDialog: (...args) => openQueueDialog?.(...args),
        enqueueDownload: (payload) => downloadsApi?.enqueueDownload?.(payload),
        refreshDownloads: () => downloadsApi?.refreshDownloads?.(),
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
          audioPreferenceSelect,
          strictDubbingInput,
          releaseYearInput,
          maxResultsInput,
          fileSearchModeBtn,
          tvSearchModeBtn,
          musicSearchModeBtn,
          discoverySearchModeBtn,
          kidsSearchModeBtn,
          searchModeHint,
          fileSearchPanel,
          musicSearchPanel,
          movieDiscoveryPanel,
          kidsCatalogPanel,
          tvModePanel,
          queryInput: input,
          suggestions: list,
          fileResultsBlocks,
          tvActiveFilters,
          tvShowSummaryCard,
          tvShowMatches,
          tvLookupInfo,
          tvSeasonPicker,
          tvLookupForm,
          tvShowName,
          tvSearchBtn,
          tvResults,
          tvFilterCategory,
          tvFilterLanguage,
          tvFilterLanguageScope,
          tvFilterAudioPreference,
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

      [categorySelect, sortSelect, languageInput, languageScopeSelect, audioPreferenceSelect, strictDubbingInput, releaseYearInput, maxResultsInput].forEach((el) => {
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
      [tvFilterCategory, tvFilterLanguage, tvFilterLanguageScope, tvFilterAudioPreference, tvFilterStrictDubbing, tvFilterMaxResults].forEach((el) => {
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
        const params = new URLSearchParams(window.location.search || "");
        const hasFileSearchParams = ["query", "category", "sort", "language", "release_year"].some((key) => params.has(key));
        if (hasFileSearchParams) {
          return (params.get("category") || "").toLowerCase() === "audio" ? "music" : "file";
        }
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
          activeWorkspaceTab = resolved;
          window.location.hash = resolved;
          writeActiveWorkspaceTab(resolved);
          if (workspaceTabsReady && resolved === "downloads") {
            refreshDownloads({ notifyOnFailure: true, background: true });
          }
        },
      });
      setWorkspaceTab = workspaceTabsApi.setActiveTab;
      workspaceTabsReady = true;
      window.addEventListener("hashchange", () => {
        const hash = (window.location.hash || "").replace("#", "").trim();
        const tab = hash === "account" ? "settings" : hash;
        if (["search", "downloads", "library", "settings"].includes(tab) && tab !== activeWorkspaceTab) {
          setWorkspaceTab(tab);
        }
      });
      setSearchMode(initialMode);
      setFileResultsView(state.fileResultsView);
      setFileResultsFilter(state.fileResultsFilter);

      refreshAccountStatus();
      downloadsApi?.refreshYoutubeAuthStatus?.();
      refreshDownloadSettings();
      refreshDownloads({ notifyOnFailure: true });
      refreshSavedCandidates();
      if (activeTvSearchJobId) {
        refreshActiveTvSearchJob({ force: true });
      }
      const shouldPollDownloads = () =>
        document.visibilityState === "visible" &&
        (activeWorkspaceTab === "downloads" || downloadsApi?.hasActiveDownloads?.());
      setInterval(() => {
        if (shouldPollDownloads()) {
          refreshDownloads({ notifyOnFailure: true, background: true });
        }
      }, 2500);
      setInterval(() => {
        refreshActiveTvSearchJob();
      }, 2500);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          if (shouldPollDownloads()) {
            refreshDownloads({ notifyOnFailure: true, background: true });
          }
          refreshActiveTvSearchJob({ force: true });
        }
      });
