import { esc } from "./dom-utils.js";
import { buildStatusErrorState, createStatusController } from "./status-ui.js";

export const initLibraryManagement = ({
  elements,
  api,
  setWorkspaceTab,
  getTvApi,
}) => {
  const {
    libraryTvMissingForm,
    libraryTvShowName,
    libraryStatus,
    libraryTvMissingResults,
    libraryFolderKind,
    libraryFoldersScanBtn,
    libraryFolderResults,
    libraryDeepScanResults,
    libraryMusicFoldersScanBtn,
    libraryMusicFolderResults,
    libraryMusicDeepScanResults,
  } = elements;

  if (!libraryTvMissingForm || !libraryTvMissingResults) {
    return {};
  }

  const status = createStatusController(libraryStatus);
  let lastReport = null;
  let scanInFlight = false;

  const submitButton = libraryTvMissingForm.querySelector('button[type="submit"]');

  const selectedFolderIsKids = () => libraryFolderKind?.value === "kids";

  const renderFolderResults = (items) => {
    if (!libraryFolderResults) return;
    if (!Array.isArray(items) || !items.length) {
      libraryFolderResults.innerHTML = `<div class="download-empty">No TV folders found in this library root.</div>`;
      return;
    }
    libraryFolderResults.innerHTML = items.map((item) => `
      <article class="library-folder-card" data-folder-name="${esc(item.folder_name || "")}">
        <div>
          <strong>${esc(item.folder_name || "Unnamed folder")}</strong>
          <span>${esc(item.season_count || 0)} season folders</span>
        </div>
        <button type="button" class="btn btn-secondary btn-sm library-deep-scan" data-folder-name="${esc(item.folder_name || "")}">
          Deep scan
        </button>
      </article>
    `).join("");
    libraryFolderResults.querySelectorAll(".library-deep-scan").forEach((button) => {
      button.addEventListener("click", () => deepScanFolder(button.dataset.folderName || ""));
    });
  };

  const deepScanFolder = async (folderName) => {
    if (!folderName || !libraryDeepScanResults) return;
    status.setStatus(`Deep scanning ${folderName}...`, "neutral");
    libraryDeepScanResults.innerHTML = `<div class="download-empty">Deep scanning...</div>`;
    const { ok, data } = await api.deepScanLibraryTvFolder({ folderName, isKids: selectedFolderIsKids() });
    if (!ok) {
      status.setStatus(buildStatusErrorState(data, "TV folder deep scan failed.", {
        hint: "Check the selected folder and media permissions.",
      }));
      libraryDeepScanResults.innerHTML = `<div class="download-empty">${esc(data?.error || "TV folder deep scan failed.")}</div>`;
      return;
    }
    const episodes = Array.isArray(data.episodes) ? data.episodes : [];
    libraryDeepScanResults.innerHTML = `
      <div class="library-deep-scan-card">
        <div class="library-summary-stats">
          <strong>${esc(data.folder_name || folderName)}</strong>
          <span>${esc(data.media_file_count || 0)} media files</span>
          <span>${esc(data.episode_count || 0)} episode codes</span>
        </div>
        ${episodes.length
          ? `<div class="library-episode-codes">${episodes.map((episode) => `<span>${esc(episode.episode_code)}</span>`).join("")}</div>`
          : `<p class="library-deep-scan-empty">No SxxEyy episode codes were detected.</p>`}
        <button type="button" class="btn btn-primary btn-sm library-search-folder" data-folder-name="${esc(data.folder_name || folderName)}">
          Find missing episodes for this folder
        </button>
      </div>
    `;
    libraryDeepScanResults.querySelector(".library-search-folder")?.addEventListener("click", (event) => {
      libraryTvShowName.value = event.currentTarget.dataset.folderName || folderName;
      libraryTvMissingForm.requestSubmit();
    });
    status.setStatus(`Deep scan complete: ${data.media_file_count || 0} media files, ${data.episode_count || 0} episode codes.`, "ok");
  };

  const scanFolders = async () => {
    if (!libraryFoldersScanBtn) return;
    libraryFoldersScanBtn.disabled = true;
    libraryFoldersScanBtn.textContent = "Scanning...";
    const { ok, data } = await api.listLibraryTvFolders({ isKids: selectedFolderIsKids() });
    libraryFoldersScanBtn.disabled = false;
    libraryFoldersScanBtn.textContent = "Scan folders";
    if (!ok) {
      status.setStatus(buildStatusErrorState(data, "TV folder scan failed.", {
        hint: "Check the configured TV library folders.",
      }));
      renderFolderResults([]);
      return;
    }
    renderFolderResults(data.items || []);
    status.setStatus(`Found ${(data.items || []).length} TV folders.`, "ok");
  };

  const formatMusicBytes = (value) => {
    const bytes = Number(value || 0);
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
  };

  const openMusicSearch = (query) => {
    const params = new URLSearchParams({ query: String(query || "").trim(), category: "audio" });
    window.location.href = `/?${params.toString()}#search`;
  };

  const deepScanMusicFolder = async (artistName, albumName = null) => {
    if (!artistName || !libraryMusicDeepScanResults) return;
    const label = albumName ? `${artistName} / ${albumName}` : artistName;
    status.setStatus(`Deep scanning ${label}...`, "neutral");
    libraryMusicDeepScanResults.innerHTML = `<div class="download-empty">Deep scanning...</div>`;
    const { ok, data } = await api.deepScanLibraryMusicFolder({ artistName, albumName });
    if (!ok) {
      status.setStatus(buildStatusErrorState(data, "Music folder deep scan failed.", {
        hint: "Check the selected artist or album folder.",
      }));
      libraryMusicDeepScanResults.innerHTML = `<div class="download-empty">${esc(data?.error || "Music folder deep scan failed.")}</div>`;
      return;
    }
    const files = Array.isArray(data.files) ? data.files : [];
    libraryMusicDeepScanResults.innerHTML = `
      <div class="library-deep-scan-card">
        <div class="library-summary-stats">
          <strong>${esc(label)}</strong>
          <span>${esc(data.audio_file_count || 0)} audio files</span>
          <span>${esc(formatMusicBytes(data.total_size_bytes))}</span>
        </div>
        ${files.length ? `<div class="library-music-file-list">${files.slice(0, 12).map((file) => `<span>${esc(file.name)}</span>`).join("")}</div>` : `<p class="library-deep-scan-empty">No supported audio files found.</p>`}
        <button type="button" class="btn btn-primary btn-sm library-search-music" data-search-query="${esc(data.search_query || label)}">Search this ${albumName ? "album" : "artist"}</button>
      </div>
    `;
    libraryMusicDeepScanResults.querySelector(".library-search-music")?.addEventListener("click", (event) => {
      openMusicSearch(event.currentTarget.dataset.searchQuery || label);
    });
    status.setStatus(`Deep scan complete: ${data.audio_file_count || 0} audio files, ${formatMusicBytes(data.total_size_bytes)}.`, "ok");
  };

  const renderMusicFolders = (items) => {
    if (!libraryMusicFolderResults) return;
    if (!Array.isArray(items) || !items.length) {
      libraryMusicFolderResults.innerHTML = `<div class="download-empty">No artist folders found in the music library.</div>`;
      return;
    }
    libraryMusicFolderResults.innerHTML = items.map((artist) => {
      const albums = Array.isArray(artist.albums) ? artist.albums : [];
      return `
        <article class="library-folder-card library-music-artist" data-artist-name="${esc(artist.artist_name || "")}">
          <div>
            <strong>${esc(artist.artist_name || "Unnamed artist")}</strong>
            <span>${esc(artist.album_count || 0)} albums · ${esc(artist.direct_audio_file_count || 0)} direct audio files</span>
            ${albums.length ? `<div class="library-music-albums">${albums.map((album) => `<button type="button" class="btn btn-soft btn-sm library-music-album" data-artist-name="${esc(artist.artist_name || "")}" data-album-name="${esc(album.album_name || "")}">${esc(album.album_name)} · ${esc(album.audio_file_count || 0)} files</button>`).join("")}</div>` : ""}
          </div>
          <button type="button" class="btn btn-secondary btn-sm library-music-artist-scan" data-artist-name="${esc(artist.artist_name || "")}">Deep scan artist</button>
        </article>
      `;
    }).join("");
    libraryMusicFolderResults.querySelectorAll(".library-music-artist-scan").forEach((button) => {
      button.addEventListener("click", () => deepScanMusicFolder(button.dataset.artistName || ""));
    });
    libraryMusicFolderResults.querySelectorAll(".library-music-album").forEach((button) => {
      button.addEventListener("click", () => deepScanMusicFolder(button.dataset.artistName || "", button.dataset.albumName || ""));
    });
  };

  const scanMusicFolders = async () => {
    if (!libraryMusicFoldersScanBtn) return;
    libraryMusicFoldersScanBtn.disabled = true;
    libraryMusicFoldersScanBtn.textContent = "Scanning...";
    const { ok, data } = await api.listLibraryMusicFolders();
    libraryMusicFoldersScanBtn.disabled = false;
    libraryMusicFoldersScanBtn.textContent = "Scan music library";
    if (!ok) {
      status.setStatus(buildStatusErrorState(data, "Music library scan failed.", {
        hint: "Check the configured music library folder.",
      }));
      renderMusicFolders([]);
      return;
    }
    renderMusicFolders(data.items || []);
    status.setStatus(`Found ${(data.items || []).length} artist folders.`, "ok");
  };

  const setScanning = (scanning) => {
    scanInFlight = Boolean(scanning);
    if (submitButton) {
      submitButton.disabled = scanInFlight;
      submitButton.textContent = scanInFlight ? "Scanning..." : "Scan missing episodes";
    }
  };

  const renderEmpty = (message) => {
    libraryTvMissingResults.innerHTML = `<div class="download-empty">${esc(message)}</div>`;
  };

  const renderReport = (report) => {
    lastReport = report;
    const show = report.show || {};
    const context = report.local_context || {};
    const summary = report.summary || {};
    const seasons = Array.isArray(report.seasons) ? report.seasons : [];
    if (!seasons.length) {
      renderEmpty("No TV seasons were returned for this show.");
      return;
    }
    libraryTvMissingResults.innerHTML = `
      <div class="library-summary-card">
        <div>
          <strong>${esc(show.name || libraryTvShowName?.value || "TV show")}</strong>
          <span>${esc(context.series_dir || "No local folder resolved")}</span>
        </div>
        <div class="library-summary-stats">
          <span>${esc(summary.downloaded_episodes || 0)} downloaded</span>
          <span>${esc(summary.missing_episodes || 0)} missing</span>
          <span>${esc(summary.total_episodes || 0)} total</span>
        </div>
      </div>
      <div class="library-season-list">
        ${seasons.map((season) => `
          <details class="library-season" ${Number(season.missing_episodes || 0) > 0 ? "open" : ""}>
            <summary>
              <strong>Season ${esc(season.season_number)}</strong>
              <span>${esc(season.downloaded_episodes || 0)} downloaded · ${esc(season.missing_episodes || 0)} missing</span>
            </summary>
            <div class="library-episode-list">
              ${(season.episodes || []).map((episode) => `
                <article class="library-episode" data-status="${esc(episode.status || "missing")}">
                  <div>
                    <strong>${esc(episode.episode_code || `S${String(episode.season_number || "").padStart(2, "0")}E${String(episode.episode_number || "").padStart(2, "0")}`)}</strong>
                    <span>${esc(episode.episode_name || "Untitled episode")}</span>
                    ${episode.airdate ? `<small>${esc(episode.airdate)}</small>` : ""}
                  </div>
                  <div class="library-episode-state">
                    <span class="library-badge" data-status="${esc(episode.status || "missing")}">${esc(episode.status === "downloaded" ? "Downloaded" : "Missing")}</span>
                    ${
                      episode.status === "downloaded"
                        ? `<small>${esc((episode.downloaded_files || [])[0] || "Local media file found")}</small>`
                        : `<button type="button" class="btn btn-secondary btn-sm library-search-missing" data-show-name="${esc(show.name || libraryTvShowName?.value || "")}" data-season-number="${esc(episode.season_number)}" data-episode-number="${esc(episode.episode_number)}">Search missing</button>`
                    }
                  </div>
                </article>
              `).join("")}
            </div>
          </details>
        `).join("")}
      </div>
    `;

    libraryTvMissingResults.querySelectorAll(".library-search-missing").forEach((btn) => {
      btn.addEventListener("click", async () => {
        setWorkspaceTab?.("search");
        const tvApi = getTvApi?.();
        if (!tvApi?.prepareTvSearchForEpisode) {
          status.setStatus("TV search is not ready.", "error");
          return;
        }
        status.setStatus("Opening TV search for the missing episode...", "neutral");
        const ok = await tvApi.prepareTvSearchForEpisode({
          showName: btn.dataset.showName,
          seasonNumber: Number(btn.dataset.seasonNumber || 0),
          episodeNumber: Number(btn.dataset.episodeNumber || 0),
        });
        status.setStatus(ok ? "TV search is ready with the missing episode selected." : "TV search opened. Select the missing episode manually.", ok ? "ok" : "warning");
      });
    });
  };

  const scanMissingShow = async (showName) => {
    if (scanInFlight) return;
    if (!showName) {
      status.setStatus({
        message: "TV show name is required.",
        mode: "error",
        details: { hint: "Enter a show name before scanning the local library." },
      });
      return;
    }
    setScanning(true);
    status.setStatus("Scanning local TV library...", "neutral");
    renderEmpty("Scanning...");
    try {
      const { ok, data } = await api.scanMissingTv({ show_name: showName });
      if (!ok) {
        status.setStatus(buildStatusErrorState(data, "TV library scan failed.", {
          hint: "Check the show name and configured media folders.",
        }));
        renderEmpty(data?.error || "TV library scan failed.");
        return;
      }
      renderReport(data);
      const summary = data.summary || {};
      status.setStatus(`Scan complete: ${summary.downloaded_episodes || 0} downloaded, ${summary.missing_episodes || 0} missing.`, "ok");
    } finally {
      setScanning(false);
    }
  };

  libraryFoldersScanBtn?.addEventListener("click", scanFolders);
  libraryMusicFoldersScanBtn?.addEventListener("click", scanMusicFolders);
  libraryTvMissingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await scanMissingShow(libraryTvShowName?.value.trim() || "");
  });

  return {
    renderReport,
    getLastReport: () => lastReport,
  };
};
