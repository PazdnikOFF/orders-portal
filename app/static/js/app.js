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

  // --- Close any open org-combobox dropdown when clicking elsewhere ----------
  document.addEventListener("click", function (e) {
    if (e.target.closest && (e.target.closest(".org-options") || e.target.closest(".org-search"))) return;
    document.querySelectorAll(".org-options").forEach(function (o) { o.innerHTML = ""; });
  });

  // --- Auto-dismiss flash messages after 5 seconds --------------------------
  function dismissMessages() {
    document.querySelectorAll(".messages li").forEach(function (li) {
      setTimeout(function () {
        li.style.transition = "opacity .4s";
        li.style.opacity = "0";
        setTimeout(function () { li.remove(); }, 400);
      }, 5000);
    });
  }
  document.addEventListener("DOMContentLoaded", dismissMessages);

  // --- When a card loads into the bottom block, expand it and scroll to it ---
  document.body.addEventListener("htmx:afterSwap", function (e) {
    var t = e.detail && e.detail.target;
    if (t && t.id === "card-block") {
      window.dispatchEvent(new CustomEvent("expand-card"));
      try { t.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (_) {}
    }
  });

  // --- Confirm transitions to «Произведён»/«Отмена» (TЗ — закрытие заказа) ---
  var DONE_LABELS = { produced: "Произведён", cancelled: "Отмена" };
  window.confirmDoneStatus = function (newStatus) {
    return window.confirm("Перевести заказ в статус «" + DONE_LABELS[newStatus] +
      "»? После этого заказ будет закрыт для редактирования.");
  };
  document.body.addEventListener("htmx:confirm", function (e) {
    var elt = e.detail.elt, sel = null, newStatus = null, current = null;
    if (elt.matches && elt.matches("select.status-select")) {            // table inline
      sel = elt; newStatus = elt.value; current = elt.dataset.current;
    } else if (elt.matches && elt.matches("form[data-status-form]")) {   // order card save
      sel = elt.querySelector('select[name="status"]');
      if (sel) { newStatus = sel.value; current = elt.dataset.currentStatus; }
    } else {
      return;  // not a status change — let htmx proceed
    }
    if ((newStatus === "produced" || newStatus === "cancelled") && newStatus !== current) {
      e.preventDefault();
      if (window.confirmDoneStatus(newStatus)) {
        e.detail.issueRequest();
      } else if (sel) {
        sel.value = current || "";   // revert the dropdown
      }
    }
  });

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
          if ((newStatus === "produced" || newStatus === "cancelled") &&
              !window.confirmDoneStatus(newStatus)) {
            window.location.reload();   // declined — put the card back
            return;
          }
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
/* Organization combobox: type INN -> dropdown of matches (with КПП) -> pick. */
function _portalCsrf() {
  var m = document.cookie.match(/(^|;)\s*csrftoken\s*=\s*([^;]+)/);
  return m ? decodeURIComponent(m[2]) : "";
}

var _orgSearchTimers = new WeakMap();

/* On input: if a full INN (10/12 digits) is typed, fetch matching orgs and
   show them in this row's dropdown. Plain fetch (no htmx) for reliability. */
function orgSearchInput(input) {
  var combo = input.closest("[data-org-combo]");
  var opts = combo ? combo.querySelector(".org-options") : null;
  if (!opts) return;

  var digits = (input.value.match(/\d/g) || []).join("");
  var prev = _orgSearchTimers.get(input);
  if (prev) clearTimeout(prev);

  if (digits.length !== 10 && digits.length !== 12) {
    opts.innerHTML = "";
    return;
  }
  _orgSearchTimers.set(input, setTimeout(function () {
    opts.innerHTML = '<div class="org-option-msg muted">Поиск…</div>';
    fetch("/directories/org-suggest/", {
      method: "POST",
      headers: {
        "X-CSRFToken": _portalCsrf(),
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: "inn=" + encodeURIComponent(digits),
    })
      .then(function (r) { return r.text(); })
      .then(function (html) { opts.innerHTML = html; })
      .catch(function () {
        opts.innerHTML = '<div class="org-option-msg err">Ошибка поиска организации</div>';
      });
  }, 450));
}

/* Pick an org: switch the combo to the read-only «chip» state (link to
   Rusprofile). Text can no longer be edited — only cleared/removed. */
function selectOrgOption(btn) {
  var combo = btn.closest("[data-org-combo]");
  if (!combo) return;
  var orgId = btn.dataset.orgId || "";
  var inn = btn.dataset.inn || "";

  // Within participants the SAME organization (ИНН+КПП = id) must not repeat.
  // Branches (same INN, different КПП) are different ids and are allowed.
  var participants = combo.closest("[data-participants]");
  if (participants && orgId) {
    var duplicate = false;
    participants.querySelectorAll("[data-org-combo] .org-id").forEach(function (h) {
      if (h.closest("[data-org-combo]") !== combo && h.value === orgId) duplicate = true;
    });
    if (duplicate) { alert("Эта организация уже добавлена в участники."); return; }
  }

  combo.querySelector(".org-id").value = orgId;
  combo.dataset.inn = inn;
  var link = combo.querySelector(".org-link");
  if (link) {
    link.textContent = btn.dataset.display || "";
    link.setAttribute("href", btn.dataset.rusprofile || "#");
    link.hidden = false;
  }
  var search = combo.querySelector(".org-search");
  if (search) { search.value = ""; search.hidden = true; }
  var clear = combo.querySelector(".org-clear");
  if (clear) clear.hidden = false;
  var opts = combo.querySelector(".org-options");
  if (opts) opts.innerHTML = "";
}

/* Clear a single-field selection -> back to the INN search input. */
function orgComboClear(btn) {
  var combo = btn.closest("[data-org-combo]");
  if (!combo) return;
  _resetComboToSearch(combo);
  var search = combo.querySelector(".org-search");
  if (search) search.focus();
}

function _resetComboToSearch(combo) {
  combo.querySelector(".org-id").value = "";
  delete combo.dataset.inn;
  var link = combo.querySelector(".org-link"); if (link) link.hidden = true;
  var clear = combo.querySelector(".org-clear"); if (clear) clear.hidden = true;
  var search = combo.querySelector(".org-search");
  if (search) { search.hidden = false; search.value = ""; }
  var opts = combo.querySelector(".org-options"); if (opts) opts.innerHTML = "";
}

function orgComboKeydown(e) {
  if (e.key !== "Enter") return;
  var combo = e.target.closest("[data-org-combo]");
  if (!combo) return;
  e.preventDefault();   // never submit the form from the search field on Enter
  var first = combo.querySelector(".org-options .org-option");
  if (first) selectOrgOption(first);   // confirm the first match
}

/* Dynamic participant rows — each row is its own org combobox. */
function addParticipantRow(btn) {
  var wrap = btn.closest("[data-participants]");
  if (!wrap) return;
  var rows = wrap.querySelector(".participant-rows");
  var last = rows.querySelector(".participant-row:last-child");
  if (!last) return;
  var row = last.cloneNode(true);
  var combo = row.querySelector("[data-org-combo]");
  if (combo) _resetComboToSearch(combo);
  rows.appendChild(row);
  var search = row.querySelector(".org-search");
  if (search) search.focus();
}

function removeParticipantRow(btn) {
  var wrap = btn.closest("[data-participants]");
  var rows = wrap ? wrap.querySelector(".participant-rows") : null;
  var row = btn.closest(".participant-row");
  if (!rows || !row) return;
  if (rows.querySelectorAll(".participant-row").length <= 1) {
    var combo = row.querySelector("[data-org-combo]");
    if (combo) _resetComboToSearch(combo);   // keep at least one (empty) row
  } else {
    row.remove();
  }
}
