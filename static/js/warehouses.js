/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر */
/* مستودعات وسجلات — سلوك النماذج: فتح/قفل الزر الأمبر، تحويل الوحدات
   (١ طن = ١٠٠٠ كجم)، اسم اليوم تلقائيًا (السبت/الأحد…)، مدة الصلاحية،
   وجملة التعبئة لكل نموذج لوحده. القوائم كلها كومبو متمثّم — لا قوائم بيضاء. */
(function () {
  "use strict";

  function json(id) {
    var el = document.getElementById(id);
    if (!el) return {};
    try { return JSON.parse(el.textContent || "{}"); }
    catch (err) { return {}; }
  }

  var ITEMS = json("whItemsData");           // {name: {unit, base, factor, id}}
  var UNIT_BASE = json("whUnitBaseData");    // {unit: [base, factor]}
  var CTX = json("whContext");               // {year, month, days_in_month}
  var AR = "٠١٢٣٤٥٦٧٨٩";
  var WEEKDAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];

  function toNum(text) {
    var s = String(text || "").trim();
    for (var i = 0; i < 10; i++) s = s.split(AR[i]).join(String(i));
    var n = parseFloat(s.replace(/٫/g, ".").replace(/,/g, ""));
    return isFinite(n) ? n : null;
  }

  function fmt(n) {
    if (n === null || !isFinite(n)) return "";
    var t = n.toLocaleString("ar-EG", { minimumFractionDigits: 0, maximumFractionDigits: 3 });
    return t;  /* الصحيحة صحيحة والكسور بكسورها — مطابقة لfmt_qty_trim */
  }

  function baseOf(unit) {
    var key = String(unit || "").trim();
    var row = UNIT_BASE[key];
    return row ? { base: row[0], factor: row[1] } : { base: key, factor: 1 };
  }

  /* فتح/قفل نماذج الزر الأمبر */
  [["whSupplierToggle", "whSupplierForm"], ["whWh1Toggle", "whWh1Form"]].forEach(function (pair) {
    var btn = document.getElementById(pair[0]);
    var form = document.getElementById(pair[1]);
    if (!btn || !form) return;
    btn.addEventListener("click", function () {
      var open = form.hidden;
      form.hidden = !open;
      form.classList.toggle("wh-open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        var first = form.querySelector("input:not([type=hidden])");
        if (first) first.focus();
      }
    });
  });

  /* اسم اليوم تلقائيًا لكل حقل input[name=day] مع تلميح .wh-day-hint */
  function weekdayName(year, month, day) {
    var d = new Date(year, month - 1, day);
    if (isNaN(d.getTime()) || d.getMonth() !== month - 1 || d.getDate() !== day) return "";
    return WEEKDAYS[d.getDay()];
  }

  Array.prototype.forEach.call(document.querySelectorAll("input[name=\"day\"]"), function (input) {
    var form = input.closest("form") || document;
    var hint = form.querySelector(".wh-day-hint");
    function refresh() {
      if (!hint) return;
      var day = toNum(input.value);
      if (day === null) { hint.textContent = ""; return; }
      var name = weekdayName(CTX.year, CTX.month, day);
      hint.textContent = name ? ("يوم " + day.toLocaleString("ar-EG") + " = " + name) : "يوم خارج الشهر";
    }
    input.addEventListener("input", refresh);
    input.addEventListener("change", refresh);
    refresh();
  });

  /* ١ مخازن: الصنف → وحدة التعامل + تحويل الكمية + مدة الصلاحية */
  var itemInput = document.getElementById("whItemName");
  var unitInput = document.getElementById("whUnitInput");
  var qtyInput = document.getElementById("whQty");
  var convHint = document.getElementById("whConvHint");

  function currentUnit() {
    if (!itemInput) return "";
    var info = ITEMS[itemInput.value.trim()];
    return info ? info.unit : (unitInput ? unitInput.value : "");
  }

  function refreshConv() {
    if (!convHint) return;
    var unit = currentUnit();
    var qty = qtyInput ? toNum(qtyInput.value) : null;
    if (!unit) { convHint.textContent = ""; return; }
    var meta = baseOf(unit);
    if (qty === null) {
      convHint.textContent = "التعامل بوحدة: " + unit;
      return;
    }
    if (meta.factor !== 1) {
      convHint.textContent = fmt(qty) + " " + unit + " = " + fmt(qty * meta.factor) + " " + meta.base;
    } else if (meta.base && meta.base !== unit) {
      convHint.textContent = fmt(qty) + " " + unit + " = " + fmt(qty * meta.factor) + " " + meta.base;
    } else {
      convHint.textContent = fmt(qty) + " " + unit + " — وحدة القاعدة هي نفسها";
    }
  }

  if (itemInput && unitInput) {
    itemInput.addEventListener("change", function () {
      var info = ITEMS[itemInput.value.trim()];
      if (info && info.unit) {
        unitInput.value = info.unit;
        unitInput.disabled = true;
      } else {
        unitInput.disabled = false;
      }
      refreshConv();
    });
  }
  if (qtyInput) qtyInput.addEventListener("input", refreshConv);
  if (unitInput) unitInput.addEventListener("change", refreshConv);
  refreshConv();

  /* مدة الصلاحية تلقائيًا */
  var prodInput = document.getElementById("date-prod_date");
  var expInput = document.getElementById("date-exp_date");
  var shelfHint = document.getElementById("whShelfHint");

  function parseDate(text) {
    var s = String(text || "").trim();
    for (var i = 0; i < 10; i++) s = s.split(AR[i]).join(String(i));
    var parts = s.split("/").map(function (p) { return parseInt(p, 10); });
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    return new Date(parts[2], parts[1] - 1, parts[0]);
  }

  function refreshShelf() {
    if (!shelfHint || !prodInput || !expInput) return;
    var d1 = parseDate(prodInput.value);
    var d2 = parseDate(expInput.value);
    if (!d1 || !d2) { shelfHint.textContent = ""; return; }
    var days = Math.round((d2 - d1) / 86400000);
    shelfHint.textContent = days >= 0
      ? "مدة الصلاحية: " + days.toLocaleString("ar-EG") + " يوم"
      : "تنبيه: الصلاحية قبل الإنتاج!";
  }
  if (prodInput && expInput) {
    prodInput.addEventListener("change", refreshShelf);
    expInput.addEventListener("change", refreshShelf);
    refreshShelf();
  }

  /* التغليف والحساب التلقائي: عدد العبوات × سعة العبوة + سائب = الكمية */
  var STORES = json("whStoresData");
  function storeIdByName(name) {
    for (var i = 0; i < STORES.length; i++) {
      if (STORES[i].name === name) return STORES[i].id;
    }
    return null;
  }

  function wirePackaging(root, hintSel) {
    var kindEl = root.querySelector('[name=pack_kind]');
    if (!kindEl) return;
    var countEl = root.querySelector('[name=pack_count]');
    var capEl = root.querySelector('[name=pack_capacity]');
    var looseEl = root.querySelector('[name=pack_loose]');
    var hint = hintSel ? document.querySelector(hintSel) : root.querySelector(".js-pack-hint");
    var qtyEl = root.querySelector('input[name=qty]');

    function isReal() {
      var k = kindEl.value.trim();
      return k && k !== "بدون تغليف";
    }
    function refresh() {
      var count = toNum(countEl ? countEl.value : null) || 0;
      var cap = toNum(capEl ? capEl.value : null) || 0;
      var loose = toNum(looseEl ? looseEl.value : null) || 0;
      var total = isReal() ? count * cap + loose : 0;
      var info = (itemInput && ITEMS[itemInput.value.trim()]) ? ITEMS[itemInput.value.trim()] : null;
      var unit = info ? info.unit : "";
      if (hint) {
        var bits = [];
        if (isReal() && count) {
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            (cap ? " × " + fmt(cap) + " " + unit : ""));
        }
        if (loose) bits.push(fmt(loose) + " " + unit + " سائب");
        hint.textContent = bits.join(" + ") + (total ? " = " + fmt(total) + " " + unit : "");
      }
      if (qtyEl) {
        if (total > 0) {
          qtyEl.value = fmt(total);
          qtyEl.readOnly = true;
        } else {
          qtyEl.readOnly = false;
        }
        refreshConv();
        SPLIT_REFRESH.forEach(function (fn) { fn(); });
      }
    }
    [kindEl, countEl, capEl, looseEl].forEach(function (el) {
      if (!el) return;
      el.addEventListener("input", refresh);
      el.addEventListener("change", refresh);
    });
    kindEl.addEventListener("change", function () {
      var name = itemInput ? itemInput.value.trim() : "";
      var specs = (ITEMS[name] || {}).packs || {};
      var remembered = specs[kindEl.value.trim()];
      if (remembered && capEl && !capEl.value) {
        capEl.value = remembered.toLocaleString("ar-EG", { maximumFractionDigits: 3 });
      }
      refresh();
    });
    refresh();
  }

  var wh1Form = document.getElementById("whWh1Form");
  if (wh1Form) wirePackaging(wh1Form, "#whPackHint");
  wirePackaging(document, null);

  /* توزيع الكمية على المخازن — صناديق متعددة (١ مخازن + رصيد أول المدة) بكومبو متمثّم */
  var SPLIT_REFRESH = [];

  function wireSplitBox(box) {
    var rows = box.querySelector(".js-split-rows");
    var add = box.querySelector(".js-split-add");
    var hint = box.querySelector(".js-split-hint");
    if (!rows || !add || rows.dataset.wired) return;
    rows.dataset.wired = "1";
    var form = box.closest("form");
    var qtyEl = form ? form.querySelector("input[name=qty]") : null;

    function splitSum() {
      var sum = 0, any = false;
      Array.prototype.forEach.call(
        rows.querySelectorAll('[name=store_qty]'), function (el) {
          var n = toNum(el.value);
          if (n && n > 0) { sum += n; any = true; }
        });
      return any ? sum : null;
    }

    function refresh() {
      if (!hint) return;
      var sum = splitSum();
      var qty = qtyEl ? toNum(qtyEl.value) : null;
      if (sum === null) { hint.textContent = ""; return; }
      hint.textContent = "مجموع التوزيع: " + fmt(sum) +
        (qty !== null ? (Math.abs(sum - qty) < 0.0001
          ? " — يطابق الكمية ✓"
          : " — لا يطابق الكمية (" + fmt(qty) + ")!") : "");
    }
    SPLIT_REFRESH.push(refresh);

    function addRow() {
      var row = document.createElement("div");
      row.className = "wh-split-row";
      row.innerHTML =
        '<input type="hidden" name="store_id" value="">' +
        '<input name="store_name" data-combo="whStoresList" autocomplete="off" placeholder="اختر المخزن">' +
        '<input name="store_qty" inputmode="decimal" autocomplete="off" placeholder="الكمية">' +
        '<button type="button" class="icon-btn del js-split-del" title="إزالة المخزن">' +
        '<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>';
      rows.appendChild(row);
      if (window.LogisticsCombo) window.LogisticsCombo.enhance(row);
      row.querySelector('[name=store_name]').addEventListener("change", function () {
        row.querySelector('[name=store_id]').value = storeIdByName(this.value) || "";
        refresh();
      });
      row.querySelector('[name=store_qty]').addEventListener("input", refresh);
      row.querySelector(".js-split-del").addEventListener("click", function () {
        row.remove();
        refresh();
      });
      refresh();
    }

    add.addEventListener("click", addRow);
    if (box.dataset.autoRow === "1" && !rows.children.length) addRow();
    refresh();
  }

  Array.prototype.forEach.call(document.querySelectorAll(".js-split-box"), wireSplitBox);

  /* مدة الصلاحية تلقائيًا — لكل نموذج (١ مخازن + رصيد أول المدة) */
  function parseDate(text) {
    var t = String(text || "").trim();
    for (var i = 0; i < 10; i++) t = t.split(AR[i]).join(String(i));
    var parts = t.split("/").map(function (p) { return parseInt(p, 10); });
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    return new Date(parts[2], parts[1] - 1, parts[0]);
  }

  function wireShelf(form) {
    var prod = form.querySelector('[name=prod_date]');
    var exp = form.querySelector('[name=exp_date]');
    var hint = form.querySelector(".js-shelf-hint");
    if (!prod || !exp || !hint || prod.dataset.shelfWired) return;
    prod.dataset.shelfWired = "1";
    function refresh() {
      var d1 = parseDate(prod.value), d2 = parseDate(exp.value);
      if (!d1 || !d2) { hint.textContent = ""; return; }
      var days = Math.round((d2 - d1) / 86400000);
      hint.textContent = days >= 0
        ? "مدة الصلاحية: " + days.toLocaleString("ar-EG") + " يوم"
        : "تنبيه: الصلاحية قبل الإنتاج!";
    }
    prod.addEventListener("change", refresh);
    exp.addEventListener("change", refresh);
    refresh();
  }
  Array.prototype.forEach.call(document.querySelectorAll("form"), wireShelf);
})();
