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

/* Alpine component for the order card's participants list (dynamic orgs). */
function participantsWidget(initial) {
  return {
    items: initial && initial.length ? initial.slice() : [""],
    add() { this.items.push(""); },
    remove(i) { this.items.splice(i, 1); if (!this.items.length) this.items.push(""); },
    get json() { return JSON.stringify(this.items.map(function (x) { return (x || "").trim(); }).filter(Boolean)); },
  };
}
