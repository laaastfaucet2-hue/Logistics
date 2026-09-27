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
  var SPLIT_REFRESH = [];   // يجب أن يُعرَّف قبل wirePackaging — استدعاء refresh المباشر يستخدمه
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

  /* فتح/قفل نماذج الزر الأمبر + فورمات رصيد أول المدة (توجيه ٢٦/٠٩: قائمة تفتح وتقفل) */
  [["whSupplierToggle", "whSupplierForm"], ["whWh1Toggle", "whWh1Form"],
   ["whOpenerToggle", "whOpenerForm"], ["whOpenerNewToggle", "whOpenerNewForm"]].forEach(function (pair) {
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

  /* كارت صنف: الصنف → وحدة التعامل + تحويل الكمية (لإذن ١ مخازن متعدد الأصناف) */
  function wireLine(card) {
    var itemInput = card.querySelector(".js-item-name");
    var unitInput = card.querySelector(".js-unit");
    var qtyInput = card.querySelector('input[name$="_qty"]');
    var convHint = card.querySelector(".js-conv-hint");
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
      if (qty === null) { convHint.textContent = "التعامل بوحدة: " + unit; return; }
      if (meta.base && meta.base !== unit) {
        convHint.textContent = fmt(qty) + " " + unit + " = " + fmt(qty * meta.factor) + " " + meta.base;
      } else {
        convHint.textContent = fmt(qty) + " " + unit + " — وحدة القاعدة هي نفسها";
      }
    }
    if (itemInput && unitInput) {
      itemInput.addEventListener("change", function () {
        var info = ITEMS[itemInput.value.trim()];
        if (info && info.unit) { unitInput.value = info.unit; unitInput.disabled = true; }
        else { unitInput.disabled = false; }
        refreshConv();
      });
    }
    if (qtyInput) qtyInput.addEventListener("input", refreshConv);
    if (unitInput) unitInput.addEventListener("change", refreshConv);
    refreshConv();
  }
  Array.prototype.forEach.call(document.querySelectorAll(".wh-item-card"), wireLine);

  /* إضافة/حذف كارت صنف (إذن ١ مخازن متعدد الأصناف — توجيه ٢٧/٠٩) */
  function wireLineCard(card) {
    wireLine(card);
    wirePackaging(card, null);
    Array.prototype.forEach.call(card.querySelectorAll(".js-split-box"), wireSplitBox);
    wireShelfCard(card);
    var del = card.querySelector(".js-line-del");
    if (del && !del.dataset.wired) {
      del.dataset.wired = "1";
      del.addEventListener("click", function () {
        card.remove();
        renumberLines();
      });
    }
  }
  function renumberLines() {
    Array.prototype.forEach.call(document.querySelectorAll("#whItemLines .wh-item-card"),
      function (card, idx) {
        var t = card.querySelector(".js-line-title");
        if (t) t.textContent = "الصنف " + (idx + 1).toLocaleString("ar-EG");
        var prefix = "l" + idx + "_";
        card.dataset.linePrefix = prefix;
        Array.prototype.forEach.call(card.querySelectorAll("[name]"), function (el) {
          if (/^l\d+_/.test(el.name)) el.name = prefix + el.name.replace(/^l\d+_/, "");
        });
      });
  }
  var addLineBtn = document.getElementById("whAddLine");
  var lineBox = document.getElementById("whItemLines");
  if (addLineBtn && lineBox) {
    addLineBtn.addEventListener("click", function () {
      var tpl = document.getElementById("whLineTpl");
      if (!tpl) return;
      var idx = lineBox.querySelectorAll(".wh-item-card").length;
      var html = tpl.innerHTML.split("__IDX__").join(String(idx));
      var holder = document.createElement("div");
      holder.innerHTML = html;
      var card = holder.firstElementChild;
      lineBox.appendChild(card);
      wireLineCard(card);
      if (window.LogisticsCombo) window.LogisticsCombo.enhance(card);
      renumberLines();
      var first = card.querySelector(".js-item-name");
      if (first) first.focus();
    });
    if (!lineBox.children.length) addLineBtn.click();
  }

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
    /* كارت صنف إذن ١ مخازن: الحقول ل0_pack_kind… — نختار باللاحقة داخل الكارت */
    var scoped = !!(root.classList && root.classList.contains("wh-item-card"));
    function sfx(name) {
      return scoped ? '[name$="_' + name + '"]' : '[name=' + name + ']';
    }
    var kindEl = root.querySelector(sfx("pack_kind"));
    if (!kindEl) return;
    var countEl = root.querySelector(sfx("pack_count"));
    var capEl = root.querySelector(sfx("pack_capacity"));
    var innerTog = root.querySelector(".js-inner-toggle");
    var innerRow = root.querySelector(".js-inner-row");
    var innerCountEl = root.querySelector(sfx("pack_inner_count"));
    var innerCapEl = root.querySelector(sfx("pack_inner_capacity"));
    var innerSum = root.querySelector(".js-inner-sum");
    var looseEl = root.querySelector(sfx("pack_loose"));
    var looseUnitEl = root.querySelector(sfx("pack_loose_unit"));
    var diffEl = root.querySelector(".js-pack-diff");
    var hint = hintSel ? document.querySelector(hintSel) : root.querySelector(".js-pack-hint");
    var qtyEl = root.querySelector("input" + sfx("qty"));
    var localItem = root.querySelector(sfx("item_name"));

    /* الصنف: من حقل النموذج نفسه، أو اسم كارت الصنف (data-item-name)، أو حقل ١ مخازن */
    function currentInfo() {
      var name = "";
      if (root.dataset && root.dataset.itemName) name = root.dataset.itemName;
      else if (localItem) name = localItem.value.trim();
      else if (itemInput) name = itemInput.value.trim();
      return name ? (ITEMS[name] || null) : null;
    }

    function isReal() {
      var k = kindEl.value.trim();
      return k && k !== "بدون تغليف";
    }

    function innerOn() {
      if (innerTog) return innerTog.checked;
      return !!(innerCountEl && (innerCountEl.value || (innerCapEl && innerCapEl.value)));
    }

    function boxWord(n) { return (n >= 3 && n <= 10) ? "علب" : "علبة"; }

    if (innerTog) {
      innerTog.addEventListener("change", function () {
        if (innerRow) innerRow.hidden = !innerTog.checked;
        if (!innerTog.checked) {
          if (innerCountEl) innerCountEl.value = "";
          if (innerCapEl) innerCapEl.value = "";
        }
        refresh();
      });
    }

    function refresh() {
      var count = toNum(countEl ? countEl.value : null) || 0;
      var cap = toNum(capEl ? capEl.value : null) || 0;
      var ic = innerOn() ? (toNum(innerCountEl ? innerCountEl.value : null) || 0) : 0;
      var ica = innerOn() ? (toNum(innerCapEl ? innerCapEl.value : null) || 0) : 0;
      var loose = toNum(looseEl ? looseEl.value : null) || 0;
      var lu = (looseUnitEl && looseUnitEl.value.trim()) || "";
      var looseBoxes = lu.indexOf("علب") === 0;
      var info = currentInfo();
      var unit = info ? info.unit : "";

      /* حاصل العلب + الفرق: الكرتونة كام مقابل عدد العلب × وزن العلبة */
      if (innerSum) {
        innerSum.textContent = (ic && ica)
          ? fmt(ic) + " " + boxWord(ic) + " × " + fmt(ica) + " " + unit +
            " = " + fmt(ic * ica) + " " + unit : "";
      }
      if (diffEl) {
        diffEl.textContent = "";
        diffEl.classList.remove("bad", "good");
        if (cap && ic && ica) {
          var sub = ic * ica, d = cap - sub;
          if (Math.abs(d) > 0.001) {
            diffEl.textContent = "⚠️ في فرق: العبوة " + fmt(cap) + " " + unit +
              " والعلب " + fmt(ic) + " × " + fmt(ica) + " = " + fmt(sub) + " " + unit +
              " — الفرق " + fmt(Math.abs(d)) + " " + unit + " — صحّح اللي متأكد منه";
            diffEl.classList.add("bad");
          } else {
            diffEl.textContent = "✓ العلب مطابقة لوزن العبوة (" + fmt(sub) + " " + unit + ")";
            diffEl.classList.add("good");
          }
        }
      }

      var bits = [], total = 0;
      if (isReal() && count) {
        if (cap) {
          /* وزن العبوة هو المرجع: ١٠ كرتونة × وزن الكرتونة ١٢ كجم = ١٢٠ كجم */
          var sub2 = count * cap;
          total += sub2;
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            " × وزن ال" + kindEl.value.trim() + " " + fmt(cap) + " " + unit +
            " = " + fmt(sub2) + " " + unit +
            (ic && ica ? " (بداخلها " + fmt(ic) + " " + boxWord(ic) + " × " +
              fmt(ica) + " " + unit + ")" : ""));
        } else if (ic && ica) {
          var cw = ic * ica, sub3 = count * cw;
          total += sub3;
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            " بداخلها " + fmt(ic) + " " + boxWord(ic) + " × وزن العلبة " +
            fmt(ica) + " " + unit + " = " + fmt(sub3) + " " + unit);
        } else {
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim());
        }
      }
      if (loose) {
        if (looseBoxes && ica) {
          var lk = loose * ica;
          total += lk;
          bits.push(fmt(loose) + " " + boxWord(loose) + " × " + fmt(ica) + " " +
            unit + " = " + fmt(lk) + " " + unit + " سائب");
        } else if (looseBoxes && !ica) {
          bits.push("السائب بالعلب محتاج وزن العلبة!");
        } else {
          total += loose;
          bits.push(fmt(loose) + " " + unit + " سائب");
        }
      }
      if (hint) {
        hint.textContent = bits.join(" + ") +
          (bits.length > 1 && total ? " = " + fmt(total) + " " + unit : "");
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

    [kindEl, countEl, capEl, innerCountEl, innerCapEl, looseEl, looseUnitEl]
      .forEach(function (el) {
        if (!el) return;
        el.addEventListener("input", refresh);
        el.addEventListener("change", refresh);
      });

    kindEl.addEventListener("change", function () {
      var info2 = currentInfo();
      var specs = (info2 && info2.packs) || {};
      var remembered = specs[kindEl.value.trim()];
      if (remembered) {
        if (capEl && !capEl.value && remembered.capacity) {
          capEl.value = remembered.capacity.toLocaleString("ar-EG", { maximumFractionDigits: 3 });
        }
        if (remembered.inner_count && remembered.inner_capacity) {
          if (innerTog && !innerTog.checked) {
            innerTog.checked = true;
            if (innerRow) innerRow.hidden = false;
          }
          if (innerCountEl && !innerCountEl.value) {
            innerCountEl.value = remembered.inner_count.toLocaleString("ar-EG",
              { maximumFractionDigits: 3 });
          }
          if (innerCapEl && !innerCapEl.value) {
            innerCapEl.value = remembered.inner_capacity.toLocaleString("ar-EG",
              { maximumFractionDigits: 3 });
          }
        }
      }
      refresh();
    });
    refresh();
  }

  wirePackaging(document, null);   /* احتياط للنماذج القديمة — الكروت تُربط في wireLineCard */

  /* توزيع الكمية على المخازن — صناديق متعددة (١ مخازن + رصيد أول المدة) بكومبو متمثّم */

  function wireSplitBox(box) {
    var rows = box.querySelector(".js-split-rows");
    var add = box.querySelector(".js-split-add");
    var hint = box.querySelector(".js-split-hint");
    if (!rows || !add || rows.dataset.wired) return;
    rows.dataset.wired = "1";
    var card = box.closest(".wh-item-card");
    var prefix = card ? card.getAttribute("data-line-prefix") || "" : "";
    var form = box.closest("form");
    var qtyEl = card ? card.querySelector('input[name$="_qty"]')
                     : (form ? form.querySelector("input[name=qty]") : null);

    function splitSum() {
      var sum = 0, any = false;
      Array.prototype.forEach.call(
        rows.querySelectorAll('[name="' + prefix + 'store_qty"]'), function (el) {
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
        '<input type="hidden" name="' + prefix + 'store_id" value="">' +
        '<input name="' + prefix + 'store_name" data-combo="whStoresList" autocomplete="off" placeholder="اختر المخزن">' +
        '<input name="' + prefix + 'store_qty" inputmode="decimal" autocomplete="off" placeholder="الكمية">' +
        '<button type="button" class="icon-btn del js-split-del" title="إزالة المخزن">' +
        '<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>';
      rows.appendChild(row);
      if (window.LogisticsCombo) window.LogisticsCombo.enhance(row);
      row.querySelector('[name="' + prefix + 'store_name"]').addEventListener("change", function () {
        row.querySelector('[name="' + prefix + 'store_id"]').value = storeIdByName(this.value) || "";
        refresh();
      });
      row.querySelector('[name="' + prefix + 'store_qty"]').addEventListener("input", refresh);
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

  function wireShelfCard(card) {
    var prod = card.querySelector('[name$="_prod_date"]');
    var exp = card.querySelector('[name$="_exp_date"]');
    var hint = card.querySelector(".js-shelf-hint");
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
  Array.prototype.forEach.call(document.querySelectorAll(".wh-item-card"), wireShelfCard);

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

/* نوافذ التفاريد المنبثقة: فتح من أي سطر/زر، وإغلاق بزر أو Esc أو الضغط بالخارج */
document.addEventListener("click", function (ev) {
    var openBtn = ev.target.closest("[data-taf-open]");
    if (openBtn) {
      var dlg = document.getElementById(openBtn.getAttribute("data-taf-open"));
      if (dlg && dlg.showModal) { dlg.showModal(); }
      return;
    }
    var closeBtn = ev.target.closest("[data-taf-close]");
    if (closeBtn) {
      var d2 = document.getElementById(closeBtn.getAttribute("data-taf-close"));
      if (d2 && d2.close) d2.close();
      return;
    }
    if (ev.target instanceof HTMLDialogElement) ev.target.close();  /* ضغط بالخارج */
  });

/* التابات الفرعية (٢ و٣ مخازن): تبديل بلا إعادة تحميل */
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-wh2sub],[data-wh3sub]");
  if (!btn) return;
  var scope = btn.closest(".panel");
  if (!scope) return;
  var sub = btn.hasAttribute("data-wh2sub") ? "data-wh2sub" : "data-wh3sub";
  var pan = btn.hasAttribute("data-wh2sub") ? "data-wh2panel" : "data-wh3panel";
  Array.prototype.forEach.call(scope.querySelectorAll("[" + sub + "]"), function (b) {
    b.classList.toggle("active", b === btn);
  });
  Array.prototype.forEach.call(scope.querySelectorAll("[" + pan + "]"), function (p) {
    p.hidden = p.getAttribute(pan) !== btn.getAttribute(sub);
  });
});
