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
  /* التصنيف الرسمي (توجيه ٢٧/٠٩): الوزن والحجم بس هوما اللي بيتحولوا —
     كجم/جم/جرام/طن → كجم، ولتر/مل → لتر. أي معيار تاني بيُعدّ بالعدد زي ما هو. */
  function isMeasureUnit(u) {
    var b = baseOf(u).base;
    return b === "كجم" || b === "لتر";
  }
  function unitModeWord(u) {
    return isMeasureUnit(u) ? "وزن/حجم — الحسبة بالكيلو أو اللتر" : "بيُعدّ بالعدد";
  }

  /* رسّام العبوات: أيقونة SVG لكل عبوة/وحدة — الشاشة الحية بترسم بيها (توجيه ٢٧/٠٩) */
  var ICON_RULES = [["كجم", "weight"], ["جرام", "weight"], ["جم", "weight"], ["طن", "weight"],
    ["كرتون", "carton"], ["ارتون", "carton"], ["شكار", "sack"], ["شيكار", "sack"], ["بلت", "pallet"],
    ["جركن", "jerrycan"], ["برميل", "barrel"], ["زجاج", "bottle"], ["لتر", "bottle"],
    ["مل", "bottle"], ["كيس", "bag"], ["شنط", "bag"], ["صيني", "tray"], ["طبق", "tray"],
    ["كوب", "cup"], ["ربط", "bundle"], ["فتل", "bundle"], ["باكت", "packet"],
    ["علب", "box"], ["عبو", "box"]];
  var ICON_PATHS = {
    carton: '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/>',
    box: '<rect x="4" y="7" width="16" height="13" rx="2"/><path d="M4 12h16M12 7v13"/>',
    packet: '<rect x="6" y="4" width="12" height="16" rx="2"/><path d="M6 9h12M9 13h6"/>',
    sack: '<path d="M10 3h4l1.2 2.6C17.5 7.5 19 10 19 13a7 6.5 0 0 1-14 0c0-3 1.5-5.5 3.8-7.4z"/><path d="M9.5 5.5h5"/>',
    pallet: '<rect x="3" y="3" width="7" height="6" rx="1"/><rect x="13" y="3" width="7" height="6" rx="1"/><rect x="8" y="11" width="8" height="6" rx="1"/><path d="M3 20h18M4 17h16"/>',
    jerrycan: '<rect x="5" y="6" width="14" height="14" rx="2"/><path d="M8 6V4h8v2"/><path d="M9 11h6v5H9z"/>',
    barrel: '<ellipse cx="12" cy="5.5" rx="7" ry="2.5"/><path d="M5 5.5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-13"/><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
    bottle: '<path d="M10 2h4v3l2 3v12a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V8l2-3z"/><path d="M8 13h8"/>',
    bag: '<path d="M6 8h12l1.5 12a1.8 1.8 0 0 1-1.8 2H6.3a1.8 1.8 0 0 1-1.8-2z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    tray: '<rect x="3" y="8" width="18" height="10" rx="2"/><path d="M9 8v10M15 8v10"/>',
    cup: '<path d="M6 4h12l-1.5 16a2 2 0 0 1-2 1.8h-5A2 2 0 0 1 7.5 20z"/><path d="M6.5 9h11"/>',
    bundle: '<path d="M7 4v16M12 3v18M17 4v16"/><path d="M5 8h14M5 16h14"/>',
    weight: '<path d="M9 7a3 3 0 0 1 6 0"/><path d="M12 7l7 13H5z"/>'
  };
  /* صور العبوات الحقيقية (ستايل أيزومتريك معتمد من المستخدم) + SVG احتياطي
     لأي مفتاح مش موجود له صورة بعد — الشاشة الحية بترسم بيها (توجيه ٢٧/٠٩) */
  var PACK_IMG = ["carton", "weight", "pouch", "bottle", "jerrycan",
    "barrel", "bag", "tray", "cup", "bundle"];
  var IMG_ALIAS = { packet: "pouch", box: "can" };
  function packIcon(name, size) {
    var n = String(name || ""), key = "box";
    for (var i = 0; i < ICON_RULES.length; i++) {
      if (n.indexOf(ICON_RULES[i][0]) !== -1) { key = ICON_RULES[i][1]; break; }
    }
    var img = IMG_ALIAS[key] || key;
    if (PACK_IMG.indexOf(img) !== -1) {
      return '<img class="wh-pack-img" src="/static/img/pack/' + img +
        '.png" width="' + size + '" height="' + size + '" alt="">';
    }
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none"' +
      ' stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
      ICON_PATHS[key] + "</svg>";
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
    /* حذف الصنف بتفويض الأحداث على الحاوية — يشتغل دايمًا حتى لو فشل ربط الكارت */
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
  if (lineBox && !lineBox.dataset.delDelegated) {
    lineBox.dataset.delDelegated = "1";
    lineBox.addEventListener("click", function (e) {
      var del = e.target.closest ? e.target.closest(".js-line-del") : null;
      if (!del) return;
      var card = del.closest(".wh-item-card");
      if (card) { card.remove(); renumberLines(); }
    });
  }
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
      /* خطأ كارت واحد لا يوقف ربط الباقي — التحذير في الكونسول */
      try { wireLineCard(card); }
      catch (err) { if (window.console && console.warn) console.warn("كارت صنف:", err); }
      try { if (window.LogisticsCombo) window.LogisticsCombo.enhance(card); }
      catch (err) { if (window.console && console.warn) console.warn("كومبو الكارت:", err); }
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
    var innerKindEl = root.querySelector(sfx("pack_inner_kind"));
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

    /* التسميات الذكية: كل كلمة على الشاشة من المستخدم نفسه —
       بلتة → عدد البلتات/كم تحتوي البلتة من الباكيت (مثال ١) —
       كارتونة كبيرة → كم كارتونة كبيرة؟/كم تحتويها من الكارتونة الصغيرة؟ (مثال ٢) */
    function plural(kind) {
      kind = (kind || "").trim();
      if (!kind) return "";
      return kind.slice(-1) === "ة" ? kind.slice(0, -1) + "ات" : kind + "ات";
    }
    function dynLabels() {
      var kind = (kindEl.value || "").trim();
      var inner = innerKindEl ? (innerKindEl.value || "").trim() : "";
      var km = kind.indexOf(" ") !== -1;     /* اسم من كمتين: كارتونة كبيرة */
      var im = inner.indexOf(" ") !== -1;
      var kDef = km ? kind : (kind ? "ال" + kind : "");
      function set(cls, txt) {
        var el = root.querySelector(cls);
        if (el) el.textContent = txt;
      }
      set(".js-inner-kind-lbl", kind ? "نوع المعيار داخل " + kDef + "؟" : "نوع المعيار داخل العبوة؟");
      var capRow = innerCapEl ? innerCapEl.closest(".wh-f") : null;
      if (capRow) {
        capRow.hidden = isMeasureUnit(inner);   /* كجم ما لهوش «وزن واحد» — الحقل يختفي */
      }
      var modeEl = root.querySelector(".js-inner-mode-hint");
      if (modeEl) {
        modeEl.textContent = inner ? "📌 «" + inner + "» " + unitModeWord(inner) : "";
      }
      set(".js-count-lbl", !kind ? "عدد العبوات" : (km ? "كم " + kind + "؟" : "عدد ال" + plural(kind)));
      if (inner) {
        /* صياغة المستخدم: «كم عدد العلب في الكارتونة؟» (توجيه ٢٧/٠٩) */
        set(".js-inner-count-lbl", "كم " + inner + " في " + (kind ? (km ? kind : kDef) : "العبوة") + "؟");
      } else {
        set(".js-inner-count-lbl", "كم علبة في العبوة؟");
      }
      set(".js-inner-cap-lbl", inner ? (im ? "وزن " + inner + " الواحد" : "وزن ال" + inner + " الواحد") : "وزن العلبة الواحدة");
      set(".js-cap-lbl", kind ? "وزن " + (km ? kind : kDef) + " الواحدة كاملة؟" : "وزن العبوة الواحدة كاملة؟");
    }
    dynLabels();

    /* قوالب جاهزة من ذاكرتك: ضغطة واحدة تتملي المعادلة كلها (توجيه ٢٧/٠٩) */
    var presetsBox = root.querySelector(".js-pack-presets");
    function renderPresets() {
      if (!presetsBox) return;
      var info = currentInfo();
      var packs = (info && info.packs) || {};
      var keys = Object.keys(packs);
      if (!keys.length) { presetsBox.hidden = true; presetsBox.innerHTML = ""; return; }
      presetsBox.hidden = false;
      presetsBox.innerHTML = "";
      keys.forEach(function (k) {
        var sp = packs[k] || {};
        var txt = k + " " + (sp.capacity ? "× " + Number(sp.capacity).toLocaleString("ar-EG", { maximumFractionDigits: 3 }) : "");
        if (sp.inner_count) {
          txt += " بداخلها " + Number(sp.inner_count).toLocaleString("ar-EG", { maximumFractionDigits: 3 })
            + (sp.inner_kind ? " " + sp.inner_kind : "");
        }
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "pack-chip preset";
        chip.textContent = "⭐ " + txt;
        chip.addEventListener("click", function (e) {
          e.preventDefault();
          if (kindEl) kindEl.value = k;
          if (capEl && sp.capacity) capEl.value = Number(sp.capacity).toLocaleString("ar-EG", { maximumFractionDigits: 3 });
          if (innerKindEl) innerKindEl.value = sp.inner_kind || "";
          if (innerCountEl && sp.inner_count) innerCountEl.value = Number(sp.inner_count).toLocaleString("ar-EG", { maximumFractionDigits: 3 });
          if (innerCapEl && sp.inner_capacity) innerCapEl.value = Number(sp.inner_capacity).toLocaleString("ar-EG", { maximumFractionDigits: 3 });
          dynLabels(); reveal(); refresh();
        });
        presetsBox.appendChild(chip);
      });
    }
    function renderPresetsSafe() {
      try { renderPresets(); } catch (err) {}
    }

    /* الكشف التدريجي: كل إجابة تفتح السؤال اللي بعدها — والسائب خلف زراره */
    var countCell = root.querySelector(".js-count-cell");
    var innerCountCell = root.querySelector(".js-innercount-cell");
    var innerCapCell = root.querySelector(".js-innercap-cell");
    var looseRow = root.querySelector(".js-loose-row");
    var looseToggle = root.querySelector(".js-loose-toggle");
    var eqTotal = root.querySelector(".js-eq-total");
    var tvEl = root.querySelector(".js-tv");

    /* 📺 الشاشة الحية: كل معلومة بتكتبها تترسم فورًا — مثل أدوات التغليف المحترفة */
    function brandLines() {
      var form = root.closest ? root.closest("form") : null;
      var sup = form ? (form.querySelector('[name="supplier_name"]') || {}) : {};
      var pro = form ? (form.querySelector('[name="producer"]') || {}) : {};
      var itEl = localItem || root.querySelector(".js-item-name");
      var it = itEl ? itEl.value.trim() : "";
      var bits = [];
      if ((sup.value || "").trim()) bits.push((sup.value).trim());
      if ((pro.value || "").trim()) bits.push((pro.value).trim());
      if (it) bits.push(it);
      return bits.join(" — ");
    }
    function drawTV(total, unitCount, tword, wUnit, cap, ica) {
      if (!tvEl) return;
      var k = kindEl.value.trim();
      var ik = innerKindEl ? innerKindEl.value.trim() : "";
      var cnt = toNum(countEl ? countEl.value : null) || 0;
      var ic = toNum(innerCountEl ? innerCountEl.value : null) || 0;
      var lo = toNum(looseEl ? looseEl.value : null) || 0;
      if (!k && !ik && !lo) {
        tvEl.innerHTML = '<span class="wh-tv-empty">📺 اكتب نوع العبوة — والشاشة هترسم قصة التغليف قدامك خطوة بخطوة</span>';
        return;
      }
      var wchip = function (w) { return w > 0 ? ' <span class="wh-tv-w">· ' + fmt(w) + " " + wUnit + "</span>" : ""; };
      var h = "";
      if (k) {
        var brand = brandLines();
        h += '<span class="wh-tv-ic">' + packIcon(k, 46) +
          '<span class="wh-tv-badge">' + (cnt ? fmt(cnt) + " " + k : k) + wchip(cap) + "</span>" +
          (brand ? '<span class="wh-tv-brand">🏷 ' + brand + "</span>" : "") + "</span>";
      }
      if (ik) {
        if (k) h += '<span class="wh-tv-arrow">⬅</span>';
        var minis = "";
        var shown = Math.min(ic || 6, 12);
        for (var mi = 0; mi < shown; mi++) minis += packIcon(ik, 18);
        if (ic > 12) minis += '<span class="wh-tv-badge">+' + fmt(ic - 12) + "</span>";
        h += '<span class="wh-tv-ic"><span class="wh-tv-mini">' + minis + "</span>" +
          '<span class="wh-tv-badge">' + (ic ? fmt(ic) + " " + ik : ik) + wchip(ica) + "</span></span>";
      }
      var tot = total > 0 ? total : (unitCount > 0 ? unitCount : null);
      if (tot !== null) {
        h += '<span class="wh-tv-arrow">=</span><span class="wh-tv-total">' +
          fmt(tot) + " " + tword + "</span>";
      }
      if (lo) {
        h += '<span class="wh-tv-ic">' + packIcon(ik || k || "علبة", 22) +
          '<span class="wh-tv-badge">سائب ' + fmt(lo) + "</span></span>";
      }
      tvEl.innerHTML = h;
    }
    function reveal() {
      if (countCell) countCell.hidden = !kindEl.value.trim();
      if (innerCountCell) innerCountCell.hidden = !innerKindEl.value.trim();
      if (innerCapCell) innerCapCell.hidden = !innerKindEl.value.trim() || isMeasureUnit(innerKindEl.value.trim());
      if (looseRow) looseRow.hidden = !looseToggle ? !!((looseEl && looseEl.value)) : !(looseRow.dataset.on === "1" || (looseEl && looseEl.value));
      if (looseToggle) looseToggle.hidden = !(looseRow && looseRow.hidden) && !!(looseEl && looseEl.value);
    }
    if (looseToggle && !looseToggle.dataset.wired) {
      looseToggle.dataset.wired = "1";
      looseToggle.addEventListener("click", function () {
        looseRow.dataset.on = "1";
        looseRow.hidden = false;
        looseToggle.hidden = true;
        if (looseEl) looseEl.focus();
      });
    }

    if (innerKindEl) {
      innerKindEl.addEventListener("input", dynLabels);
      innerKindEl.addEventListener("change", dynLabels);
    }

    /* الصنف: من حقل النموذج نفسه، أو اسم كارت الصنف (data-item-name)، أو حقل ١ مخازن */
    function currentInfo() {
      var name = "";
      if (root.dataset && root.dataset.itemName) name = root.dataset.itemName;
      else if (localItem) name = localItem.value.trim();
      else {
        var altItem = root.querySelector(".js-item-name");
        if (altItem) name = altItem.value.trim();
      }
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
      var iw = innerKindEl ? innerKindEl.value.trim() : "";
      var word = iw || boxWord(ic || 0);
      var loose = toNum(looseEl ? looseEl.value : null) || 0;
      var lu = (looseUnitEl && looseUnitEl.value.trim()) || "";
      var looseBoxes = lu.indexOf("علب") === 0;
      var info = currentInfo();
      var unit = info ? info.unit : "";
      /* وحدة الوزن: كجم/لتر من أساس الصنف نفسه — عمرها ما وحدة العدّ (كارتونة/شكارة)
         «وزن العبوة هو المرجع»: العبوة بوزن ⇒ الحسبة والسجل بالوزن (توجيه ٢٧/٠٩) */
      var wUnit = (info && info.base) ? info.base
        : (isMeasureUnit(iw) ? baseOf(iw).base : "كجم");

      /* حاصل العلب + الفرق: الكرتونة كام مقابل عدد العلب × وزن العلبة */
      if (innerSum) {
        innerSum.textContent = (ic && ica)
          ? fmt(ic) + " " + word + " × " + fmt(ica) + " " + wUnit +
            " = " + fmt(ic * ica) + " " + wUnit : "";
      }
      if (diffEl) {
        diffEl.textContent = "";
        diffEl.classList.remove("bad", "good");
        if (cap && ic && ica) {
          var sub = ic * ica, d = cap - sub;
          if (Math.abs(d) > 0.001) {
            diffEl.textContent = "⚠️ في فرق: العبوة " + fmt(cap) + " " + wUnit +
              " والعلب " + fmt(ic) + " × " + fmt(ica) + " = " + fmt(sub) + " " + wUnit +
              " — الفرق " + fmt(Math.abs(d)) + " " + wUnit + " — صحّح اللي متأكد منه";
            diffEl.classList.add("bad");
          } else {
            diffEl.textContent = "✓ العلب مطابقة لوزن العبوة (" + fmt(sub) + " " + wUnit + ")";
            diffEl.classList.add("good");
          }
        }
      }

      /* وضع الحسبة موحّد: كله وزن (كجم/لتر) أو كله عدّ وحدات — ممنوع خلط مجهولين
         (خطأ ٥٠٠ + ٤١ = ٤١ كان بسبب جمعهما في متغيرين مختلفين — توجيه ٢٧/٠٩) */
      var weightMode = (cap > 0) || (ica > 0) || isMeasureUnit(iw) || isMeasureUnit(unit);
      var bits = [], total = 0, unitCount = 0;
      if (isReal() && count) {
        if (cap) {
          /* وزن العبوة هو المرجع: ١٠ كرتونة × وزن الكرتونة ١٢ كجم = ١٢٠ كجم */
          var sub2 = count * cap;
          total += sub2;
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            " × وزن ال" + kindEl.value.trim() + " " + fmt(cap) + " " + wUnit +
            " = " + fmt(sub2) + " " + wUnit +
            (ic ? " (بداخلها " + fmt(ic) + " " + word + ")" : ""));
        } else if (ic && ica) {
          var cw = ic * ica, sub3 = count * cw;
          total += sub3;
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            " بداخلها " + fmt(ic) + " " + word + " × وزن ال" + word + " " +
            fmt(ica) + " " + wUnit + " = " + fmt(sub3) + " " + wUnit);
        } else if (ic) {
          var q = count * ic;
          var qUnit = weightMode ? wUnit : word;
          if (weightMode) {
            total += q;   /* ١٠ شكارة بداخلها ٥٠ كجم = ٥٠٠ كجم — وزن */
          } else {
            unitCount += q;   /* ١٠ بلتة بداخلها ٢٧ باكت = ٢٧٠ باكت — عدّ */
          }
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim() +
            " بداخلها " + fmt(ic) + " " + word + " = " + fmt(q) + " " + qUnit);
        } else {
          bits.push(count.toLocaleString("ar-EG") + " " + kindEl.value.trim());
        }
      }
      if (loose) {
        if (looseBoxes && ica) {
          var lk = loose * ica;
          total += lk;
          bits.push(fmt(loose) + " " + word + " × " + fmt(ica) + " " +
            wUnit + " = " + fmt(lk) + " " + wUnit + " سائب");
        } else if (looseBoxes && weightMode) {
          bits.push("السائب بالعلب محتاج وزن العلبة!");
        } else if (weightMode) {
          total += loose;
          bits.push(fmt(loose) + " " + wUnit + " سائب");
        } else {
          unitCount += loose;
          bits.push(fmt(loose) + " " + word + " سائب");
        }
      }
      if (eqTotal) {
        eqTotal.textContent = total > 0 ? fmt(total) + " " + wUnit
          : (unitCount > 0 ? fmt(unitCount) + " " + word : "—");
      }
      if (hint) {
        var sum = total || unitCount;
        var sumUnit = total ? wUnit : word;
        if (bits.length === 1 && sum > 0) {
          hint.textContent = "الإجمالي: " + bits[0];
        } else {
          hint.textContent = bits.join(" + ") +
            (bits.length > 1 && sum > 0 ? " — الإجمالي: " + fmt(sum) + " " + sumUnit : "");
        }
      }
      drawTV(total, unitCount, total > 0 ? wUnit
        : (unitCount > 0 ? (isMeasureUnit(iw) ? iw : word) : word),
        wUnit, cap, ica);
      /* وحدة التعامل بتتبني على ناتج التغليف: وزن ⇒ كجم/لتر، عدّ ⇒ المعيار نفسه —
         وخانة وحدة التعامل قراءة بس وقتها (توجيه ٢٧/٠٩) */
      var unitInput = root.querySelector(".js-unit");
      if (unitInput) {
        if (total > 0 || (unitCount > 0 && !isMeasureUnit(unit))) {
          unitInput.disabled = false;
          unitInput.readOnly = true;
          unitInput.dataset.managed = "1";
          unitInput.value = total > 0 ? wUnit : (iw || word);
        } else if (unitInput.dataset.managed === "1") {
          unitInput.readOnly = false;
          delete unitInput.dataset.managed;
          unitInput.value = info ? info.unit : "";
        }
      }
      if (qtyEl) {
        if (total > 0) {
          qtyEl.value = fmt(total);
          qtyEl.readOnly = true;
        } else if (unitCount > 0 && !isMeasureUnit(unit)) {
          /* عدّ وحدات: عالم العدّ كله — الكمية الإجمالية بالوحدات من غير وزن */
          qtyEl.value = fmt(unitCount);
          qtyEl.readOnly = true;
        } else {
          qtyEl.readOnly = false;
        }
        /* تحديث تلميح التحويل عبر حدث input — refreshConv محلية في wireLine */
        qtyEl.dispatchEvent(new Event("input", { bubbles: true }));
        SPLIT_REFRESH.forEach(function (fn) { fn(); });
      }
    }

    [kindEl, countEl, capEl, innerKindEl, innerCountEl, innerCapEl, looseEl, looseUnitEl]
      .forEach(function (el) {
        if (!el) return;
        el.addEventListener("input", function () { reveal(); refresh(); });
        el.addEventListener("change", function () { dynLabels(); renderPresetsSafe(); reveal(); refresh(); });
      });
    /* طباعة المورد/المنتج/الصنف على العبوة في الشاشة — أي تعديل يعيد الرسم فورًا */
    var brandForm = root.closest ? root.closest("form") : null;
    if (brandForm) {
      ["supplier_name", "producer"].forEach(function (nm) {
        var bel = brandForm.querySelector('[name="' + nm + '"]');
        if (bel && !bel.dataset.tvWired) {
          bel.dataset.tvWired = "1";
          bel.addEventListener("input", function () { refresh(); });
          bel.addEventListener("change", function () { refresh(); });
        }
      });
    }
    if (localItem && !localItem.dataset.tvWired) {
      localItem.dataset.tvWired = "1";
      localItem.addEventListener("input", function () { refresh(); });
      localItem.addEventListener("change", function () { refresh(); });
    }
    kindEl.addEventListener("change", function () { renderPresetsSafe(); });

    kindEl.addEventListener("change", function () {
      var info2 = currentInfo();
      renderPresetsSafe();
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
          if (innerKindEl && !innerKindEl.value && remembered.inner_kind) {
            innerKindEl.value = remembered.inner_kind;
            dynLabels();
          }
        }
      }
      refresh();
    });
    renderPresetsSafe();
    reveal();
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

/* من التاميدات: «عرض الإذن» يفتح ٢ مخازن على «سجلات ٢ مخازن» عند إذنها مباشرة (توجيه ٢٧/٠٩) */
(function () {
  try {
    var q = new URLSearchParams(window.location.search);
    var sub2 = q.get("wh2sub"), no = q.get("wh2permit");
    if (!sub2 && !no) return;
    if (sub2) {
      var btn = document.querySelector('[data-wh2sub="' + sub2 + '"]');
      if (btn) btn.click();
    }
    if (no) {
      var row = document.querySelector('[data-taf-open="sijDialog-' + no + '"]');
      if (row) row.click();
    }
  } catch (err) {}

  /* ============ كارت الصنف على الموبايل: الضغط على صنف ينزل على الكارت على طول
  (القائمة فوقه والكارت تحتها — من غيرها يبان «الجدول مختفي» وهو تحت) ============ */
  try {
    var q3 = new URLSearchParams(window.location.search);
    if (q3.get("item")) {
      var cardEl = document.getElementById("whCard");
      if (cardEl && cardEl.scrollIntoView) {
        window.setTimeout(function () {
          cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 150);
      }
    }
  } catch (err) {}

  /* ============ وضع تعديل إذن ١ مخازن: تعبئة الفورم ببياناته (توجيه ٢٧/٠٩) ============ */
  var editData = document.getElementById("whEditData");
  if (editData && addLineBtn && lineBox) {
    var editLines = [];
    try { editLines = JSON.parse(editData.textContent || "[]"); }
    catch (err) { if (window.console && console.warn) console.warn("داتا التعديل:", err); }
    lineBox.innerHTML = "";   /* الكارت الفاضي التلقائي يتشال — الكروت تُبنى من الداتا */
    Array.prototype.forEach.call(editLines, function () { addLineBtn.click(); });
    function dmy(iso) {
      var p = String(iso || "").split("-");
      return p.length === 3 ? AR[+p[2]] + "/" + AR[+p[1]] + "/" + AR[+p[0]] : "";
    }
    Array.prototype.forEach.call(lineBox.querySelectorAll(".wh-item-card"),
      function (card, idx) {
        var ln = editLines[idx];
        if (!ln) return;
        function set(name, val) {
          var el = card.querySelector('[name="l' + idx + "_" + name + '"]');
          if (el) el.value = (val === null || val === undefined) ? "" : String(val);
        }
        set("item_name", ln.item_name);
        set("handle_unit", ln.handle_unit);
        set("qty", ln.qty ? fmt(ln.qty) : "");
        set("pack_kind", ln.pack_kind);
        set("pack_count", ln.pack_count ? fmt(ln.pack_count) : "");
        set("pack_inner_kind", ln.pack_inner_kind);
        set("pack_inner_count", ln.pack_inner_count ? fmt(ln.pack_inner_count) : "");
        set("pack_inner_capacity", ln.pack_inner_capacity ? fmt(ln.pack_inner_capacity) : "");
        set("pack_capacity", ln.pack_capacity ? fmt(ln.pack_capacity) : "");
        set("pack_loose", ln.pack_loose ? fmt(ln.pack_loose) : "");
        set("pack_loose_unit", ln.pack_loose_unit);
        set("prod_date", dmy(ln.prod_date));
        set("exp_date", dmy(ln.exp_date));
        /* المخازن: صف توزيع لكل مخزن محفوظ */
        var rowsBox = card.querySelector(".js-split-rows");
        var addBtn = card.querySelector(".js-split-add");
        if (rowsBox && addBtn) {
          rowsBox.innerHTML = "";
          Array.prototype.forEach.call(ln.stores || [], function (st) {
            addBtn.click();
            var row = rowsBox.children[rowsBox.children.length - 1];
            if (!row) return;
            row.querySelector('[name$="store_id"]').value = st.store_id || "";
            var nameEl = row.querySelector('[name$="store_name"]');
            nameEl.value = st.store_name || "";
            row.querySelector('[name$="store_qty"]').value = st.qty ? fmt(st.qty) : "";
            nameEl.dispatchEvent(new Event("input", { bubbles: true }));
            nameEl.dispatchEvent(new Event("change", { bubbles: true }));
          });
        }
        /* إطلاق الأحداث: الكومبو والشرائح والحسابات تتجدد بالقيم المعبأة */
        Array.prototype.forEach.call(card.querySelectorAll("input, textarea"), function (el) {
          el.dispatchEvent(new Event("input", { bubbles: true }));
        });
        Array.prototype.forEach.call(card.querySelectorAll("input"), function (el) {
          el.dispatchEvent(new Event("change", { bubbles: true }));
        });
        var qtyEl = card.querySelector(".js-line-qty");
        if (qtyEl && SPLIT_REFRESH) SPLIT_REFRESH.forEach(function (f) { f(); });
      });
  }
})();
