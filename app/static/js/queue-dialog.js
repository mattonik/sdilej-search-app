export const initQueueDialog = ({
  elements,
  api,
  setDownloadStatus,
  refreshDownloads,
  enqueueDownload,
  focusDownloadJob,
}) => {
  const {
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
  } = elements;

  let queueDialogState = null;

  const resolveKidsValue = (rawValue) => {
    if (rawValue === "yes") return true;
    if (rawValue === "no") return false;
    return null;
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
      const { ok, data } = await api.classifyMedia(payload);
      if (!ok) {
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

  const closeQueueDialog = () => {
    queueDialogBackdrop.classList.add("hidden");
    queueDialogState = null;
    queueDialogPreview.textContent = "";
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
      const { ok, data } = await api.updateDownloadClassification(queueDialogState.jobId, mediaPayload);
      if (!ok) {
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

  return { openQueueDialog, closeQueueDialog };
};
