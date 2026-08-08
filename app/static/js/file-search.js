import { buildFileQueueKey } from "./keys.js";
import { writeFileResultsFilter, writeFileResultsView, writeFileSearchAdvancedOpen, writeSearchMode } from "./storage-state.js";

export const initFileSearch = ({
  elements,
  api,
  state,
  applyCardQueueState,
  bindQueueManageButtons,
  getActiveQueueState,
  openQueueDialog,
  enqueueDownload,
  refreshDownloads,
}) => {
  const {
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
    musicQueueAllBtn,
    musicAlbumQueueStatus,
  } = elements;

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
    return key ? state.savedResultsState.keys.has(key) : false;
  };

  const setSavedStateFromItems = (items) => {
    state.savedResultsState = buildSavedStateFromItems(items);
    refreshFileSearchResultsUi();
  };

  const upsertSavedStateItem = (item) => {
    const items = Array.from(state.savedResultsState.itemsByKey.values());
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

    fileSearchActiveFilters.innerHTML = `<strong>Active filters:</strong> ${parts.map((part) => `<code>${part}</code>`).join(" ")}`;
  };

  const setFileResultsView = (view) => {
    const next = view === "list" ? "list" : "cards";
    state.fileResultsView = next;
    if (fileResultsGrid) {
      fileResultsGrid.dataset.view = next;
    }
    fileResultsCardsBtn?.classList.toggle("active", next === "cards");
    fileResultsListBtn?.classList.toggle("active", next === "list");
    writeFileResultsView(next);
  };

  const setFileResultsFilter = (filter) => {
    const next = ["all", "unsaved", "saved", "queued", "playable"].includes(String(filter)) ? String(filter) : "all";
    state.fileResultsFilter = next;
    fileResultsToolbar?.querySelectorAll(".file-results-filter-chip").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.filter === next);
    });
    writeFileResultsFilter(next);
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
    const queueJob = fileKey ? getActiveQueueState().fileJobs.get(fileKey) || null : null;
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
    if (state.fileResultsFilter === "saved") return outcome.saved;
    if (state.fileResultsFilter === "unsaved") return !outcome.saved;
    if (state.fileResultsFilter === "queued") return outcome.queued;
    if (state.fileResultsFilter === "playable") return outcome.playable;
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
      const savedItem = outcome.fileKey ? state.savedResultsState.itemsByKey.get(outcome.fileKey) || null : null;

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

  const refreshSavedCandidates = async () => {
    if (!fileResultsGrid) return;
    try {
      const { ok, data } = await api.listSaved(1000);
      if (!ok) return;
      setSavedStateFromItems(data.items || []);
    } catch (_) {
      // Keep file search usable even if saved-state hydration fails.
    }
  };

  const setMovieInfoStatus = (statusEl, message, mode = "neutral") => {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.dataset.mode = mode;
  };

  musicQueueAllBtn?.addEventListener("click", async () => {
    const cards = Array.from(fileResultsGrid?.querySelectorAll(".result-card[data-detail-url]") || []);
    const activeJobs = getActiveQueueState().fileJobs;
    const seenKeys = new Set();
    const candidates = cards.filter((card) => {
      const key = buildFileQueueKey({ fileId: card.dataset.fileId, detailUrl: card.dataset.detailUrl });
      if (key && seenKeys.has(key)) return false;
      if (key) seenKeys.add(key);
      return !key || !activeJobs.get(key);
    });
    if (!candidates.length) {
      if (musicAlbumQueueStatus) musicAlbumQueueStatus.textContent = "No unqueued music results are available.";
      return;
    }

    musicQueueAllBtn.disabled = true;
    let queued = 0;
    let skipped = 0;
    let failed = 0;
    if (musicAlbumQueueStatus) musicAlbumQueueStatus.textContent = `Queueing ${candidates.length} music results...`;
    try {
      for (const card of candidates) {
        const result = await enqueueDownload?.({
          detail_url: card.dataset.detailUrl,
          file_id: card.dataset.fileId ? Number(card.dataset.fileId) : null,
          title: card.dataset.title || card.querySelector("h3")?.textContent?.trim() || "Music result",
          source_type: "sdilej",
          preferred_mode: "premium",
          destination_preset: "music",
          media_kind: "music",
          is_kids: false,
          chunk_count: 1,
          priority: 0,
        });
        if (result?.ok) queued += 1;
        else if (result?.duplicateDone) skipped += 1;
        else failed += 1;
      }
      await refreshDownloads?.();
      if (musicAlbumQueueStatus) {
        musicAlbumQueueStatus.textContent = `${queued} music results queued${skipped ? `, ${skipped} already present` : ""}${failed ? `, ${failed} failed` : "."}`;
        musicAlbumQueueStatus.dataset.mode = failed ? "warning" : "ok";
      }
    } finally {
      musicQueueAllBtn.disabled = false;
    }
  });

  const copyTextToClipboard = async (text) => {
    const value = String(text || "").trim();
    if (!value) return false;
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  };

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
        const { ok, data } = await api.resolveMovieInfoLink({
          title: btn.dataset.title || "",
          primary_year: btn.dataset.primaryYear ? Number(btn.dataset.primaryYear) : null,
          search_query: btn.dataset.searchQuery || null,
          search_title: btn.dataset.searchTitle || null,
        });

        if (!ok || !data.found || !data.preferred_url) {
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
        setMovieInfoStatus(statusEl, `Opened info for ${data.resolved_title || btn.dataset.title || "this movie"}.`, "ok");
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

  document.querySelectorAll(".copy-link-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const originalLabel = btn.dataset.defaultLabel || "Copy link";
      const copiedLabel = "Copied";
      const failedLabel = "Copy failed";
      const url = btn.dataset.url || "";

      btn.disabled = true;
      try {
        const ok = await copyTextToClipboard(url);
        btn.textContent = ok ? copiedLabel : failedLabel;
      } catch (_) {
        btn.textContent = failedLabel;
      } finally {
        window.setTimeout(() => {
          btn.textContent = originalLabel;
          btn.disabled = false;
        }, 1200);
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

      const { ok, data } = await api.saveCandidate(payload);
      if (!ok) {
        window.alert(`Save failed: ${data.error || "unknown error"}`);
        return;
      }
      upsertSavedStateItem(data);
    });
  });

  document.querySelectorAll(".queue-dialog-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const musicResult = categorySelect?.value === "audio";
      await openQueueDialog({
        intent: "enqueue",
        detailUrl: btn.dataset.detailUrl,
        fileId: btn.dataset.fileId ? Number(btn.dataset.fileId) : null,
        title: btn.dataset.title || "",
        preferredMode: "premium",
        destinationPreset: musicResult ? "music" : "auto",
        mediaKind: musicResult ? "music" : null,
        isKids: musicResult ? false : null,
      });
    });
  });

  musicSearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const params = new URLSearchParams();
    const query = musicSearchQuery?.value.trim() || "";
    if (query) {
      params.set("query", query);
    }
    params.set("category", "audio");
    params.set("sort", musicSearchSort?.value || "downloads");
    params.set("max_results", musicSearchMaxResults?.value || "120");
    writeSearchMode("music");
    window.location.href = `/?${params.toString()}`;
  });

  if (musicSearchPanel && categorySelect?.value === "audio") {
    writeSearchMode("music");
  }

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
    writeFileSearchAdvancedOpen(fileSearchAdvancedFilters.open);
  });

  return {
    renderFileSearchActiveFilters,
    setFileResultsView,
    setFileResultsFilter,
    refreshFileSearchResultsUi,
    setSavedStateFromItems,
    upsertSavedStateItem,
    refreshSavedCandidates,
  };
};
