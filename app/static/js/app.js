/* Portal front-end glue: CSRF for HTMX, idle-timeout redirect, Kanban DnD. */
(function () {
  "use strict";

  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? decodeURIComponent(m.pop()) : "";
  }
  const CSRF = getCookie("csrftoken");

  // --- HTMX: attach CSRF token to every unsafe request ---------------------
  document.body.addEventListener("htmx:configRequest", function (evt) {
    evt.detail.headers["X-CSRFToken"] = CSRF;
  });

  // --- 45-minute idle auto-logout (client side, mirrors server, TЗ §1) -----
  const idleSeconds = parseInt(document.body.dataset.idleTimeout || "2700", 10);
  const loginUrl = document.body.dataset.loginUrl || "/accounts/login/";
  let idleTimer = null;
  function resetIdle() {
    if (!document.body.dataset.authenticated) return;
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      window.location.href = loginUrl + "?next=" + encodeURIComponent(window.location.pathname);
    }, idleSeconds * 1000);
  }
  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach(function (e) {
    document.addEventListener(e, resetIdle, { passive: true });
  });
  document.body.addEventListener("htmx:afterRequest", resetIdle);
  resetIdle();

  // --- Kanban drag & drop --------------------------------------------------
  window.initKanban = function () {
    if (typeof Sortable === "undefined") return;
    const canChange = document.body.dataset.canChangeStatus === "1";
    document.querySelectorAll(".kanban .column").forEach(function (col) {
      const status = col.dataset.status;
      new Sortable(col.querySelector(".cards"), {
        group: "kanban",
        animation: 150,
        disabled: !canChange,
        ghostClass: "sortable-ghost",
        onEnd: function (evt) {
          if (!canChange) return;
          const card = evt.item;
          const newStatus = evt.to.closest(".column").dataset.status;
          const orderId = card.dataset.orderId;
          if (newStatus === card.dataset.status) return;
          fetch("/orders/" + orderId + "/status/", {
            method: "POST",
            headers: { "X-CSRFToken": CSRF, "Content-Type": "application/x-www-form-urlencoded" },
            body: "status=" + encodeURIComponent(newStatus),
          })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
              if (res.ok && res.d.ok) {
                card.dataset.status = newStatus;
              } else {
                alert((res.d && res.d.error) || "Не удалось изменить статус.");
                window.location.reload();
              }
            })
            .catch(function () { window.location.reload(); });
        },
      });
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelector(".kanban")) window.initKanban();
  });
})();

/* Dynamic participant-INN rows. Plain JS so it works inside HTMX-swapped
   cards (no framework init needed). Each row is an <input name="participant_inns">;
   the server collects them via request.POST.getlist(). */
function addParticipantRow(btn) {
  var wrap = btn.closest("[data-participants]");
  if (!wrap) return;
  var rows = wrap.querySelector(".participant-rows");
  var last = rows.querySelector(".participant-row:last-child");
  var row;
  if (last) {
    row = last.cloneNode(true);
  } else {
    row = document.createElement("div");
    row.className = "participant-row";
    row.innerHTML =
      '<input class="input" type="text" inputmode="numeric" name="participant_inns" ' +
      'placeholder="ИНН организации" autocomplete="off">' +
      '<button type="button" class="btn secondary sm" onclick="removeParticipantRow(this)" title="Убрать">✕</button>';
  }
  var input = row.querySelector("input");
  if (input) input.value = "";
  rows.appendChild(row);
  if (input) input.focus();
}

function removeParticipantRow(btn) {
  var wrap = btn.closest("[data-participants]");
  var rows = wrap ? wrap.querySelector(".participant-rows") : null;
  var row = btn.closest(".participant-row");
  if (!rows || !row) return;
  if (rows.querySelectorAll(".participant-row").length <= 1) {
    var input = row.querySelector("input");
    if (input) input.value = "";   // keep at least one (empty) row
  } else {
    row.remove();
  }
}
