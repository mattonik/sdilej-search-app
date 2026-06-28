import { esc } from "./dom-utils.js";
import { buildStatusErrorState } from "./status-ui.js";

export const initKidsCatalog = ({
  elements,
  api,
  enqueueDownload,
  refreshDownloads,
  focusDownloadJob,
}) => {
  const {
    kidsCatalogLoadBtn,
    kidsCatalogFilter,
    kidsCatalogStatus,
    kidsCatalogShows,
    kidsCatalogEpisodes,
  } = elements;

  if (!kidsCatalogLoadBtn || !kidsCatalogShows || !kidsCatalogEpisodes) {
    return {};
  }

  let shows = [];
  let selectedShow = null;

  const setStatus = (value, mode = "neutral") => {
    if (!kidsCatalogStatus) return;
    if (typeof value === "object" && value !== null) {
      kidsCatalogStatus.textContent = value.message || value.error || "";
      kidsCatalogStatus.dataset.mode = value.mode || mode;
      return;
    }
    kidsCatalogStatus.textContent = value || "";
    kidsCatalogStatus.dataset.mode = mode;
  };

  const filteredShows = () => {
    const query = String(kidsCatalogFilter?.value || "").trim().toLowerCase();
    if (!query) return shows;
    return shows.filter((show) => String(show.title || "").toLowerCase().includes(query));
  };

  const renderShows = () => {
    const items = filteredShows();
    if (!items.length) {
      kidsCatalogShows.innerHTML = `<div class="download-empty">No catalog shows match the filter.</div>`;
      return;
    }
    kidsCatalogShows.innerHTML = items
      .map(
        (show) => `
          <button type="button" class="kids-catalog-show btn btn-soft" data-slug="${esc(show.slug)}">
            <span>${esc(show.title)}</span>
            ${show.episode_count ? `<small>${esc(show.episode_count)} episodes</small>` : ""}
          </button>
        `
      )
      .join("");
    kidsCatalogShows.querySelectorAll(".kids-catalog-show").forEach((btn) => {
      btn.addEventListener("click", () => loadShow(btn.dataset.slug || ""));
    });
  };

  const renderEpisodes = (show) => {
    selectedShow = show;
    const episodes = Array.isArray(show?.episodes) ? show.episodes : [];
    if (!episodes.length) {
      kidsCatalogEpisodes.innerHTML = `<div class="download-empty">No episodes were found for this show.</div>`;
      return;
    }
    kidsCatalogEpisodes.innerHTML = `
      <div class="kids-catalog-episode-head">
        <strong>${esc(show.title || "Kids show")}</strong>
        <span>${esc(episodes.length)} episodes</span>
      </div>
      <div class="kids-catalog-episode-list">
        ${episodes
          .map(
            (episode) => `
              <article class="kids-catalog-episode">
                <div>
                  <a href="${esc(episode.url)}" target="_blank" rel="noreferrer">${esc(episode.title || "")}</a>
                  <div class="kids-catalog-episode-meta">
                    ${episode.episode_number ? `<span>E${String(episode.episode_number).padStart(2, "0")}</span>` : ""}
                    ${episode.duration ? `<span>${esc(episode.duration)}</span>` : ""}
                  </div>
                </div>
                <button
                  type="button"
                  class="kids-catalog-enqueue-btn btn btn-primary btn-sm"
                  data-url="${esc(episode.url)}"
                  data-title="${esc(episode.title || "")}"
                  data-episode-number="${esc(episode.episode_number || "")}"
                >
                  Add to queue
                </button>
              </article>
            `
          )
          .join("")}
      </div>
    `;
    kidsCatalogEpisodes.querySelectorAll(".kids-catalog-enqueue-btn").forEach((btn) => {
      btn.addEventListener("click", () => enqueueEpisode(btn));
    });
  };

  const loadShows = async () => {
    setStatus("Loading kids catalog...", "neutral");
    const { ok, data } = await api.listKidsCatalogShows();
    if (!ok) {
      setStatus(buildStatusErrorState(data, "Kids catalog failed to load."), "error");
      return;
    }
    shows = Array.isArray(data.items) ? data.items : [];
    renderShows();
    setStatus(`Loaded ${shows.length} catalog shows.`, "ok");
  };

  const loadShow = async (slug) => {
    if (!slug) return;
    setStatus("Loading episodes...", "neutral");
    const { ok, data } = await api.getKidsCatalogShow(slug);
    if (!ok) {
      setStatus(buildStatusErrorState(data, "Kids show failed to load."), "error");
      return;
    }
    renderEpisodes(data);
    setStatus(`Loaded ${data.episode_count || 0} episodes for ${data.title || slug}.`, "ok");
  };

  const enqueueEpisode = async (btn) => {
    const episodeUrl = btn.dataset.url || "";
    if (!selectedShow || !episodeUrl) return;
    btn.disabled = true;
    setStatus("Resolving YouTube video...", "neutral");
    try {
      const { ok, data } = await api.resolveKidsCatalogEpisode({ episode_url: episodeUrl });
      if (!ok) {
        setStatus(buildStatusErrorState(data, "Episode could not be resolved."), "error");
        return;
      }
      const episodeNumber = Number(btn.dataset.episodeNumber || 0);
      const result = await enqueueDownload({
        detail_url: data.youtube_url,
        title: btn.dataset.title || data.title || selectedShow.title,
        source_type: "youtube",
        source_metadata: {
          provider: "veselerozpravky",
          source_url: episodeUrl,
          youtube_video_id: data.youtube_video_id,
        },
        preferred_mode: "auto",
        media_kind: "tv",
        is_kids: true,
        series_name: selectedShow.title,
        season_number: 1,
        episode_number: Number.isFinite(episodeNumber) && episodeNumber > 0 ? episodeNumber : null,
      });
      if (result.ok) {
        setStatus(`Queued ${btn.dataset.title || data.title || "episode"}.`, "ok");
      } else if (result.duplicateJob && result.duplicateIsActive) {
        await refreshDownloads?.();
        focusDownloadJob?.(result.duplicateJob.id);
      }
    } finally {
      btn.disabled = false;
    }
  };

  kidsCatalogLoadBtn.addEventListener("click", loadShows);
  kidsCatalogFilter?.addEventListener("input", renderShows);

  return { loadShows, loadShow };
};
