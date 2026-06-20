/* Portal front-end glue: CSRF for HTMX, idle-timeout redirect, Kanban DnD,
   inline order card. */
var _cardDirty = false;        // unsaved changes in the open inline card
var _pendingAfterSave = null;  // action to run after a save we initiated

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
    var inOrg = e.target.closest && (e.target.closest(".org-options") || e.target.closest(".org-search"));
    if (!inOrg) {
      document.querySelectorAll(".org-options").forEach(function (o) { o.innerHTML = ""; });
    }
    var inFilter = e.target.closest && e.target.closest(".filter-combo");
    if (!inFilter) {
      document.querySelectorAll(".filter-options").forEach(function (o) { o.innerHTML = ""; });
    }
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

  // --- Inline card: react to content swapped into #card-block --------------
  document.body.addEventListener("htmx:afterSwap", function (e) {
    var t = e.detail && e.detail.target;
    if (!t || t.id !== "card-block") return;
    _cardDirty = false;                       // freshly loaded/saved -> clean
    if (_pendingAfterSave) {                   // a save we initiated just finished
      var fn = _pendingAfterSave; _pendingAfterSave = null; fn(); return;
    }
    try { t.scrollIntoView({ behavior: "smooth", block: "nearest" }); } catch (_) {}
  });

  // --- Track unsaved changes in the open card ------------------------------
  function _maybeDirty(e) {
    if (e.target.closest && e.target.closest("[data-card-form]")) _cardDirty = true;
  }
  document.body.addEventListener("input", _maybeDirty);
  document.body.addEventListener("change", _maybeDirty);

  // --- On load: auto-open the selected order's inline card -----------------
  document.addEventListener("DOMContentLoaded", function () {
    var tbody = document.getElementById("orders-tbody");
    var pk = tbody && tbody.dataset.selected;
    if (pk) {
      var row = document.getElementById("order-row-" + pk);
      if (row) { loadOrderCard(row, pk); try { row.scrollIntoView({ block: "center" }); } catch (_) {} }
    }
  });

  // --- Confirm transitions to «Произведён»/«Отмена» (TЗ — закрытие заказа) ---
  var DONE_LABELS = { produced: "Произведён", cancelled: "Отмена" };
  window.confirmDoneStatus = function (newStatus) {
    return window.confirm("Перевести заказ в статус «" + DONE_LABELS[newStatus] +
      "»? После этого заказ будет закрыт для редактирования.");
  };
  // Parses «ДД.ММ.ГГГГ» or ISO «ГГГГ-ММ-ДД» -> Date at midnight, or null.
  function _parseLocalDate(value) {
    var v = (value || "").trim();
    if (!v) return null;
    var m = v.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m) return new Date(parseInt(m[3], 10), parseInt(m[2], 10) - 1, parseInt(m[1], 10));
    var iso = v.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (iso) return new Date(parseInt(iso[1], 10), parseInt(iso[2], 10) - 1, parseInt(iso[3], 10));
    return null;
  }

  // Aggregate pre-submit checks for the order card.
  // Returns true to proceed, false to cancel htmx send.
  function _validateCardForm(form) {
    if (!form) return true;

    function innByName(n) {
      var h = form.querySelector('input.org-id[name="' + n + '"]');
      if (!h) return "";
      var c = h.closest("[data-org-combo]");
      return c ? (c.dataset.inn || "") : "";
    }

    // 1) Distributor != Potential User по ИНН
    var distInn = innByName("distributor_org");
    var potInn  = innByName("potential_user_org");
    if (distInn && potInn && distInn === potInn) {
      alert("Дистрибьютор и Потенциальный пользователь не могут иметь один и тот же ИНН.");
      return false;
    }

    // 1.1) Distributor != любой Комментарий по ИНН
    if (distInn) {
      var conflict = false;
      form.querySelectorAll('[data-participants] [data-org-combo]').forEach(function (c) {
        if (c.dataset.inn && c.dataset.inn === distInn) conflict = true;
      });
      if (conflict) {
        alert("Дистрибьютор не может совпадать по ИНН с организацией в поле «Комментарий».");
        return false;
      }
    }

    // 2) Прогнозируемая дата не может быть в прошлом.
    var dateInp = form.querySelector('input[name="forecast_date"]');
    if (dateInp && dateInp.value.trim()) {
      var d = _parseLocalDate(dateInp.value);
      if (d) {
        var today = new Date(); today.setHours(0, 0, 0, 0);
        d.setHours(0, 0, 0, 0);
        if (d < today) {
          alert("Прогнозируемая дата не может быть в прошлом.");
          try { dateInp.focus(); } catch (_) {}
          return false;
        }
      }
    }

    // 3) Пустой «Комментарий» — спросить про потенциального пользователя.
    return _confirmEmptyComment(form);
  }

  // Если в форме карточки нет выбранных «комментариев» (участников) — задаём
  // вопрос про потенциального пользователя. Возвращает true, если форму можно
  // отправлять дальше; false — отменить (пользователь должен заполнить ИНН).
  function _confirmEmptyComment(form) {
    if (!form) return true;
    var rows = form.querySelectorAll('input[name="participant_orgs"]');
    for (var i = 0; i < rows.length; i++) {
      if ((rows[i].value || "").trim()) return true;     // есть хотя бы один — ОК
    }
    var pot = form.querySelector('input[name="potential_user_org"]');
    var potValue = pot ? (pot.value || "").trim() : "";
    if (!potValue) {
      window.alert("Заполните «Потенциальный пользователь» либо добавьте хотя бы один ИНН в «Комментарий».");
      return false;
    }
    var sameAsUser = window.confirm(
      "Поле «Комментарий» пустое.\n\n" +
      "Конечный пользователь такой же, как «Потенциальный пользователь»?\n" +
      "ОК — подставить его в «Комментарий».\n" +
      "Отмена — добавить ИНН в «Комментарий» вручную."
    );
    if (sameAsUser) {
      var hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "participant_orgs";
      hidden.value = potValue;
      form.appendChild(hidden);
      return true;
    }
    window.alert("Добавьте хотя бы один ИНН в поле «Комментарий».");
    return false;
  }

  document.body.addEventListener("htmx:confirm", function (e) {
    var elt = e.detail.elt;

    // 1) Карточка заказа — все проверки перед сабмитом (даты, дубль ЮЛ,
    //    пустой комментарий).
    if (elt.matches && elt.matches("form[data-card-form]")) {
      if (!_validateCardForm(elt)) { e.preventDefault(); return; }
    }

    // 2) Подтверждение перевода в «Произведён»/«Отмена».
    var sel = null, newStatus = null, current = null;
    if (elt.matches && elt.matches("select.status-select")) {            // table inline
      sel = elt; newStatus = elt.value; current = elt.dataset.current;
    } else if (elt.matches && elt.matches("form[data-status-form]")) {   // order card save
      sel = elt.querySelector('select[name="status"]');
      if (sel) { newStatus = sel.value; current = elt.dataset.currentStatus; }
    } else {
      return;  // не статус — htmx продолжает
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

/* ===================== Inline order card (in the table) ===================== */
function _detailRow() { return document.getElementById("card-detail-row"); }
function _cardForm() { return document.querySelector("#card-block form[data-card-form]"); }

function _highlightRow(pk) {
  document.querySelectorAll(".order-row").forEach(function (r) { r.classList.remove("selected"); });
  if (pk) { var r = document.getElementById("order-row-" + pk); if (r) r.classList.add("selected"); }
}

function collapseCard() {
  var d = _detailRow();
  if (d) { d.hidden = true; d.dataset.openPk = ""; }
  var cb = document.getElementById("card-block");
  if (cb) cb.innerHTML = "";
  _cardDirty = false;
  _highlightRow(null);
}

function loadOrderCard(rowEl, pk) {
  var d = _detailRow();
  if (!d || !rowEl) return;
  rowEl.parentNode.insertBefore(d, rowEl.nextSibling);   // place under the row
  d.hidden = false;
  d.dataset.openPk = String(pk);
  _cardDirty = false;
  _highlightRow(pk);
  if (window.htmx) htmx.ajax("GET", "/orders/" + pk + "/card/", { target: "#card-block", swap: "innerHTML" });
}

/* If the open card has unsaved changes, ask to save; then run `proceed`. */
function guardUnsaved(proceed) {
  if (!_cardDirty) { proceed(); return; }
  if (window.confirm("Данные изменены. Сохранить перед закрытием?\n(ОК — сохранить, Отмена — закрыть без сохранения)")) {
    _cardDirty = false;
    var f = _cardForm();
    if (f && (f.requestSubmit || f.submit)) {
      _pendingAfterSave = proceed;                       // run after the save swaps in
      if (f.requestSubmit) f.requestSubmit();
      else f.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    } else { proceed(); }
  } else {
    _cardDirty = false;
    proceed();
  }
}

/* Row click: toggle the open card, or switch to another (guarding unsaved). */
function onRowClick(rowEl, pk) {
  var d = _detailRow();
  var openPk = d ? d.dataset.openPk : "";
  if (openPk === String(pk)) {
    guardUnsaved(collapseCard);                          // re-click -> collapse
  } else {
    guardUnsaved(function () { loadOrderCard(rowEl, pk); });  // switch
  }
}

function openNewOrderRow() {
  guardUnsaved(function () {
    var d = _detailRow(), tbody = document.getElementById("orders-tbody");
    if (!d || !tbody) return;
    tbody.appendChild(d);                                // to the bottom of the table
    d.hidden = false;
    d.dataset.openPk = "new";
    _cardDirty = false;
    _highlightRow(null);
    if (window.htmx) htmx.ajax("GET", "/orders/new/", { target: "#card-block", swap: "innerHTML" });
  });
}

function closeCardGuarded() { guardUnsaved(collapseCard); }

/* Dynamic participant-INN rows. Plain JS so it works inside HTMX-swapped
   cards (no framework init needed). Each row is an <input name="participant_inns">;
   the server collects them via request.POST.getlist(). */
/* Organization combobox: type INN -> dropdown of matches (with КПП) -> pick. */
function _portalCsrf() {
  var m = document.cookie.match(/(^|;)\s*csrftoken\s*=\s*([^;]+)/);
  return m ? decodeURIComponent(m[2]) : "";
}

function _markDirtyIfCard(el) {
  if (el && el.closest && el.closest("[data-card-form]")) _cardDirty = true;
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

/* Distributor combobox: smart search over the LOCAL directory by name or ИНН
   (admin-managed; not a DaData lookup). Picking reuses selectOrgOption() since
   the option markup / data attributes are identical. */
function _distributorFetch(combo, q) {
  var opts = combo ? combo.querySelector(".org-options") : null;
  if (!opts) return;
  opts.innerHTML = '<div class="org-option-msg muted">Загрузка…</div>';
  fetch("/directories/distributor-suggest/?q=" + encodeURIComponent(q || ""), {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  })
    .then(function (r) { return r.text(); })
    .then(function (html) { opts.innerHTML = html; })
    .catch(function () {
      opts.innerHTML = '<div class="org-option-msg err">Ошибка поиска дистрибьютора</div>';
    });
}

function distributorSearchInput(input) {
  var combo = input.closest("[data-org-combo]");
  var prev = _orgSearchTimers.get(input);
  if (prev) clearTimeout(prev);
  // Empty input -> show the full active list (same as on focus).
  _orgSearchTimers.set(input, setTimeout(function () {
    _distributorFetch(combo, (input.value || "").trim());
  }, 250));
}

/* On focus / click — show the whole active distributor list so the user can
   pick from a dropdown without typing anything. */
function distributorShowAll(input) {
  var combo = input.closest("[data-org-combo]");
  var opts = combo ? combo.querySelector(".org-options") : null;
  if (opts && opts.children.length === 0) _distributorFetch(combo, "");
}

/* Custom table-filter autocomplete. Unlike a native <datalist> (whose dropdown
   width is locked to the input width and truncates long values), this dropdown
   sizes itself to the longest option while the input keeps its column width.
   Option values come from the page's existing <datalist> (no backend change). */
function filterSuggest(input, datalistId) {
  var combo = input.closest(".filter-combo");
  var box = combo ? combo.querySelector(".filter-options") : null;
  var dl = document.getElementById(datalistId);
  if (!box || !dl) return;

  // Close any other open filter dropdown.
  document.querySelectorAll(".filter-options").forEach(function (o) {
    if (o !== box) o.innerHTML = "";
  });

  var q = (input.value || "").trim().toLowerCase();
  var seen = {};
  var matches = [];
  var opts = dl.querySelectorAll("option");
  for (var i = 0; i < opts.length; i++) {
    var v = opts[i].value;
    if (!v || seen[v]) continue;
    if (q && v.toLowerCase().indexOf(q) === -1) continue;
    seen[v] = 1;
    matches.push(v);
    if (matches.length >= 50) break;
  }

  box.innerHTML = "";
  matches.forEach(function (v) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "filter-option";
    b.textContent = v;
    b.onmousedown = function (e) { e.preventDefault(); };   // keep input focus
    b.onclick = function () {
      input.value = v;
      box.innerHTML = "";
      if (input.form) input.form.submit();
    };
    box.appendChild(b);
  });
}

/* Close the dropdown when focus leaves the field (option clicks use
   mousedown+preventDefault, so they don't trigger this). */
function filterBlur(input) {
  var combo = input.closest(".filter-combo");
  var box = combo ? combo.querySelector(".filter-options") : null;
  if (box) setTimeout(function () { box.innerHTML = ""; }, 120);
}

/* Clear a single column filter (the ✕ next to a chosen value). */
function clearFilter(btn) {
  var combo = btn.closest(".filter-combo");
  var input = combo ? combo.querySelector("input") : null;
  if (!input) return;
  input.value = "";
  if (input.form) input.form.submit();
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

  // Cross-field правила по ИНН (а не по pk): филиалы с одним ИНН и разными
  // КПП тоже считаются совпадением — это та же компания.
  var hid  = combo.querySelector(".org-id");
  var name = hid ? hid.name : "";

  function _innOf(twinHidden) {
    if (!twinHidden) return "";
    var c = twinHidden.closest("[data-org-combo]");
    return c ? (c.dataset.inn || "") : "";
  }

  if (orgId && inn) {
    // 1) Distributor <-> Potential User
    var pair = { distributor_org: "potential_user_org",
                 potential_user_org: "distributor_org" };
    if (pair[name]) {
      var twinHid = document.querySelector('input.org-id[name="' + pair[name] + '"]');
      if (_innOf(twinHid) === inn) {
        alert("Дистрибьютор и Потенциальный пользователь не могут иметь один и тот же ИНН.");
        return;
      }
    }

    // 2) Distributor <-> участник Комментария
    if (name === "distributor_org") {
      var hit = false;
      document.querySelectorAll('[data-participants] [data-org-combo]').forEach(function (c) {
        if (c.dataset.inn === inn) hit = true;
      });
      if (hit) {
        alert("Дистрибьютор не может совпадать по ИНН с организацией в поле «Комментарий».");
        return;
      }
    }
    if (combo.closest("[data-participants]")) {
      var dHid = document.querySelector('input.org-id[name="distributor_org"]');
      if (_innOf(dHid) === inn) {
        alert("Эта организация уже выбрана как Дистрибьютор. У дистрибьютора и участника «Комментария» не может быть один ИНН.");
        return;
      }
    }
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
  _markDirtyIfCard(combo);
}

/* Clear a single-field selection -> back to the INN search input. */
function orgComboClear(btn) {
  var combo = btn.closest("[data-org-combo]");
  if (!combo) return;
  _resetComboToSearch(combo);
  _markDirtyIfCard(combo);
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
  _markDirtyIfCard(wrap);
  var search = row.querySelector(".org-search");
  if (search) search.focus();
}

function removeParticipantRow(btn) {
  var wrap = btn.closest("[data-participants]");
  var rows = wrap ? wrap.querySelector(".participant-rows") : null;
  var row = btn.closest(".participant-row");
  if (!rows || !row) return;
  _markDirtyIfCard(wrap);
  if (rows.querySelectorAll(".participant-row").length <= 1) {
    var combo = row.querySelector("[data-org-combo]");
    if (combo) _resetComboToSearch(combo);   // keep at least one (empty) row
  } else {
    row.remove();
  }
}
