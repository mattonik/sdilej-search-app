import { esc } from "./dom-utils.js";
import { formatBytes, formatEta, formatSpeed } from "./formatters.js";
import { ACTIVE_QUEUE_STATUSES } from "./keys.js";
import { buildStatusErrorState, createStatusController } from "./status-ui.js";

export const initDownloads = ({
  elements,
  api,
  setActiveQueueStateFromJobs,
  setDownloadStatus,
  focusDownloadJob,
  openQueueDialog,
}) => {
  const {
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
    youtubeQuickForm,
    youtubeQuickDestinationPreset,
    youtubeQuickUrl,
    youtubeQuickPlaylist,
    youtubeQuickTvFields,
    youtubeQuickSeriesName,
    youtubeQuickSeriesSuggestions,
    youtubeQuickSeasonNumber,
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
  } = elements;

  const setAccountStatus = (value, mode = "neutral") => {
    if (!accountStatus) return;
    const text = typeof value === "object" && value !== null ? value.message || value.text || value.error || "" : value;
    const nextMode = typeof value === "object" && value !== null ? value.mode || mode : mode;
    accountStatus.textContent = text || "";
    accountStatus.dataset.mode = nextMode;
  };

  const youtubeAuthStatusController = createStatusController(youtubeAuthStatus);
  const setYoutubeAuthStatus = (value, mode = "neutral") => youtubeAuthStatusController.setStatus(value, mode);

  let refreshDownloadsInFlight = false;
  let refreshDownloadsQueued = false;
  let refreshDownloadsQueuedOptions = null;
  let refreshDownloadsFailures = 0;
  let queueRefreshWarningVisible = false;
  let nextBackgroundRefreshAt = 0;
  let lastSuccessfulRefreshAt = 0;
  let destinationPreviewSeq = 0;
  let youtubeQuickTvSuggestionsSeq = 0;

  const isYoutubeLikeUrl = (value) => {
    const text = String(value || "").trim().toLowerCase();
    return /(^https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\//.test(text);
  };

  const formatRefreshTime = (timestamp) => timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "n/a";

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

  const showDownloadError = (data, fallbackMessage, options = {}) => {
    setDownloadStatus(buildStatusErrorState(data, fallbackMessage, options));
  };

  const resolveKidsValue = (rawValue) => {
    if (rawValue === "yes") return true;
    if (rawValue === "no") return false;
    return null;
  };

  const resolveYoutubeQuickPresetPlan = () => {
    const preset = youtubeQuickDestinationPreset?.value || "auto";
    if (preset === "movies") return { destination_preset: preset, media_kind: "movie", is_kids: false, needsTvFields: false };
    if (preset === "kids_movies") return { destination_preset: preset, media_kind: "movie", is_kids: true, needsTvFields: false };
    if (preset === "tv") return { destination_preset: preset, media_kind: "tv", is_kids: false, needsTvFields: true };
    if (preset === "kids_tv") return { destination_preset: preset, media_kind: "tv", is_kids: true, needsTvFields: true };
    if (preset === "music") return { destination_preset: preset, media_kind: "music", is_kids: false, needsTvFields: false };
    if (preset === "unsorted") return { destination_preset: preset, media_kind: null, is_kids: null, needsTvFields: false };
    return { destination_preset: "auto", media_kind: null, is_kids: null, needsTvFields: false };
  };

  const renderYoutubeQuickSeriesSuggestions = (items = []) => {
    if (!youtubeQuickSeriesSuggestions) return;
    youtubeQuickSeriesSuggestions.innerHTML = (Array.isArray(items) ? items : [])
      .map((item) => `<option value="${esc(item)}"></option>`)
      .join("");
  };

  const refreshYoutubeQuickSeriesSuggestions = async () => {
    if (!api.listLocalTvShows) return;
    const plan = resolveYoutubeQuickPresetPlan();
    if (!plan.needsTvFields) {
      renderYoutubeQuickSeriesSuggestions([]);
      return;
    }
    const seq = ++youtubeQuickTvSuggestionsSeq;
    const { ok, data } = await api.listLocalTvShows({
      q: youtubeQuickSeriesName?.value.trim() || "",
      isKids: Boolean(plan.is_kids),
      limit: 20,
    });
    if (seq !== youtubeQuickTvSuggestionsSeq) return;
    if (!ok) {
      renderYoutubeQuickSeriesSuggestions([]);
      return;
    }
    renderYoutubeQuickSeriesSuggestions(data.items || []);
  };

  const updateYoutubeQuickPresetFields = async () => {
    const plan = resolveYoutubeQuickPresetPlan();
    const showTvFields = Boolean(plan.needsTvFields);
    youtubeQuickTvFields?.classList.toggle("hidden", !showTvFields);
    if (youtubeQuickSeriesName) {
      youtubeQuickSeriesName.disabled = !showTvFields;
      if (!showTvFields) {
        youtubeQuickSeriesName.value = "";
      }
    }
    if (youtubeQuickSeasonNumber) {
      youtubeQuickSeasonNumber.disabled = !showTvFields;
      if (!showTvFields) {
        youtubeQuickSeasonNumber.value = "";
      }
    }
    if (!showTvFields) {
      renderYoutubeQuickSeriesSuggestions([]);
      return;
    }
    await refreshYoutubeQuickSeriesSuggestions();
  };

  const buildMediaRoutingPayload = () => {
    const mediaKind = downloadMediaKind.value === "auto" ? null : downloadMediaKind.value;
    const isKids = resolveKidsValue(downloadKidsTag.value);
    const payload = {
      destination_preset: downloadDestinationPreset?.value || "auto",
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

  const applyDestinationPresetToDownloadFields = () => {
    const preset = downloadDestinationPreset?.value || "auto";
    if (preset === "movies" || preset === "kids_movies") {
      downloadMediaKind.value = "movie";
      downloadKidsTag.value = preset === "kids_movies" ? "yes" : "no";
      downloadSeriesName.value = "";
      downloadSeasonNumber.value = "";
    } else if (preset === "tv" || preset === "kids_tv") {
      downloadMediaKind.value = "tv";
      downloadKidsTag.value = preset === "kids_tv" ? "yes" : "no";
    } else if (preset === "music") {
      downloadMediaKind.value = "music";
      downloadKidsTag.value = "no";
      downloadSeriesName.value = "";
      downloadSeasonNumber.value = "";
    } else if (preset === "unsorted") {
      downloadMediaKind.value = "auto";
      downloadKidsTag.value = "auto";
      downloadSeriesName.value = "";
      downloadSeasonNumber.value = "";
    }
    const isTv = downloadMediaKind.value === "tv";
    downloadSeriesName.disabled = !isTv;
    downloadSeasonNumber.disabled = !isTv;
  };

  const updateDownloadDestinationPreview = async () => {
    if (!downloadDestinationPreview) return;
    const seq = ++destinationPreviewSeq;
    const detailUrl = downloadDetailUrl?.value.trim() || "";
    if (!detailUrl && (downloadDestinationPreset?.value || "auto") === "auto") {
      downloadDestinationPreview.textContent = "Destination will be detected after you paste a URL.";
      downloadDestinationPreview.dataset.mode = "neutral";
      return;
    }
    downloadDestinationPreview.textContent = "Checking destination...";
    downloadDestinationPreview.dataset.mode = "neutral";
    const payload = {
      title: detailUrl ? detailUrl.split("/").filter(Boolean).pop() || "Manual download" : "Manual download",
      ...buildMediaRoutingPayload(),
    };
    try {
      const { ok, data } = await api.classifyMedia(payload);
      if (seq !== destinationPreviewSeq) return;
      if (!ok) {
        downloadDestinationPreview.textContent = data.error || "Destination preview failed.";
        downloadDestinationPreview.dataset.mode = "error";
        return;
      }
      const c = data.classification || {};
      const warning = data.requires_confirmation ? " Needs confirmation." : "";
      downloadDestinationPreview.textContent = `Will save to: ${data.destination_subpath || "unsorted"} (${c.media_kind || "unknown"}).${warning}`;
      downloadDestinationPreview.dataset.mode = data.requires_confirmation ? "warning" : "ok";
    } catch (_) {
      if (seq !== destinationPreviewSeq) return;
      downloadDestinationPreview.textContent = "Destination preview failed.";
      downloadDestinationPreview.dataset.mode = "error";
    }
  };

  const renderDownloadJobs = (jobs, { refreshDownloads, enqueueDownload }) => {
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
        const sourceType = job.source_type || "sdilej";
        const eta = formatEta(done, total, job.speed_bps);
        const savePath = job.save_path ? `<div><strong>Saved:</strong> <code>${esc(job.save_path)}</code></div>` : "";
        const error = job.error ? `<div class="job-error"><strong>Error:</strong> ${esc(job.error)}</div>` : "";
        const copyValue = job.save_path || job.working_path || job.detail_url || "";
        const copyLabel = job.save_path ? "Copy path" : "Copy link";
        return `
          <article class="download-job" data-job-id="${esc(job.id)}">
            <div class="job-head">
              <a href="${esc(job.detail_url)}" target="_blank" rel="noreferrer">${esc(title)}</a>
              <span class="job-source">${esc(sourceType)}</span>
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
              ${(job.status === "queued" || job.status === "running") ? `<button type="button" class="btn btn-secondary btn-sm" data-action="priority" data-id="${job.id}" data-priority="${esc(job.priority)}">Set priority</button>` : ""}
              <button type="button" class="btn btn-soft btn-sm" data-action="copy" data-id="${job.id}" data-copy-value="${esc(copyValue)}" data-copy-label="${esc(copyLabel)}">${esc(copyLabel)}</button>
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
            await api.cancelDownloadJob(jobId);
            setDownloadStatus(`Canceled job #${jobId}.`, "neutral");
          } else if (action === "cancel_complete") {
            await api.cancelDownloadJobComplete(jobId);
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
            await api.retryDownloadJob(jobId);
            setDownloadStatus(`Retried job #${jobId}.`, "ok");
          } else if (action === "top") {
            await api.moveDownloadJobToTop(jobId);
            setDownloadStatus(`Moved job #${jobId} to top.`, "ok");
          } else if (action === "remove") {
            const { ok, data } = await api.deleteDownloadJob(jobId);
            if (!ok) {
              showDownloadError(data, "Failed to remove job.");
              return;
            }
            setDownloadStatus(`Removed job #${jobId}.`, "ok");
          } else if (action === "remove_data") {
            const { ok, data } = await api.deleteDownloadJob(jobId, { withData: true });
            if (!ok) {
              showDownloadError(data, "Failed to remove job + data.");
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
              setDownloadStatus(
                {
                  message: "Priority must be a number.",
                  mode: "error",
                  details: { hint: "Enter an integer between -1000 and 1000." },
                }
              );
              return;
            }
            const { ok, data } = await api.updateDownloadJobPriority(jobId, { priority: next });
            if (!ok) {
              showDownloadError(data, "Failed to set priority.");
              return;
            }
            setDownloadStatus(`Priority updated for job #${jobId}.`, "ok");
          } else if (action === "copy") {
            const value = btn.dataset.copyValue || "";
            const copied = await copyTextToClipboard(value);
            setDownloadStatus(
              copied ? `Copied ${btn.dataset.copyLabel || "job value"} for job #${jobId}.` : `Copy failed for job #${jobId}.`,
              copied ? "ok" : "error"
            );
            if (copied) {
              const original = btn.textContent;
              btn.textContent = "Copied";
              window.setTimeout(() => {
                btn.textContent = original || btn.dataset.copyLabel || "Copy link";
              }, 1200);
            }
          }
        } catch (_) {
          setDownloadStatus({
            message: `Action failed for job #${jobId}.`,
            mode: "error",
            details: {
              hint: "Retry the action or check the queue status.",
            },
          });
        } finally {
          await refreshDownloads();
        }
      });
    });
  };

  const refreshDownloads = async ({ notifyOnFailure = false, notifyOnSuccess = false, background = false } = {}) => {
    if (background && Date.now() < nextBackgroundRefreshAt) return;
    if (refreshDownloadsInFlight) {
      refreshDownloadsQueued = true;
      refreshDownloadsQueuedOptions = {
        notifyOnFailure: Boolean(refreshDownloadsQueuedOptions?.notifyOnFailure || notifyOnFailure),
        notifyOnSuccess: Boolean(refreshDownloadsQueuedOptions?.notifyOnSuccess || notifyOnSuccess),
        background: refreshDownloadsQueuedOptions ? Boolean(refreshDownloadsQueuedOptions.background && background) : background,
      };
      return;
    }
    refreshDownloadsInFlight = true;
    let refreshPhase = "request";
    try {
      const { ok, data } = await api.listDownloads(200);
      refreshPhase = "response";
      if (!ok) {
        refreshDownloadsFailures += 1;
        nextBackgroundRefreshAt = Date.now() + Math.min(30000, 2500 * (2 ** Math.min(refreshDownloadsFailures - 1, 4)));
        if (notifyOnFailure && refreshDownloadsFailures === 1) {
          showDownloadError(data, "Queue refresh failed. Retrying in background.", {
            mode: "warning",
            hint: "The last known queue state is preserved while the app retries in the background.",
            preferFallbackMessage: true,
            context: {
              phase: refreshPhase,
              backend_error: data?.error || null,
            },
          });
          queueRefreshWarningVisible = true;
        }
        return;
      }
      const hadQueueRefreshWarning = queueRefreshWarningVisible || refreshDownloadsFailures > 0;
      refreshDownloadsFailures = 0;
      nextBackgroundRefreshAt = 0;
      lastSuccessfulRefreshAt = Date.now();
      const summary = data.summary || {};
      refreshPhase = "summary";
      downloadWorkerState.textContent = data.worker_alive ? "Worker: online" : "Worker: offline";
      downloadSummary.textContent = `Queue: ${summary.queued || 0} queued, ${summary.running || 0} running, ${summary.done || 0} done, ${summary.failed || 0} failed, ${summary.canceled || 0} canceled · Updated ${formatRefreshTime(lastSuccessfulRefreshAt)}`;
      if (hadQueueRefreshWarning) {
        queueRefreshWarningVisible = false;
        setDownloadStatus("Queue recovered. Latest refresh succeeded.", "ok");
      } else if (notifyOnSuccess) {
        setDownloadStatus("Queue updated.", "ok");
      }
      refreshPhase = "render jobs";
      renderDownloadJobs(data.items || [], { refreshDownloads, enqueueDownload });
      refreshPhase = "sync active queue state";
      setActiveQueueStateFromJobs(data.items || []);
    } catch (error) {
      refreshDownloadsFailures += 1;
      nextBackgroundRefreshAt = Date.now() + Math.min(30000, 2500 * (2 ** Math.min(refreshDownloadsFailures - 1, 4)));
      const displayFailure = refreshPhase !== "request" && refreshPhase !== "response";
      if (notifyOnFailure && refreshDownloadsFailures === 1) {
        setDownloadStatus({
          message: displayFailure ? "Queue data loaded, but display update failed." : "Queue refresh failed. Retrying in background.",
          mode: displayFailure ? "error" : "warning",
          details: {
            error_code: displayFailure ? "downloads_render_failed" : "downloads_refresh_failed",
            hint: displayFailure
              ? "The queue response was received, but a browser update failed. Copy these details for diagnosis."
              : "The last known queue state is preserved while the app retries in the background.",
            retryable: true,
            details: `phase=${refreshPhase}; ${error?.stack || error?.message || String(error || "unknown error")}`,
          },
        });
        queueRefreshWarningVisible = true;
      }
    } finally {
      refreshDownloadsInFlight = false;
      if (refreshDownloadsQueued) {
        const queuedOptions = refreshDownloadsQueuedOptions || {};
        refreshDownloadsQueued = false;
        refreshDownloadsQueuedOptions = null;
        window.setTimeout(() => {
          refreshDownloads(queuedOptions);
        }, 0);
      }
    }
  };

  const refreshDownloadSettings = async () => {
    try {
      const { ok, data } = await api.getDownloadSettings();
      if (!ok) {
        showDownloadError(data, "Failed to load download settings.");
        return;
      }
      settingsMaxConcurrent.value = data.max_concurrent_jobs ?? 1;
      settingsDefaultChunks.value = data.default_chunk_count ?? 1;
      settingsBandwidth.value = data.bandwidth_limit_kbps ?? 0;
      downloadChunkCount.value = data.default_chunk_count ?? 1;
    } catch (_) {
      setDownloadStatus({
        message: "Download settings unavailable.",
        mode: "error",
        details: {
          hint: "Retry the request or check the storage layer.",
        },
      });
    }
  };

  const updateDownloadSourceMode = () => {
    const sourceType = downloadSourceType?.value || "sdilej";
    const isYoutube = sourceType === "youtube";
    if (downloadModeLabel) {
      downloadModeLabel.classList.toggle("hidden", isYoutube);
    }
    if (downloadMode) {
      downloadMode.disabled = isYoutube;
    }
    if (downloadChunkCountLabel) {
      downloadChunkCountLabel.classList.toggle("hidden", isYoutube);
    }
    if (downloadChunkCount) {
      downloadChunkCount.disabled = isYoutube;
    }
    if (downloadDetailUrl) {
      downloadDetailUrl.placeholder = isYoutube
        ? "https://www.youtube.com/watch?v=... or VeseleRozpravky episode URL"
        : "https://sdilej.cz/123456/file-name.mkv";
    }
  };

  const enqueueDownload = async (payload) => {
    try {
      const { ok, status, data } = await api.enqueueDownload(payload);
      if (!ok) {
        if (status === 409 && data.duplicate_job) {
          const dup = data.duplicate_job;
          setDownloadStatus({
            message: `${data.error || "Duplicate download."} Existing job #${dup.id} is ${dup.status}.`,
            mode: "error",
            details: {
              error_code: data.error_code || null,
              request_id: data.request_id || null,
              hint: data.hint || "Open the existing job instead of enqueueing another one.",
              retryable: data.retryable ?? null,
              details: `duplicate_job_id=${dup.id}; duplicate_status=${dup.status}`,
            },
          });
          return {
            ok: false,
            duplicateJob: dup,
            duplicateIsActive: ACTIVE_QUEUE_STATUSES.has(String(dup.status || "")),
          };
        }
        if (status === 409 && data.requires_confirmation) {
          showDownloadError(data, "Classification confirmation is required.");
        } else {
          showDownloadError(data, "Failed to enqueue job.");
        }
        return { ok: false };
      }
      await refreshDownloads();
      setDownloadStatus(`Queued #${data.id}: ${data.title || data.detail_url}`, "ok");
      return { ok: true, job: data };
    } catch (_) {
      setDownloadStatus({
        message: "Failed to enqueue job.",
        mode: "error",
        details: {
          hint: "Retry the enqueue or check the download worker health.",
        },
      });
      return { ok: false };
    }
  };

  const refreshAccountStatus = async () => {
    try {
      const { ok, data } = await api.getAccount();
      if (!ok) {
        setAccountStatus(`Status error: ${data.error || "unknown error"}`, "error");
        return;
      }
      if (data.configured) {
        accountLogin.value = data.login || "";
        setAccountStatus(`Premium - ${data.login}`, "ok");
      } else {
        accountLogin.value = "";
        setAccountStatus("Free", "neutral");
      }
    } catch (_) {
      setAccountStatus("Status unavailable", "error");
    }
  };

  const updateYoutubeAuthModeFields = () => {
    const mode = youtubeAuthMode?.value || "none";
    const fileFields = Array.from(document.querySelectorAll(".youtube-cookies-file-field, .youtube-cookies-text-field"));
    const browserFields = Array.from(document.querySelectorAll(".youtube-cookies-browser-field"));
    fileFields.forEach((el) => el.classList.toggle("hidden", mode !== "cookies_file"));
    browserFields.forEach((el) => el.classList.toggle("hidden", mode !== "cookies_from_browser"));
  };

  const refreshYoutubeAuthStatus = async () => {
    if (!youtubeAuthStatus || !api.getYoutubeAuth) return;
    try {
      const { ok, data } = await api.getYoutubeAuth();
      if (!ok) {
        setYoutubeAuthStatus(`YouTube auth status error: ${data.error || "unknown error"}`, "error");
        return;
      }
      if (youtubeAuthMode) youtubeAuthMode.value = data.mode || "none";
      if (youtubeCookiesPath) youtubeCookiesPath.value = data.mode === "cookies_file" ? data.cookies_path || "" : "";
      if (youtubeCookiesBrowser) youtubeCookiesBrowser.value = data.mode === "cookies_from_browser" ? data.cookies_from_browser || "" : "";
      if (youtubeCookiesText) youtubeCookiesText.value = "";
      updateYoutubeAuthModeFields();
      if (data.configured && data.mode === "cookies_file") {
        setYoutubeAuthStatus(`Cookies file configured${data.managed_cookies ? " (managed)" : ""}`, "ok");
      } else if (data.configured && data.mode === "cookies_from_browser") {
        setYoutubeAuthStatus(`Browser cookies configured: ${data.cookies_from_browser} (runtime access required)`, "warning");
      } else {
        setYoutubeAuthStatus("No YouTube cookies", "neutral");
      }
    } catch (_) {
      setYoutubeAuthStatus("YouTube auth status unavailable", "error");
    }
  };

  downloadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const detailUrl = downloadDetailUrl.value.trim();
    if (!detailUrl) {
      setDownloadStatus({
        message: "Detail URL is required.",
        mode: "error",
        details: {
          hint: "Paste a valid sdilej.cz detail URL before enqueueing.",
        },
      });
      return;
    }

    const payload = {
      detail_url: detailUrl,
      source_type: downloadSourceType?.value || "sdilej",
      preferred_mode: downloadSourceType?.value === "youtube" ? "auto" : (downloadMode.value || "premium"),
      chunk_count: Number(downloadChunkCount.value || 1),
      priority: Number(downloadPriority.value || 0),
      ...buildMediaRoutingPayload(),
    };

    const result = await enqueueDownload(payload);
    if (result.ok) {
      downloadDetailUrl.value = "";
    } else if (result.duplicateJob && result.duplicateIsActive) {
      await refreshDownloads();
      focusDownloadJob(result.duplicateJob.id);
    }
  });

  youtubeQuickForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const detailUrl = youtubeQuickUrl?.value.trim() || "";
    const quickPlan = resolveYoutubeQuickPresetPlan();
    if (!detailUrl) {
      setDownloadStatus({
        message: "YouTube URL is required.",
        mode: "error",
        details: {
          hint: "Paste a YouTube video URL before enqueueing.",
        },
      });
      return;
    }
    if (!isYoutubeLikeUrl(detailUrl)) {
      setDownloadStatus({
        message: "This does not look like a YouTube URL.",
        mode: "warning",
        details: {
          hint: "Use the full download form below for non-YouTube URLs.",
        },
      });
      return;
    }
    const seriesName = youtubeQuickSeriesName?.value.trim() || "";
    const seasonNumber = Number(youtubeQuickSeasonNumber?.value || 0);
    if (quickPlan.needsTvFields && !seriesName) {
      setDownloadStatus({
        message: "TV show is required for this destination.",
        mode: "error",
        details: {
          hint: "Pick an existing local show or type a new one before enqueueing.",
        },
      });
      return;
    }
    if (quickPlan.needsTvFields && (!Number.isFinite(seasonNumber) || seasonNumber < 1)) {
      setDownloadStatus({
        message: "Season number is required for this destination.",
        mode: "error",
        details: {
          hint: "Enter a season number greater than 0 before enqueueing.",
        },
      });
      return;
    }
    if (youtubeQuickPlaylist?.checked && quickPlan.needsTvFields) {
      setDownloadStatus({
        message: "Full playlists cannot use TV episode routing.",
        mode: "warning",
        details: { hint: "Choose Music, Movies, or Unsorted for a playlist download." },
      });
      return;
    }

    if (youtubeQuickSubmit) {
      youtubeQuickSubmit.disabled = true;
    }
    try {
      const result = await enqueueDownload({
        detail_url: detailUrl,
        title: "YouTube video",
        source_type: "youtube",
        source_metadata: {
          provider: "youtube_direct",
          prefer_metadata_title: true,
          download_playlist: Boolean(youtubeQuickPlaylist?.checked),
        },
        preferred_mode: "auto",
        destination_preset: quickPlan.destination_preset,
        media_kind: quickPlan.media_kind,
        is_kids: quickPlan.is_kids,
        series_name: quickPlan.needsTvFields ? seriesName : null,
        season_number: quickPlan.needsTvFields ? seasonNumber : null,
        chunk_count: 1,
        priority: 0,
      });
      if (result.ok && youtubeQuickUrl) {
        youtubeQuickUrl.value = "";
        if (youtubeQuickPlaylist) youtubeQuickPlaylist.checked = false;
        if (youtubeQuickSeriesName) youtubeQuickSeriesName.value = "";
        if (youtubeQuickSeasonNumber) youtubeQuickSeasonNumber.value = "";
      } else if (result.duplicateJob && result.duplicateIsActive) {
        await refreshDownloads();
        focusDownloadJob(result.duplicateJob.id);
      }
    } finally {
      if (youtubeQuickSubmit) {
        youtubeQuickSubmit.disabled = false;
      }
    }
  });

  downloadDetailUrl?.addEventListener("input", () => {
    if (!downloadSourceType || !isYoutubeLikeUrl(downloadDetailUrl.value)) return;
    if (downloadSourceType.value !== "youtube") {
      downloadSourceType.value = "youtube";
      updateDownloadSourceMode();
    }
  });

  downloadDestinationPreset?.addEventListener("change", async () => {
    applyDestinationPresetToDownloadFields();
    await updateDownloadDestinationPreview();
  });
  [downloadMediaKind, downloadKidsTag].forEach((el) => {
    el?.addEventListener("change", async () => {
      if (downloadDestinationPreset) {
        downloadDestinationPreset.value = "auto";
      }
      applyDestinationPresetToDownloadFields();
      await updateDownloadDestinationPreview();
    });
  });
  [downloadDetailUrl, downloadSeriesName, downloadSeasonNumber].forEach((el) => {
    el?.addEventListener("input", () => {
      window.setTimeout(updateDownloadDestinationPreview, 0);
    });
  });
  youtubeQuickDestinationPreset?.addEventListener("change", () => {
    updateYoutubeQuickPresetFields();
  });
  youtubeQuickSeriesName?.addEventListener("focus", () => {
    refreshYoutubeQuickSeriesSuggestions();
  });
  youtubeQuickSeriesName?.addEventListener("input", () => {
    refreshYoutubeQuickSeriesSuggestions();
  });

  downloadSourceType?.addEventListener("change", updateDownloadSourceMode);
  updateDownloadSourceMode();
  applyDestinationPresetToDownloadFields();
  updateDownloadDestinationPreview();
  updateYoutubeQuickPresetFields();

  refreshDownloadsBtn.addEventListener("click", async () => {
    setDownloadStatus("Refreshing queue...", "neutral");
    await refreshDownloads({ notifyOnFailure: true, notifyOnSuccess: true, background: false });
  });

  clearFinishedBtn.addEventListener("click", async () => {
    setDownloadStatus("Clearing finished jobs...", "neutral");
    try {
      const { ok, data } = await api.clearDownloads({ statuses: ["done", "failed", "canceled"] });
      if (!ok) {
        showDownloadError(data, "Failed to clear jobs.");
        return;
      }
      setDownloadStatus(`Cleared ${data.deleted} finished jobs.`, "ok");
      await refreshDownloads();
    } catch (_) {
      setDownloadStatus({
        message: "Failed to clear finished jobs.",
        mode: "error",
        details: {
          hint: "Retry the action or check the storage layer.",
        },
      });
    }
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
      const { ok, data } = await api.updateDownloadSettings(payload);
      if (!ok) {
        showDownloadError(data, "Failed to save download settings.");
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
      setDownloadStatus({
        message: "Failed to save download settings.",
        mode: "error",
        details: {
          hint: "Retry the save or check the storage layer.",
        },
      });
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
      const { ok, data } = await api.setAccount({
        login,
        password,
        verify: accountVerify.checked,
      });
      if (!ok) {
        setAccountStatus({
          message: data.error || "Failed to save credentials.",
          mode: "error",
          details: {
            error_code: data.error_code || null,
            request_id: data.request_id || null,
            hint: data.hint || null,
            retryable: data.retryable ?? null,
            details: data.details || null,
          },
        });
        return;
      }
      accountPassword.value = "";
      setAccountStatus(data.verified === false ? `Saved (not verified): ${data.login}` : `Saved for: ${data.login}`, "ok");
      await refreshAccountStatus();
    } catch (_) {
      setAccountStatus({
        message: "Failed to save credentials.",
        mode: "error",
        details: {
          hint: "Retry the save or check the account service.",
        },
      });
    }
  });

  accountClearBtn.addEventListener("click", async () => {
    setAccountStatus("Clearing credentials...", "neutral");
    try {
      const { ok, data } = await api.deleteAccount();
      if (!ok || !data.cleared) {
        setAccountStatus({
          message: data.error || "Failed to clear credentials.",
          mode: "error",
          details: {
            error_code: data.error_code || null,
            request_id: data.request_id || null,
            hint: data.hint || null,
            retryable: data.retryable ?? null,
            details: data.details || null,
          },
        });
        return;
      }
      accountPassword.value = "";
      await refreshAccountStatus();
    } catch (_) {
      setAccountStatus({
        message: "Failed to clear credentials.",
        mode: "error",
        details: {
          hint: "Retry the action or check the account service.",
        },
      });
    }
  });

  youtubeAuthMode?.addEventListener("change", updateYoutubeAuthModeFields);

  youtubeAuthTestBtn?.addEventListener("click", async () => {
    const detailUrl = youtubeAuthTestUrl?.value.trim() || "";
    if (!isYoutubeLikeUrl(detailUrl)) {
      setYoutubeAuthStatus({ message: "Enter a valid YouTube video URL.", mode: "warning", details: { hint: "Use a youtube.com or youtu.be video link." } });
      return;
    }
    setYoutubeAuthStatus("Testing YouTube access...", "neutral");
    const { ok, data } = await api.testYoutubeAuth({ detail_url: detailUrl });
    if (!ok) {
      setYoutubeAuthStatus(buildStatusErrorState(data, "YouTube access test failed."));
      return;
    }
    setYoutubeAuthStatus(`YouTube access works${data.title ? `: ${data.title}` : "."}`, "ok");
  });

  youtubeAuthForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const selectedMode = youtubeAuthMode?.value || "none";
    if (selectedMode === "none") {
      setYoutubeAuthStatus(
        "Choose Cookies file / pasted cookies or Browser cookies before saving. Use Clear YouTube auth to remove saved cookies.",
        "warning"
      );
      return;
    }
    const payload = {
      mode: selectedMode,
      cookies_path: youtubeCookiesPath?.value.trim() || null,
      cookies_text: youtubeCookiesText?.value.trim() || null,
      cookies_from_browser: youtubeCookiesBrowser?.value.trim() || null,
    };
    setYoutubeAuthStatus("Saving YouTube auth...", "neutral");
    try {
      const { ok, data } = await api.setYoutubeAuth(payload);
      if (!ok) {
        setYoutubeAuthStatus({
          message: data.error || "Failed to save YouTube auth.",
          mode: "error",
          details: {
            error_code: data.error_code || null,
            request_id: data.request_id || null,
            hint: data.hint || null,
            retryable: data.retryable ?? null,
            details: data.details || null,
          },
        });
        return;
      }
      if (youtubeCookiesText) youtubeCookiesText.value = "";
      await refreshYoutubeAuthStatus();
    } catch (_) {
      setYoutubeAuthStatus({
        message: "Failed to save YouTube auth.",
        mode: "error",
        details: {
          hint: "Retry the save or check the local cookies file path.",
        },
      });
    }
  });

  youtubeAuthClearBtn?.addEventListener("click", async () => {
    setYoutubeAuthStatus("Clearing YouTube auth...", "neutral");
    try {
      const { ok, data } = await api.deleteYoutubeAuth();
      if (!ok || !data.cleared) {
        setYoutubeAuthStatus({
          message: data.error || "Failed to clear YouTube auth.",
          mode: "error",
          details: {
            error_code: data.error_code || null,
            request_id: data.request_id || null,
            hint: data.hint || null,
            retryable: data.retryable ?? null,
            details: data.details || null,
          },
        });
        return;
      }
      await refreshYoutubeAuthStatus();
    } catch (_) {
      setYoutubeAuthStatus({
        message: "Failed to clear YouTube auth.",
        mode: "error",
        details: {
          hint: "Retry the action or check the storage layer.",
        },
      });
    }
  });

  updateYoutubeAuthModeFields();

  return {
    refreshDownloads,
    refreshDownloadSettings,
    refreshAccountStatus,
    refreshYoutubeAuthStatus,
    enqueueDownload,
    setAccountStatus,
  };
};
