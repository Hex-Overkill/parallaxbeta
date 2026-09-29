/* LoP Gaming Hub — playtime tracking for the game iframe page.
   Starts a server-side session on load, heartbeats every 30s, and
   reports the final duration on unload via sendBeacon (CSRF-exempt API).
   The game slug is read from data-game on this script tag. */
(function () {
  "use strict";

  var script = document.currentScript;
  var slug = script && script.getAttribute("data-game");
  if (!slug) return;

  var BASE = "/api/games/" + encodeURIComponent(slug) + "/session";
  var sessionId = null;
  var startedAt = null;
  var heartbeatTimer = null;
  var heartbeatDelay = 30000;

  function postForm(url, fields) {
    var body = new FormData();
    Object.keys(fields).forEach(function (k) { body.append(k, fields[k]); });
    return fetch(url, { method: "POST", body: body, credentials: "same-origin" });
  }

  function start() {
    postForm(BASE + "/start", {})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok && data.session_id) {
          sessionId = data.session_id;
          startedAt = Date.now();
          heartbeatTimer = setInterval(heartbeat, heartbeatDelay);
        }
      })
      .catch(function () { /* offline — nothing to track */ });
  }

  function heartbeat() {
    if (!sessionId) return;
    postForm(BASE + "/heartbeat", { session_id: sessionId })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.ended) stopTimers();
      })
      .catch(function () {});
  }

  function stopTimers() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  }

  function end() {
    stopTimers();
    if (!sessionId || !slug) return;
    if (navigator.sendBeacon) {
      var body = new FormData();
      body.append("session_id", sessionId);
      navigator.sendBeacon(BASE + "/end", body);
    } else {
      postForm(BASE + "/end", { session_id: sessionId });
    }
    sessionId = null;
  }

  /* End the session when the tab is hidden (navigating away, closing,
     switching tabs) and heartbeat again if the user comes back. */
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      end();
      heartbeatTimer = null; // paused
    } else if (sessionId === null && startedAt !== null) {
      // returning to the page: resume tracking a fresh session
      start();
    }
  });
  window.addEventListener("pagehide", end);

  start();
})();