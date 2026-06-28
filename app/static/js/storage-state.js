import {
  FILE_RESULTS_FILTER_KEY,
  FILE_RESULTS_VIEW_KEY,
  FILE_SEARCH_ADVANCED_KEY,
  TV_ACTIVE_JOB_KEY,
} from "./keys.js";

const readValue = (key) => window.localStorage.getItem(key);

const writeValue = (key, value) => {
  if (value == null || value === "") {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, String(value));
};

export const readFileResultsView = () => (readValue(FILE_RESULTS_VIEW_KEY) === "list" ? "list" : "cards");

export const writeFileResultsView = (value) => writeValue(FILE_RESULTS_VIEW_KEY, value);

export const readFileResultsFilter = () => readValue(FILE_RESULTS_FILTER_KEY) || "all";

export const writeFileResultsFilter = (value) => writeValue(FILE_RESULTS_FILTER_KEY, value);

export const readSearchMode = () => {
  const value = readValue("searchMode");
  return ["file", "tv", "music", "discovery", "kids"].includes(value) ? value : "file";
};

export const writeSearchMode = (value) => writeValue("searchMode", value);

export const readActiveWorkspaceTab = () => readValue("activeWorkspaceTab");

export const writeActiveWorkspaceTab = (value) => writeValue("activeWorkspaceTab", value);

export const readActiveTvSearchJobId = () => readValue(TV_ACTIVE_JOB_KEY);

export const writeActiveTvSearchJobId = (value) => writeValue(TV_ACTIVE_JOB_KEY, value);

export const clearActiveTvSearchJobId = () => window.localStorage.removeItem(TV_ACTIVE_JOB_KEY);

export const readFileSearchAdvancedOpen = () => readValue(FILE_SEARCH_ADVANCED_KEY) === "1";

export const writeFileSearchAdvancedOpen = (value) => writeValue(FILE_SEARCH_ADVANCED_KEY, value ? "1" : "");
