export const initWorkspaceTabs = ({ workspaceTabs, tabSections, initialTab, onTabChange }) => {
  const setActiveTab = (tabName) => {
    const resolved =
      tabName === "downloads" ? "downloads" : tabName === "library" ? "library" : tabName === "account" ? "account" : "search";
    workspaceTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === resolved);
    });
    tabSections.forEach((section) => {
      const showSearch = section.classList.contains("tab-search");
      const showDownloads = section.classList.contains("tab-downloads");
      const showLibrary = section.classList.contains("tab-library");
      const showAccount = section.classList.contains("tab-account");
      const visible =
        (resolved === "search" && showSearch) ||
        (resolved === "downloads" && showDownloads) ||
        (resolved === "library" && showLibrary) ||
        (resolved === "account" && showAccount);
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
