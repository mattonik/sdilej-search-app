      const savedStatus = document.getElementById("savedStatus");
      const savedChunkCount = document.getElementById("savedChunkCount");
      const savedPriority = document.getElementById("savedPriority");
      const resolveKidsValue = (rawValue) => {
        if (rawValue === "yes") return true;
        if (rawValue === "no") return false;
        return null;
      };

      const setSavedStatus = (text, mode = "neutral") => {
        savedStatus.textContent = text;
        savedStatus.dataset.mode = mode;
      };

      const loadDefaults = async () => {
        try {
          const res = await fetch("/api/downloads/settings");
          const data = await res.json();
          if (!res.ok) return;
          savedChunkCount.value = data.default_chunk_count ?? 1;
        } catch (_) {
          // Keep built-in defaults.
        }
      };

      document.querySelectorAll(".saved-download-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const fileId = Number(btn.dataset.fileId);
          const detailUrl = btn.dataset.detailUrl;
          const title = btn.dataset.title;
          const removeOnComplete = btn.dataset.removeOnComplete === "1";
          const card = btn.closest(".saved-card");
          const mediaKindEl = card?.querySelector(".saved-media-kind");
          const kidsTagEl = card?.querySelector(".saved-kids-tag");
          const seriesNameEl = card?.querySelector(".saved-series-name");
          const seasonNumberEl = card?.querySelector(".saved-season-number");

          const mediaKind = mediaKindEl && mediaKindEl.value !== "auto" ? mediaKindEl.value : null;
          const isKids = kidsTagEl ? resolveKidsValue(kidsTagEl.value) : null;
          const seriesName = seriesNameEl ? (seriesNameEl.value.trim() || null) : null;
          const seasonRaw = seasonNumberEl ? Number(seasonNumberEl.value || 0) : 0;
          const seasonNumber = Number.isFinite(seasonRaw) && seasonRaw > 0 ? seasonRaw : null;

          const payload = {
            detail_url: detailUrl,
            title,
            file_id: fileId,
            preferred_mode: "premium",
            chunk_count: Number(savedChunkCount.value || 1),
            priority: Number(savedPriority.value || 0),
            media_kind: mediaKind,
            is_kids: isKids,
            series_name: mediaKind === "tv" ? seriesName : null,
            season_number: mediaKind === "tv" ? seasonNumber : null,
            source_saved_file_id: fileId,
            delete_saved_on_complete: removeOnComplete,
          };

          try {
            const res = await fetch("/api/downloads", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) {
              if (res.status === 409 && data.duplicate_job) {
                setSavedStatus(
                  `${data.error || "Duplicate download."} Existing job #${data.duplicate_job.id} is ${data.duplicate_job.status}.`,
                  "error"
                );
              } else if (res.status === 409 && data.requires_confirmation) {
                const classification = data.classification || {};
                const kindInput = window.prompt(
                  "Classify content (movie/tv):",
                  classification.media_kind === "tv" ? "tv" : "movie"
                );
                if (kindInput == null) {
                  setSavedStatus("Queue canceled. Classification confirmation required.", "neutral");
                  return;
                }
                const kindValue = kindInput.trim().toLowerCase();
                const mediaKindRetry = kindValue.startsWith("t") ? "tv" : "movie";
                const kidsInput = window.prompt(
                  "Kids content? (yes/no):",
                  classification.is_kids ? "yes" : "no"
                );
                const isKidsRetry = typeof kidsInput === "string" && kidsInput.trim().toLowerCase().startsWith("y");

                const retryPayload = {
                  ...payload,
                  media_kind: mediaKindRetry,
                  is_kids: isKidsRetry,
                  series_name: null,
                  season_number: null,
                };
                if (mediaKindRetry === "tv") {
                  const seriesInput = window.prompt("Series name:", classification.series_name || title || "");
                  if (seriesInput == null || !seriesInput.trim()) {
                    setSavedStatus("Queue canceled. Series name is required for TV routing.", "error");
                    return;
                  }
                  const seasonInput = window.prompt("Season number:", String(classification.season_number || 1));
                  const seasonRetry = Number(seasonInput);
                  if (!Number.isFinite(seasonRetry) || seasonRetry < 1) {
                    setSavedStatus("Queue canceled. Invalid season number.", "error");
                    return;
                  }
                  retryPayload.series_name = seriesInput.trim();
                  retryPayload.season_number = seasonRetry;
                }
                const retryRes = await fetch("/api/downloads", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(retryPayload),
                });
                const retryData = await retryRes.json();
                if (!retryRes.ok) {
                  setSavedStatus(retryData.error || "Failed to queue download.", "error");
                  return;
                }
                setSavedStatus(
                  removeOnComplete
                    ? `Queued #${retryData.id}. Saved pick will be removed after download completes.`
                    : `Queued #${retryData.id}.`,
                  "ok"
                );
              } else {
                setSavedStatus(data.error || "Failed to queue download.", "error");
              }
              return;
            }
            setSavedStatus(
              removeOnComplete
                ? `Queued #${data.id}. Saved pick will be removed after download completes.`
                : `Queued #${data.id}.`,
              "ok"
            );
          } catch (_) {
            setSavedStatus("Failed to queue download.", "error");
          }
        });
      });

      document.querySelectorAll(".saved-delete-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const fileId = Number(btn.dataset.fileId);
          try {
            const res = await fetch(`/api/saved/${fileId}`, { method: "DELETE" });
            const data = await res.json();
            if (!res.ok) {
              setSavedStatus(data.error || "Failed to delete saved pick.", "error");
              return;
            }
            setSavedStatus(`Deleted saved pick #${fileId}.`, "ok");
            btn.closest(".saved-card")?.remove();
          } catch (_) {
            setSavedStatus("Failed to delete saved pick.", "error");
          }
        });
      });

      loadDefaults();
