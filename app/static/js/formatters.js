export const formatBytes = (value) => {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  const num = Number(value);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let idx = 0;
  let current = num;
  while (current >= 1024 && idx < units.length - 1) {
    current /= 1024;
    idx += 1;
  }
  const precision = current >= 10 || idx === 0 ? 0 : 1;
  return `${current.toFixed(precision)} ${units[idx]}`;
};

export const formatSpeed = (value) => {
  if (value == null || Number.isNaN(Number(value)) || Number(value) <= 0) return "n/a";
  return `${formatBytes(value)}/s`;
};

export const formatEta = (bytesDownloaded, bytesTotal, speedBps) => {
  const done = Number(bytesDownloaded);
  const total = Number(bytesTotal);
  const speed = Number(speedBps);
  if (!Number.isFinite(done) || !Number.isFinite(total) || !Number.isFinite(speed) || speed <= 0 || done >= total) {
    return "n/a";
  }
  const seconds = Math.floor((total - done) / speed);
  if (!Number.isFinite(seconds) || seconds < 0) return "n/a";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export const pluralize = (count, singular, plural = `${singular}s`) => (count === 1 ? singular : plural);

export const queueButtonLabelForStatus = (status) => (status === "running" ? "Downloading" : "Added to queue");

export const queueBadgeLabelForStatus = (status) => (status === "running" ? "Downloading" : "In queue");
