export const initWorkspaceTabs = ({ workspaceTabs, tabSections, initialTab, onTabChange }) => {
  const setActiveTab = (tabName) => {
    const resolved =
      tabName === "downloads" ? "downloads" : tabName === "library" ? "library" : tabName === "settings" || tabName === "account" ? "settings" : "search";
    workspaceTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === resolved);
      if (tab.dataset.tab) {
        tab.setAttribute("aria-current", tab.dataset.tab === resolved ? "page" : "false");
      }
    });
    tabSections.forEach((section) => {
      const showSearch = section.classList.contains("tab-search");
      const showDownloads = section.classList.contains("tab-downloads");
      const showLibrary = section.classList.contains("tab-library");
      const showSettings = section.classList.contains("tab-settings");
      const visible =
        (resolved === "search" && showSearch) ||
        (resolved === "downloads" && showDownloads) ||
        (resolved === "library" && showLibrary) ||
        (resolved === "settings" && showSettings);
      section.style.display = visible ? "" : "none";
    });
    if (typeof onTabChange === "function") {
      onTabChange(resolved);
    }
    return resolved;
  };

  workspaceTabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tab || "search"));
  });

  setActiveTab(initialTab);
  return { setActiveTab };
};
