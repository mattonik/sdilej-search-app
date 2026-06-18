import { esc } from "./dom-utils.js";

const DETAIL_LABELS = [
  ["error_code", "Error code"],
  ["request_id", "Request ID"],
  ["hint", "Hint"],
  ["retryable", "Retryable"],
  ["details", "Details"],
];

const normalizeText = (value) => {
  if (value === null || value === undefined) return "";
  return String(value).trim();
};

const normalizeRetryable = (value) => {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "";
};

const normalizeDetailRows = (details) => {
  if (!details) return [];
  if (typeof details === "string") {
    const text = normalizeText(details);
    return text ? [["Details", text]] : [];
  }
  if (Array.isArray(details)) {
    return details
      .map((entry) => {
        if (!entry) return null;
        if (Array.isArray(entry) && entry.length >= 2) {
          const label = normalizeText(entry[0]);
          const value = normalizeText(entry[1]);
          return label && value ? [label, value] : null;
        }
        if (typeof entry === "object") {
          const label = normalizeText(entry.label || entry.key || entry.name);
          const value = normalizeText(entry.value || entry.text || entry.detail);
          return label && value ? [label, value] : null;
        }
        return null;
      })
      .filter(Boolean);
  }
  if (typeof details !== "object") return [];

  const rows = [];
  const add = (label, value) => {
    const text = normalizeText(value);
    if (text) rows.push([label, text]);
  };

  for (const [key, label] of DETAIL_LABELS) {
    if (key === "retryable") {
      add(label, normalizeRetryable(details.retryable));
      continue;
    }
    add(label, details[key]);
  }

  for (const [key, value] of Object.entries(details)) {
    if (DETAIL_LABELS.some(([field]) => field === key)) continue;
    add(key.replace(/_/g, " "), value);
  }

  return rows;
};

const buildCopyText = ({ message, mode, details }) => {
  const lines = [];
  if (message) lines.push(`Status: ${message}`);
  if (mode) lines.push(`Mode: ${mode}`);
  const rows = normalizeDetailRows(details);
  for (const [label, value] of rows) {
    lines.push(`${label}: ${value}`);
  }
  return lines.join("\n");
};

const copyToClipboard = async (text) => {
  const value = normalizeText(text);
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

export const buildStatusErrorState = (payload, fallbackMessage, { mode = "error", hint = null } = {}) => {
  const data = payload && typeof payload === "object" ? payload : {};
  return {
    message: normalizeText(data.error || fallbackMessage || "Unexpected error."),
    mode: data.retryable === false ? "error" : mode,
    details: {
      error_code: data.error_code || data.errorCode || null,
      request_id: data.request_id || data.requestId || null,
      hint: data.hint || hint || null,
      retryable: data.retryable ?? null,
      details: data.details || data.detail || data.message || null,
    },
  };
};

export const createStatusController = (element) => {
  let currentCopyText = "";
  let currentMode = "neutral";

  const setStatus = (value, mode = "neutral", details = null) => {
    const state =
      typeof value === "object" && value !== null
        ? {
            message: normalizeText(value.message || value.text || value.error),
            mode: value.mode || mode || "neutral",
            details: value.details ?? null,
          }
        : {
            message: normalizeText(value),
            mode,
            details,
          };

    currentMode = state.mode || "neutral";
    currentCopyText = buildCopyText(state);

    if (!element) return state;

    const rows = normalizeDetailRows(state.details);
    const hasDetails = rows.length > 0;
    const hasCopy = Boolean(currentCopyText) && (currentMode === "error" || currentMode === "warning" || hasDetails);
    element.dataset.mode = currentMode;
    element.innerHTML = `
      <div class="status-summary">
        <span class="status-message">${esc(state.message || "")}</span>
        ${hasCopy ? `<button type="button" class="btn btn-soft btn-sm status-copy-btn">Copy details</button>` : ""}
      </div>
      ${hasDetails ? `<details class="status-details"><summary>Details</summary><div class="status-detail-list">${rows
        .map(([label, value]) => `<div class="status-detail-row"><span class="status-detail-label">${esc(label)}</span><span class="status-detail-value">${esc(value)}</span></div>`)
        .join("")}</div></details>` : ""}
    `;

    const copyBtn = element.querySelector(".status-copy-btn");
    if (copyBtn && hasCopy) {
      copyBtn.addEventListener("click", async () => {
        const original = copyBtn.textContent;
        try {
          const copied = await copyToClipboard(currentCopyText);
          copyBtn.textContent = copied ? "Copied" : "Copy failed";
        } finally {
          window.setTimeout(() => {
            copyBtn.textContent = original || "Copy details";
          }, 1200);
        }
      });
    }

    return state;
  };

  return {
    setStatus,
    getMode: () => currentMode,
  };
};
