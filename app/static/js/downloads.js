import { esc } from "./dom-utils.js";
import { formatBytes, formatEta, formatSpeed } from "./formatters.js";
import { ACTIVE_QUEUE_STATUSES } from "./keys.js";
import { buildStatusErrorState } from "./status-ui.js";

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
  } = elements;

  const setAccountStatus = (value, mode = "neutral") => {
    if (!accountStatus) return;
    const text = typeof value === "object" && value !== null ? value.message || value.text || value.error || "" : value;
    const nextMode = typeof value === "object" && value !== null ? value.mode || mode : mode;
    accountStatus.textContent = text || "";
    accountStatus.dataset.mode = nextMode;
  };

  let refreshDownloadsInFlight = false;
  let refreshDownloadsQueued = false;
  let refreshDownloadsFailures = 0;
  let destinationPreviewSeq = 0;

  const isYoutubeLikeUrl = (value) => {
    const text = String(value || "").trim().toLowerCase();
    return /(^https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\//.test(text);
  };

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

  const refreshDownloads = async ({ notifyOnFailure = false } = {}) => {
    if (refreshDownloadsInFlight) {
      refreshDownloadsQueued = true;
      return;
    }
    refreshDownloadsInFlight = true;
    try {
      const { ok, data } = await api.listDownloads(200);
      if (!ok) {
        refreshDownloadsFailures += 1;
        if (notifyOnFailure && refreshDownloadsFailures === 1) {
          showDownloadError(data, "Queue refresh failed. Retrying in background.", {
            mode: "warning",
            hint: "The last known queue state is preserved while the app retries in the background.",
          });
        }
        return;
      }
      refreshDownloadsFailures = 0;
      const summary = data.summary || {};
      downloadWorkerState.textContent = data.worker_alive ? "Worker: online" : "Worker: offline";
      downloadSummary.textContent = `Queue: ${summary.queued || 0} queued, ${summary.running || 0} running, ${summary.done || 0} done, ${summary.failed || 0} failed, ${summary.canceled || 0} canceled`;
      renderDownloadJobs(data.items || [], { refreshDownloads, enqueueDownload });
      setActiveQueueStateFromJobs(data.items || []);
    } catch (_) {
      refreshDownloadsFailures += 1;
      if (notifyOnFailure && refreshDownloadsFailures === 1) {
        setDownloadStatus({
          message: "Queue refresh failed. Retrying in background.",
          mode: "warning",
          details: {
            hint: "The last known queue state is preserved while the app retries in the background.",
          },
        });
      }
    } finally {
      refreshDownloadsInFlight = false;
      if (refreshDownloadsQueued) {
        refreshDownloadsQueued = false;
        window.setTimeout(() => {
          refreshDownloads();
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
        },
        preferred_mode: "auto",
        media_kind: "movie",
        is_kids: false,
        chunk_count: 1,
        priority: 0,
      });
      if (result.ok && youtubeQuickUrl) {
        youtubeQuickUrl.value = "";
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

  downloadSourceType?.addEventListener("change", updateDownloadSourceMode);
  updateDownloadSourceMode();
  applyDestinationPresetToDownloadFields();
  updateDownloadDestinationPreview();

  refreshDownloadsBtn.addEventListener("click", async () => {
    setDownloadStatus("Refreshing queue...", "neutral");
    await refreshDownloads({ notifyOnFailure: true });
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

  return {
    refreshDownloads,
    refreshDownloadSettings,
    refreshAccountStatus,
    enqueueDownload,
    setAccountStatus,
  };
};
