import { esc, truncateText } from "./dom-utils.js";

export const initMovieDiscovery = ({
  elements,
  api,
  openQueueDialog,
}) => {
  const {
    movieDiscoveryPanel,
    movieDiscoveryForm,
    movieDiscoveryMode,
    movieDiscoveryWindow,
    movieDiscoveryGenre,
    movieDiscoveryYear,
    movieDiscoveryLimit,
    movieDiscoveryStatus,
    movieDiscoveryResults,
  } = elements;

  if (!movieDiscoveryForm || !movieDiscoveryResults) {
    return {};
  }

  const setStatus = (message, mode = "neutral") => {
    if (!movieDiscoveryStatus) return;
    movieDiscoveryStatus.textContent = message || "";
    movieDiscoveryStatus.dataset.mode = mode;
  };

  const availabilityLabel = (status) => {
    if (status === "available") return "Available";
    if (status === "weak_match") return "Weak match";
    if (status === "error") return "Check failed";
    return "Not found";
  };

  const renderMovies = (items) => {
    if (!Array.isArray(items) || !items.length) {
      movieDiscoveryResults.innerHTML = `<div class="download-empty">No discovery movies found.</div>`;
      return;
    }
    movieDiscoveryResults.innerHTML = items.map((item) => {
      const availability = item.availability || {};
      const best = availability.best_result || null;
      const status = availability.status || "not_found";
      return `
        <article class="movie-discovery-card" data-status="${esc(status)}">
          ${item.poster_url ? `<img src="${esc(item.poster_url)}" alt="" loading="lazy" />` : `<div class="movie-discovery-poster-fallback">No poster</div>`}
          <div class="movie-discovery-body">
            <div class="movie-discovery-head">
              <strong>${esc(item.title || item.original_title || "Untitled movie")}</strong>
              <span>${esc(item.year || "n/a")}</span>
            </div>
            <div class="movie-discovery-meta">
              <span>TMDB ${esc(item.vote_average ?? "n/a")}</span>
              <span>${esc(item.vote_count ?? 0)} votes</span>
              <span class="movie-availability" data-status="${esc(status)}">${esc(availabilityLabel(status))}</span>
            </div>
            ${item.overview ? `<p>${esc(truncateText(item.overview, 180))}</p>` : ""}
            ${best ? `
              <div class="movie-discovery-match">
                <span>Best sdilej match</span>
                <strong>${esc(best.title || "")}</strong>
                <small>${esc(best.size || "n/a")} · ${esc(best.primary_year || "year n/a")} · ${esc((best.detected_languages || []).join(", ") || "language n/a")}</small>
              </div>
              <button
                type="button"
                class="movie-discovery-queue btn btn-primary btn-sm"
                data-file-id="${esc(best.file_id || "")}"
                data-title="${esc(best.title || "")}"
                data-detail-url="${esc(best.detail_url || "")}"
                data-status="${esc(status)}"
              >
                Add match to queue
              </button>
            ` : `<div class="movie-discovery-match muted">No usable sdilej match yet.</div>`}
          </div>
        </article>
      `;
    }).join("");

    movieDiscoveryResults.querySelectorAll(".movie-discovery-queue").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await openQueueDialog({
          intent: "enqueue",
          detailUrl: btn.dataset.detailUrl,
          fileId: btn.dataset.fileId ? Number(btn.dataset.fileId) : null,
          title: btn.dataset.title || "",
          preferredMode: "premium",
          destinationPreset: "movies",
          mediaKind: "movie",
          isKids: false,
        });
      });
    });
  };

  const loadGenres = async () => {
    const { ok, data } = await api.listMovieDiscoveryGenres("sk-SK");
    if (!ok || !data.configured) {
      setStatus(data?.hint || "Set TMDB_BEARER_TOKEN to enable movie discovery.", "warning");
      return;
    }
    (data.items || []).forEach((genre) => {
      const option = document.createElement("option");
      option.value = String(genre.id);
      option.textContent = genre.name;
      movieDiscoveryGenre?.appendChild(option);
    });
  };

  movieDiscoveryForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (movieDiscoveryPanel) {
      movieDiscoveryPanel.open = true;
    }
    setStatus("Loading TMDB movies and checking sdilej availability...", "neutral");
    movieDiscoveryResults.innerHTML = "";
    const params = {
      mode: movieDiscoveryMode?.value || "trending",
      time_window: movieDiscoveryWindow?.value || "week",
      limit: movieDiscoveryLimit?.value || "12",
      language: "sk-SK",
      region: "SK",
    };
    if (movieDiscoveryGenre?.value) params.genre = movieDiscoveryGenre.value;
    if (movieDiscoveryYear?.value) params.year = movieDiscoveryYear.value;
    const { ok, data } = await api.discoverMovies(params);
    if (!ok || !data.configured) {
      setStatus(data?.hint || data?.error || "Movie discovery is not configured.", "warning");
      return;
    }
    renderMovies(data.items || []);
    setStatus(`Loaded ${data.items?.length || 0} movies with sdilej availability.`, "ok");
  });

  loadGenres();

  return { loadGenres };
};
