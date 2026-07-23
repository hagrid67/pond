(function () {
  "use strict";

  function initBookingsWidget(rootNode) {
    const widget = rootNode && rootNode.classList && rootNode.classList.contains("bookings-widget")
      ? rootNode
      : (rootNode ? rootNode.querySelector(".bookings-widget") : null);

    if (!widget || widget.dataset.filtersInit === "1") {
      return;
    }
    widget.dataset.filtersInit = "1";

    const PREFS_STORAGE_KEY = "pondBookingsFilterPrefs";
    const PREFS_CONSENT_KEY = "pondBookingsFilterPrefsConsent";
    const FILTERS_COLLAPSED_STORAGE_KEY = "pondBookingsFiltersCollapsed";

    const debugFilters = window.location.search.includes("debugFilters=1");
    function debugLog(message, details) {
      if (!debugFilters) {
        return;
      }
      if (typeof details === "undefined") {
        console.log("[bookings-filters]", message);
      } else {
        console.log("[bookings-filters]", message, details);
      }
    }

    const uiButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='ui']"));
    const prefsButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='prefs']"));
    const rememberButton = prefsButtons.find((btn) => btn.dataset.filterValue === "remember");
    const filtersShell = widget.querySelector(".filters-shell");
    const desktopToggle = filtersShell ? filtersShell.querySelector(".filters-toggle-desktop") : null;
    const slotGroupButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='slot-group']"));
    const venueButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='venue']"));
    const dayGroupButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='day-group']"));
    const timeButtons = Array.from(widget.querySelectorAll(".filter-btn[data-filter-group='time']"));
    const reloadSelector = document.getElementById("reloadInterval");

    function setDesktopFiltersCollapsed(isCollapsed) {
      if (!filtersShell || !desktopToggle) {
        return;
      }
      filtersShell.classList.toggle("filters-collapsed", isCollapsed);
      desktopToggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      desktopToggle.textContent = isCollapsed ? "Show filters" : "Hide filters";
      try {
        window.localStorage.setItem(FILTERS_COLLAPSED_STORAGE_KEY, isCollapsed ? "1" : "0");
      } catch (_err) {
        // Ignore storage failures.
      }
      debugLog("desktop disclosure toggled", {
        isCollapsed: isCollapsed,
        width: window.innerWidth,
      });
    }

    if (desktopToggle) {
      desktopToggle.addEventListener("click", () => {
        const isCollapsed = !filtersShell.classList.contains("filters-collapsed");
        setDesktopFiltersCollapsed(isCollapsed);
      });
    }

    debugLog("init", {
      width: window.innerWidth,
      mediaMax900: window.matchMedia("(max-width: 900px)").matches,
      hasDesktopToggle: !!desktopToggle,
      hasMobileToggle: false,
    });

    try {
      const collapsedPref = window.localStorage.getItem(FILTERS_COLLAPSED_STORAGE_KEY) === "1";
      setDesktopFiltersCollapsed(collapsedPref);
    } catch (_err) {
      setDesktopFiltersCollapsed(false);
    }

    if (!slotGroupButtons.length && !venueButtons.length && !dayGroupButtons.length && !timeButtons.length) {
      return;
    }

    const selectedVenues = new Set(venueButtons.map((btn) => btn.dataset.filterValue));
    const selectedDayGroups = new Set(dayGroupButtons.map((btn) => btn.dataset.filterValue));
    const selectedTimes = new Set(timeButtons.map((btn) => btn.dataset.filterValue));
    const selectedSlotGroups = new Set(slotGroupButtons.map((btn) => btn.dataset.filterValue));
    let showWeather = false;
    let persistPrefs = false;

    function readStorage(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (_err) {
        return null;
      }
    }

    function writeStorage(key, value) {
      try {
        window.localStorage.setItem(key, value);
        return true;
      } catch (_err) {
        return false;
      }
    }

    function removeStorage(key) {
      try {
        window.localStorage.removeItem(key);
      } catch (_err) {
        // Ignore storage removal failures.
      }
    }

    function setButtonState(button, isActive) {
      button.classList.toggle("active", isActive);
    }

    function updateRememberButton() {
      if (!rememberButton) {
        return;
      }
      rememberButton.textContent = persistPrefs
        ? "Remember my filters on this device: On"
        : "Remember my filters on this device: Off";
      setButtonState(rememberButton, persistPrefs);
    }

    function savePreferences() {
      if (!persistPrefs) {
        return;
      }
      const payload = {
        venues: Array.from(selectedVenues),
        dayGroups: Array.from(selectedDayGroups),
        times: Array.from(selectedTimes),
        slotGroups: Array.from(selectedSlotGroups),
        darkBg: widget.classList.contains("dark-bg"),
        showWeather: showWeather,
        reloadInterval: reloadSelector ? reloadSelector.value : null,
      };
      writeStorage(PREFS_STORAGE_KEY, JSON.stringify(payload));
    }

    function loadPreferences() {
      const raw = readStorage(PREFS_STORAGE_KEY);
      if (!raw) {
        return;
      }

      let parsed = null;
      try {
        parsed = JSON.parse(raw);
      } catch (_err) {
        return;
      }

      if (parsed && Array.isArray(parsed.venues)) {
        selectedVenues.clear();
        parsed.venues.forEach((value) => {
          if (venueButtons.some((btn) => btn.dataset.filterValue === value)) {
            selectedVenues.add(value);
          }
        });
      }

      if (parsed && Array.isArray(parsed.dayGroups)) {
        selectedDayGroups.clear();
        parsed.dayGroups.forEach((value) => {
          if (dayGroupButtons.some((btn) => btn.dataset.filterValue === value)) {
            selectedDayGroups.add(value);
          }
        });
      }

      if (parsed && Array.isArray(parsed.times)) {
        selectedTimes.clear();
        parsed.times.forEach((value) => {
          if (timeButtons.some((btn) => btn.dataset.filterValue === value)) {
            selectedTimes.add(value);
          }
        });
      }

      if (parsed && Array.isArray(parsed.slotGroups)) {
        selectedSlotGroups.clear();
        parsed.slotGroups.forEach((value) => {
          if (slotGroupButtons.some((btn) => btn.dataset.filterValue === value)) {
            selectedSlotGroups.add(value);
          }
        });
      }

      if (parsed && parsed.darkBg) {
        widget.classList.add("dark-bg");
      }

      if (parsed && typeof parsed.showWeather === "boolean") {
        showWeather = parsed.showWeather;
      }

      if (reloadSelector && parsed && typeof parsed.reloadInterval === "string") {
        const hasOption = !!reloadSelector.querySelector("option[value='" + parsed.reloadInterval + "']");
        if (hasOption) {
          reloadSelector.value = parsed.reloadInterval;
          if (typeof window.update_reload_setting === "function") {
            window.update_reload_setting();
          }
        }
      }

      venueButtons.forEach((btn) => setButtonState(btn, selectedVenues.has(btn.dataset.filterValue)));
      dayGroupButtons.forEach((btn) => setButtonState(btn, selectedDayGroups.has(btn.dataset.filterValue)));
      timeButtons.forEach((btn) => setButtonState(btn, selectedTimes.has(btn.dataset.filterValue)));
      slotGroupButtons.forEach((btn) => setButtonState(btn, selectedSlotGroups.has(btn.dataset.filterValue)));

      const darkToggle = uiButtons.find((btn) => btn.dataset.filterValue === "dark-bg");
      if (darkToggle) {
        setButtonState(darkToggle, widget.classList.contains("dark-bg"));
      }
      const weatherToggle = uiButtons.find((btn) => btn.dataset.filterValue === "weather");
      if (weatherToggle) {
        setButtonState(weatherToggle, showWeather);
      }
    }

    function refreshDayGroupButtons() {
      dayGroupButtons.forEach((groupBtn) => {
        setButtonState(groupBtn, selectedDayGroups.has(groupBtn.dataset.filterValue));
      });
    }

    function refreshSlotGroupButtons() {
      slotGroupButtons.forEach((groupBtn) => {
        const groupName = groupBtn.dataset.filterValue;
        setButtonState(groupBtn, selectedSlotGroups.has(groupName));
      });
    }

    function applyFilters() {
      widget.querySelectorAll("th.weather-col, td.weather-col").forEach((cell) => {
        cell.classList.toggle("weather-hidden", !showWeather);
      });

      timeButtons.forEach((button) => {
        const slotGroup = button.dataset.slotGroup;
        button.style.display = selectedSlotGroups.has(slotGroup) ? "" : "none";
      });

      widget.querySelectorAll(".bookings-table").forEach((table) => {
        table.querySelectorAll("th.venue-col, td.venue-cell").forEach((cell) => {
          const venueIdx = cell.dataset.venueIdx;
          cell.style.display = selectedVenues.has(venueIdx) ? "" : "none";
        });

        table.querySelectorAll("tr[data-time]").forEach((row) => {
          const timeMatch = selectedTimes.has(row.dataset.time);
          const slotGroupMatch = selectedSlotGroups.has(row.dataset.slotGroup);
          const hasVisibleVenue = Array.from(row.querySelectorAll("td.venue-cell")).some(
            (cell) => cell.style.display !== "none"
          );
          row.style.display = timeMatch && slotGroupMatch && hasVisibleVenue ? "" : "none";
        });
      });

      widget.querySelectorAll(".booking-day").forEach((section) => {
        const daySelected = selectedDayGroups.has(section.dataset.dayGroup);
        const hasVisibleRows = Array.from(section.querySelectorAll("tr[data-time]")).some(
          (row) => row.style.display !== "none"
        );
        section.style.display = daySelected && hasVisibleRows ? "" : "none";
      });

      refreshDayGroupButtons();
      refreshSlotGroupButtons();
      savePreferences();
    }

    prefsButtons.forEach((button) => {
      if (button.dataset.filterValue !== "remember") {
        return;
      }
      button.addEventListener("click", () => {
        persistPrefs = !persistPrefs;
        if (persistPrefs) {
          if (!writeStorage(PREFS_CONSENT_KEY, "accepted")) {
            persistPrefs = false;
          }
        } else {
          removeStorage(PREFS_CONSENT_KEY);
          removeStorage(PREFS_STORAGE_KEY);
        }
        updateRememberButton();
        savePreferences();
      });
    });

    uiButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.filterValue === "dark-bg") {
          widget.classList.toggle("dark-bg");
          setButtonState(button, widget.classList.contains("dark-bg"));
        } else if (button.dataset.filterValue === "weather") {
          showWeather = !showWeather;
          setButtonState(button, showWeather);
          applyFilters();
        }
        savePreferences();
      });
    });

    slotGroupButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.filterValue;
        if (selectedSlotGroups.has(value)) {
          selectedSlotGroups.delete(value);
        } else {
          selectedSlotGroups.add(value);
        }
        setButtonState(button, selectedSlotGroups.has(value));
        applyFilters();
      });
    });

    dayGroupButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.filterValue;
        if (selectedDayGroups.has(value)) {
          selectedDayGroups.delete(value);
        } else {
          selectedDayGroups.add(value);
        }
        setButtonState(button, selectedDayGroups.has(value));
        applyFilters();
      });
    });

    function wireButtons(buttons, selectedSet) {
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          const value = button.dataset.filterValue;
          if (selectedSet.has(value)) {
            selectedSet.delete(value);
          } else {
            selectedSet.add(value);
          }
          setButtonState(button, selectedSet.has(value));
          applyFilters();
        });
      });
    }

    wireButtons(venueButtons, selectedVenues);
    wireButtons(timeButtons, selectedTimes);

    if (reloadSelector) {
      reloadSelector.addEventListener("change", () => {
        savePreferences();
      });
    }

    persistPrefs = readStorage(PREFS_CONSENT_KEY) === "accepted";
    updateRememberButton();
    if (persistPrefs) {
      loadPreferences();
    }

    refreshDayGroupButtons();
    refreshSlotGroupButtons();
    applyFilters();
  }

  function initAllBookingsWidgets(root) {
    const searchRoot = root || document;
    searchRoot.querySelectorAll(".bookings-widget").forEach((widget) => {
      initBookingsWidget(widget);
    });
  }

  window.initBookingsWidget = initBookingsWidget;
  window.initAllBookingsWidgets = initAllBookingsWidgets;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initAllBookingsWidgets(document);
    });
  } else {
    initAllBookingsWidgets(document);
  }
})();
