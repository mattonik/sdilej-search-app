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
  } = elements;

  if (!libraryTvMissingForm || !libraryTvMissingResults) {
    return {};
  }

  const status = createStatusController(libraryStatus);
  let lastReport = null;

  const renderEmpty = (message) => {
    libraryTvMissingResults.innerHTML = `<div class="download-empty">${esc(message)}</div>`;
  };

  const renderReport = (report) => {
    lastReport = report;
    const show = report.show || {};
    const context = report.local_context || {};
    const summary = report.summary || {};
    const seasons = Array.isArray(report.seasons) ? report.seasons : [];
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

  libraryTvMissingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const showName = libraryTvShowName?.value.trim() || "";
    if (!showName) {
      status.setStatus({
        message: "TV show name is required.",
        mode: "error",
        details: { hint: "Enter a show name before scanning the local library." },
      });
      return;
    }
    status.setStatus("Scanning local TV library...", "neutral");
    renderEmpty("Scanning...");
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
  });

  return {
    renderReport,
    getLastReport: () => lastReport,
  };
};
