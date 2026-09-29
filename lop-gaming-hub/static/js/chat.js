/* LoP Gaming Hub — chatroom polling client.
   Polls new messages every 2.5s, posts via the CSRF-protected API,
   and renders everything with textContent (no HTML injection). */
(function () {
  "use strict";

  var wrap = document.querySelector(".chat-wrap");
  if (!wrap) return;

  var roomId = wrap.getAttribute("data-room-id");
  var messagesBox = document.getElementById("chatMessages");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatText");
  var onlineChip = document.getElementById("onlineCount");
  var onlineNames = document.getElementById("onlineNames");

  var POLL_MS = 2500;

  /* ---------- helpers ---------- */
  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function lastId() {
    var nodes = messagesBox.querySelectorAll(".msg[data-msg-id]");
    if (!nodes.length) return 0;
    return parseInt(nodes[nodes.length - 1].getAttribute("data-msg-id"), 10);
  }

  function isNearBottom() {
    return messagesBox.scrollHeight - messagesBox.scrollTop - messagesBox.clientHeight < 120;
  }

  function scrollBottom() {
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function renderMessage(m, mine) {
    var row = document.createElement("div");
    row.className = "msg" + (mine ? " msg-me" : "");
    row.setAttribute("data-msg-id", m.id);

    var av = document.createElement("span");
    av.className = "msg-avatar";
    av.textContent = (m.user || "?")[0].toUpperCase();

    var body = document.createElement("div");
    body.className = "msg-body";

    var meta = document.createElement("p");
    meta.className = "msg-meta";
    var name = document.createElement("strong");
    name.textContent = m.user;
    var time = document.createElement("time");
    time.textContent = (m.ts || "").slice(11, 19);
    meta.appendChild(name);
    meta.appendChild(time);

    var text = document.createElement("p");
    text.className = "msg-text";
    text.textContent = m.content;

    body.appendChild(meta);
    body.appendChild(text);
    row.appendChild(av);
    row.appendChild(body);
    return row;
  }

  /* ---------- poll ---------- */
  function poll() {
    fetch("/chat/" + roomId + "/api/messages?after=" + lastId(), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var stick = isNearBottom();
        (data.messages || []).forEach(function (m) {
          messagesBox.appendChild(renderMessage(m, false));
        });
        if (stick) scrollBottom();

        if (onlineChip && data.online_count !== undefined) {
          onlineChip.textContent = data.online_count + " online";
          onlineChip.classList.toggle("muted", data.online_count === 0);
        }
        if (onlineNames) {
          onlineNames.textContent = (data.online || []).join(", ");
        }
      })
      .catch(function () { /* transient network error — try again next tick */ });
  }

  /* ---------- send ---------- */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var content = input.value.trim();
    if (!content) return;

    var sendBtn = form.querySelector("button");
    sendBtn.disabled = true;

    window.LoP.fetch("/chat/" + roomId + "/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: content }),
      credentials: "same-origin",
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok && res.d.ok) {
          input.value = "";
          messagesBox.appendChild(renderMessage(res.d.message, true));
          scrollBottom();
        } else {
          var msg = (res.d && res.d.error) || "Could not send message.";
          flashError(msg);
        }
      })
      .catch(function () { flashError("Network error — message not sent."); })
      .finally(function () { sendBtn.disabled = false; });
  });

  function flashError(msg) {
    var el = document.createElement("div");
    el.className = "alert alert-error";
    el.textContent = msg;
    var box = document.querySelector(".chat-box");
    box.insertBefore(el, box.firstChild);
    setTimeout(function () { el.remove(); }, 3500);
  }

  /* ---------- boot ---------- */
  scrollBottom();
  setInterval(poll, POLL_MS);
})();