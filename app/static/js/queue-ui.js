import { buildEpisodeQueueKey, buildFileQueueKey, buildTvEpisodeKey } from "./keys.js";
import { queueBadgeLabelForStatus, queueButtonLabelForStatus } from "./formatters.js";
import { buildDownloadedTvEpisodesFromJobs } from "./tv-state.js";

const choosePreferredActiveJob = (current, candidate) => {
  if (!current) return candidate;
  if (!candidate) return current;
  if (current.status !== "running" && candidate.status === "running") return candidate;
  if (current.status === "running" && candidate.status !== "running") return current;
  return Number(candidate.id || 0) > Number(current.id || 0) ? candidate : current;
};

export const createQueueUiHelpers = ({ downloadJobsEl, setDownloadStatus } = {}) => {
  const focusDownloadJob = (jobId) => {
    const job = downloadJobsEl?.querySelector(`[data-job-id="${CSS.escape(String(jobId))}"]`);
    if (!job) {
      setDownloadStatus?.(`Job #${jobId} is no longer visible in the queue.`, "neutral");
      return false;
    }
    job.scrollIntoView({ behavior: "smooth", block: "center" });
    job.classList.add("job-focused");
    window.setTimeout(() => job.classList.remove("job-focused"), 1200);
    setDownloadStatus?.(`Showing job #${jobId}.`, "ok");
    return true;
  };

  const bindQueueManageButtons = (root = document) => {
    root.querySelectorAll(".queue-manage-btn, .tv-manage-btn").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const jobId = Number(btn.dataset.jobId || 0);
        focusDownloadJob(jobId);
      });
    });
  };

  const applyCardQueueState = (card, job) => {
    const queueBtn = card.querySelector(".queue-dialog-btn");
    const manageBtn = card.querySelector(".queue-manage-btn");
    const stateEl = card.querySelector(".card-queue-state");

    card.classList.remove("queue-active", "queue-running", "queue-queued");

    if (!job) {
      if (queueBtn) {
        queueBtn.disabled = false;
        queueBtn.textContent = queueBtn.dataset.defaultLabel || "Add to queue...";
      }
      if (manageBtn) {
        manageBtn.classList.add("hidden");
        manageBtn.dataset.jobId = "";
      }
      if (stateEl) {
        stateEl.classList.add("hidden");
        stateEl.textContent = "";
        delete stateEl.dataset.mode;
      }
      return;
    }

    card.classList.add("queue-active", `queue-${job.status}`);
    if (queueBtn) {
      queueBtn.disabled = true;
      queueBtn.textContent = queueButtonLabelForStatus(job.status);
    }
    if (manageBtn) {
      manageBtn.classList.remove("hidden");
      manageBtn.dataset.jobId = String(job.id);
    }
    if (stateEl) {
      stateEl.classList.remove("hidden");
      stateEl.dataset.mode = job.status;
      stateEl.textContent = `${queueBadgeLabelForStatus(job.status)} as job #${job.id}`;
    }
  };

  const buildActiveQueueStateFromJobs = (jobs) => {
    const fileJobs = new Map();
    const episodeJobs = new Map();
    const jobsById = new Map();

    (Array.isArray(jobs) ? jobs : []).forEach((job) => {
      const status = String(job?.status || "");
      if (!["queued", "running"].includes(status)) return;

      jobsById.set(String(job.id), job);

      const fileKey = buildFileQueueKey({ fileId: job.file_id, detailUrl: job.detail_url });
      if (fileKey) {
        fileJobs.set(fileKey, choosePreferredActiveJob(fileJobs.get(fileKey), job));
      }

      const episodeKey = buildEpisodeQueueKey({
        seriesName: job.series_name,
        seasonNumber: job.season_number,
        episodeNumber: job.episode_number,
      });
      if (episodeKey) {
        const current = episodeJobs.get(episodeKey);
        const summary = current || { jobs: [], primaryJob: job, status: status };
        summary.jobs.push(job);
        summary.primaryJob = choosePreferredActiveJob(summary.primaryJob, job);
        summary.status = summary.primaryJob.status;
        episodeJobs.set(episodeKey, summary);
      }
    });

    return { fileJobs, episodeJobs, jobsById };
  };

  const applyTvResultQueueState = (row, job) => {
    const queueBtn = row.querySelector(".tv-queue-btn");
    const manageBtn = row.querySelector(".tv-manage-btn");
    const stateEl = row.querySelector(".tv-result-queue-state");

    row.classList.remove("queue-active", "queue-running", "queue-queued");

    if (!job) {
      if (queueBtn) {
        queueBtn.disabled = false;
        queueBtn.textContent = queueBtn.dataset.defaultLabel || "Add to queue...";
      }
      if (manageBtn) {
        manageBtn.classList.add("hidden");
        manageBtn.dataset.jobId = "";
      }
      if (stateEl) {
        stateEl.classList.add("hidden");
        stateEl.textContent = "";
        delete stateEl.dataset.mode;
      }
      return;
    }

    row.classList.add("queue-active", `queue-${job.status}`);
    if (queueBtn) {
      queueBtn.disabled = true;
      queueBtn.textContent = queueButtonLabelForStatus(job.status);
    }
    if (manageBtn) {
      manageBtn.classList.remove("hidden");
      manageBtn.dataset.jobId = String(job.id);
    }
    if (stateEl) {
      stateEl.classList.remove("hidden");
      stateEl.dataset.mode = job.status;
      stateEl.textContent = `${queueBadgeLabelForStatus(job.status)} as job #${job.id}`;
    }
  };

  const applyEpisodeQueueSummaryState = (episodeNode, summary) => {
    const badge = episodeNode.querySelector(".tv-episode-queue-badge");
    episodeNode.classList.remove("queue-active", "queue-running", "queue-queued");
    if (!badge) return;

    if (!summary || !Array.isArray(summary.jobs) || summary.jobs.length === 0) {
      badge.classList.add("hidden");
      badge.textContent = "";
      delete badge.dataset.mode;
      return;
    }

    const label = queueBadgeLabelForStatus(summary.status);
    const suffix = summary.jobs.length > 1 ? ` (${summary.jobs.length})` : "";
    episodeNode.classList.add("queue-active", `queue-${summary.status}`);
    badge.classList.remove("hidden");
    badge.dataset.mode = summary.status;
    badge.textContent = `${label}${suffix}`;
  };

  return {
    focusDownloadJob,
    bindQueueManageButtons,
    applyCardQueueState,
    applyTvResultQueueState,
    applyEpisodeQueueSummaryState,
    buildActiveQueueStateFromJobs,
    buildDownloadedTvEpisodesFromJobs,
  };
};
