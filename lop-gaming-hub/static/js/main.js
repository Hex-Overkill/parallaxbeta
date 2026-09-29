/* LoP Gaming Hub — global helpers */
(function () {
  "use strict";

  /* CSRF token from the meta tag */
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  /* fetch wrapper that always attaches the CSRF header */
  function apiFetch(url, opts) {
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {}, { "X-CSRFToken": csrfToken() });
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = opts.headers["Content-Type"] || "application/json";
    }
    return fetch(url, opts);
  }

  window.LoP = {
    csrf: csrfToken,
    fetch: apiFetch,
  };

  /* mobile nav toggle */
  var toggle = document.getElementById("navToggle");
  var links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      links.classList.toggle("open");
    });
  }

  /* data-confirm buttons (admin destructive actions) */
  document.querySelectorAll("[data-confirm]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var msg = btn.getAttribute("data-confirm");
      if (msg && !window.confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  /* auto-dismiss flash messages */
  document.querySelectorAll(".alert").forEach(function (el, i) {
    var delay = 4500 + i * 600;
    setTimeout(function () {
      el.style.transition = "opacity .4s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 450);
    }, delay);
  });
})();