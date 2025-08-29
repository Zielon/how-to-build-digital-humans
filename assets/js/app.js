const TABLE_FILES = {
  publications: "tables/publications.html",
  taxonomy: "tables/taxonomy.html",
  assets: "tables/assets.html",
  datasets: "tables/datasets.html",
  statistics: "tables/statistics.html",
  "add-entry": "tables/add-entry.html",
};

// Cache-busting version injected by deploy.sh (fallback to timestamp)
const BUILD_VERSION = document.documentElement.getAttribute("data-build") || Date.now();

const cache = {};

async function loadTable(name) {
  const container = document.getElementById("table-container");
  if (!container) return;

  // Lock current height to prevent layout shift while swapping content
  var prevHeight = container.offsetHeight;
  if (prevHeight > 0) {
    container.style.minHeight = prevHeight + "px";
  }

  if (cache[name]) {
    container.innerHTML = cache[name];
    runInlineScripts(container);
    container.style.minHeight = "";
    return;
  }

  container.innerHTML = '<div class="loading-message">Loading ' + name + ' table\u2026</div>';

  const url = TABLE_FILES[name];
  if (!url) {
    container.innerHTML = '<div class="error-message">Unknown table.</div>';
    container.style.minHeight = "";
    return;
  }

  try {
    const res = await fetch(url + "?v=" + BUILD_VERSION);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const text = await res.text();
    cache[name] = text;
    container.innerHTML = text;
    runInlineScripts(container);
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div class="error-message">Failed to load table. Please try again later.</div>';
  }
  container.style.minHeight = "";
}

/**
 * innerHTML does NOT execute <script> tags.
 * This finds all script tags in the container and re-creates them
 * so the browser actually runs them.
 */
function runInlineScripts(container) {
  var scripts = container.querySelectorAll("script");
  for (var i = 0; i < scripts.length; i++) {
    var old = scripts[i];
    var fresh = document.createElement("script");
    if (old.src) {
      fresh.src = old.src;
    } else {
      fresh.textContent = old.textContent;
    }
    old.parentNode.replaceChild(fresh, old);
  }
}

function switchToTab(table) {
  var buttons = Array.from(document.querySelectorAll(".tab-button"));
  var matched = false;
  buttons.forEach(function(b) {
    var isActive = b.getAttribute("data-table") === table;
    b.classList.toggle("is-active", isActive);
    b.setAttribute("aria-selected", isActive ? "true" : "false");
    if (isActive) matched = true;
  });
  if (matched) loadTable(table);
  return matched;
}

function getTabFromHash() {
  var hash = location.hash.replace("#", "").toLowerCase();
  if (!hash) return null;
  var valid = ["publications", "taxonomy", "assets", "datasets", "statistics", "add-entry"];
  for (var i = 0; i < valid.length; i++) {
    if (valid[i] === hash) return valid[i];
  }
  return null;
}

function initTabs() {
  var buttons = Array.from(document.querySelectorAll(".tab-button"));
  buttons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      var table = btn.getAttribute("data-table");
      if (!table) return;
      buttons.forEach(function(b) {
        var isActive = b === btn;
        b.classList.toggle("is-active", isActive);
        b.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      if (table === "publications") {
        history.pushState(null, "", location.pathname + location.search);
      } else {
        history.pushState(null, "", "#" + table);
      }
      loadTable(table);
    });
  });

  window.addEventListener("hashchange", function() {
    var tab = getTabFromHash();
    if (tab) switchToTab(tab);
  });

  // Legend filtering: clicking a legend item toggles it in the filter array
  if (!window.__legendFilters) window.__legendFilters = [];
  document.getElementById("table-container").addEventListener("click", function(e) {
    var btn = e.target.closest(".legend-filter-btn");
    if (!btn) return;
    var field = btn.getAttribute("data-filter-field");
    var value = btn.getAttribute("data-filter-value");

    // Toggle: remove if already present, add otherwise
    var idx = -1;
    for (var i = 0; i < window.__legendFilters.length; i++) {
      if (window.__legendFilters[i].field === field && window.__legendFilters[i].value === value) {
        idx = i; break;
      }
    }
    if (idx >= 0) {
      window.__legendFilters.splice(idx, 1);
      btn.classList.remove("is-active");
    } else {
      window.__legendFilters.push({ field: field, value: value });
      btn.classList.add("is-active");
    }

    // Trigger filter update
    if (typeof window.__pubDoFilter === "function") {
      window.__pubDoFilter();
    }
  });

  var initialTab = getTabFromHash() || "publications";
  switchToTab(initialTab);
}

/* === Cell overflow tooltip for taxonomy / assets / datasets tables === */
function initCellTooltip() {
  var tip = document.createElement("div");
  tip.className = "cell-tooltip";
  document.body.appendChild(tip);

  var hideTimer = null;
  var currentCell = null;

  var container = document.getElementById("table-container");
  if (!container) return;

  container.addEventListener("mouseenter", function(e) {
    var td = e.target.closest(".latex-table td, .latex-table th");
    if (!td) return;
    // Only show tooltip if content is actually truncated (horizontally or vertically)
    if (td.scrollWidth <= td.clientWidth + 1 && td.scrollHeight <= td.clientHeight + 1) return;

    currentCell = td;
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }

    tip.innerHTML = td.innerHTML;
    tip.classList.add("is-visible");

    // Position: below the cell, aligned to its left edge
    var rect = td.getBoundingClientRect();
    var tipX = rect.left;
    var tipY = rect.bottom + 6;

    // Prevent going off-screen right
    tip.style.left = "0px";
    tip.style.top = "0px";
    tip.style.display = "block";
    var tipW = tip.offsetWidth;
    if (tipX + tipW > window.innerWidth - 12) {
      tipX = window.innerWidth - tipW - 12;
    }
    if (tipX < 4) tipX = 4;

    // Prevent going off-screen bottom — show above cell instead
    var tipH = tip.offsetHeight;
    if (tipY + tipH > window.innerHeight - 12) {
      tipY = rect.top - tipH - 6;
    }

    tip.style.left = tipX + "px";
    tip.style.top = tipY + "px";
  }, true);

  container.addEventListener("mouseleave", function(e) {
    var td = e.target.closest(".latex-table td, .latex-table th");
    if (!td || td !== currentCell) return;
    hideTimer = setTimeout(function() {
      tip.classList.remove("is-visible");
      currentCell = null;
    }, 80);
  }, true);
}

document.addEventListener("DOMContentLoaded", function() {
  initTabs();
  initCellTooltip();

  // Floating tooltip for crbox letter badges
  (function() {
    var tip = document.createElement("div");
    tip.className = "crbox-tip";
    document.body.appendChild(tip);

    var container = document.getElementById("table-container");
    if (!container) return;

    container.addEventListener("mouseover", function(e) {
      var crbox = e.target.closest(".crbox[title]");
      if (!crbox) { tip.classList.remove("is-visible"); return; }
      tip.textContent = crbox.getAttribute("title");
      tip.classList.add("is-visible");
      var r = crbox.getBoundingClientRect();
      var x = r.left + r.width / 2 - tip.offsetWidth / 2;
      var y = r.top - tip.offsetHeight - 6;
      if (x < 4) x = 4;
      if (x + tip.offsetWidth > window.innerWidth - 4) x = window.innerWidth - 4 - tip.offsetWidth;
      if (y < 4) y = r.bottom + 6;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    });

    container.addEventListener("mouseout", function(e) {
      if (e.target.closest(".crbox[title]")) tip.classList.remove("is-visible");
    });
  })();
});
