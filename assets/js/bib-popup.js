(function () {
  var overlay = null;
  var pubCardsCache = null; // parsed DOM fragment of publications.html

  function createOverlay() {
    var el = document.createElement("div");
    el.className = "bib-overlay";
    el.innerHTML =
      '<div class="bib-popup pub-card-popup">' +
        '<button class="bib-popup-close" aria-label="Close">&times;</button>' +
        '<div class="pub-card-popup-body"></div>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }

  function hidePopup() {
    if (overlay) overlay.style.display = "none";
  }

  function loadPublicationsHTML() {
    if (pubCardsCache) return Promise.resolve(pubCardsCache);
    var version = document.documentElement.getAttribute("data-build") || Date.now();
    return fetch("tables/publications.html?v=" + version)
      .then(function (res) { return res.text(); })
      .then(function (text) {
        var tmp = document.createElement("div");
        tmp.innerHTML = text;
        pubCardsCache = tmp;
        return tmp;
      });
  }

  function showPubCard(bibkey) {
    if (!overlay) overlay = createOverlay();
    var body = overlay.querySelector(".pub-card-popup-body");
    body.innerHTML = '<div class="loading-message">Loading…</div>';
    overlay.style.display = "flex";

    loadPublicationsHTML().then(function (container) {
      var card = container.querySelector('article[data-bibkey="' + CSS.escape(bibkey) + '"]');
      if (!card) {
        body.innerHTML = '<div class="error-message">Publication not found.</div>';
        return;
      }
      var clone = card.cloneNode(true);
      // Remove the rank badge in the popup
      var rank = clone.querySelector(".pub-rank");
      if (rank) rank.remove();
      // Make sure the card is visible (not hidden by pagination)
      clone.style.display = "";
      clone.classList.add("pub-card-in-popup");
      body.innerHTML = "";
      body.appendChild(clone);

      // Re-attach BibTeX copy handler for the cloned card
      var bibBtn = clone.querySelector(".pub-bib-copy");
      if (bibBtn) {
        bibBtn.addEventListener("click", function (ev) {
          ev.stopPropagation();
          var bibtex = bibBtn.getAttribute("data-bibtex");
          if (bibtex && navigator.clipboard) {
            navigator.clipboard.writeText(bibtex).then(function () {
              bibBtn.textContent = "Copied!";
              bibBtn.classList.add("pub-bib-copied");
              setTimeout(function () {
                bibBtn.textContent = "BibTeX";
                bibBtn.classList.remove("pub-bib-copied");
              }, 1000);
            }).catch(function () {});
          }
        });
      }
    }).catch(function () {
      body.innerHTML = '<div class="error-message">Failed to load publication data.</div>';
    });
  }

  document.addEventListener("click", function (ev) {
    var target = ev.target;

    // Clicked a bib-btn in taxonomy/assets/datasets table
    var bibBtn = target.closest(".bib-btn");
    if (bibBtn) {
      var bibkey = bibBtn.getAttribute("data-bibkey");
      if (bibkey) {
        showPubCard(bibkey);
        return;
      }
    }

    if (target.classList && target.classList.contains("bib-popup-close")) {
      hidePopup();
    }

    if (target === overlay) {
      hidePopup();
    }
  });

  // Close on Escape key
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") hidePopup();
  });
})();
