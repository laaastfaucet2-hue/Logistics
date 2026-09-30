/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md */
/* مربعات الراغبين الذكية + مودال «كشف وتسجيل أسماء الضباط والأفراد الراغبين»
   في التأميدات — نفس تصميم النظام المرجعي للمستخدم:
   • المودال مربوط بجهة التأميدة المكتوبة (#tmEntity) ويوم «من يوم».
   • قائمة القوة بتشيكات: التشيك = راغب اليوم ويملأ أول مربع فاضي،
     والإلغاء يفضي مربعه، والكتابة في المربعات بتشيك الاسم تلقائيًا.
   • إضافة عضو سريع للقوة + حذف 🗑 + بحث — كلها تعيد رسم الجزء من السيرفر.
   • «حفظ وأعتماد التجهيزات» = نفس endpoint تاب الراغبين (ربط بالاتجاهين). */
(function () {
  "use strict";

  function toArabic(n) {
    var d = "٠١٢٣٤٥٦٧٨٩";
    return String(n).replace(/\d/g, function (x) { return d[+x]; });
  }

  function parseArabicInt(text) {
    var digits = "٠١٢٣٤٥٦٧٨٩";
    var s = String(text || "").trim();
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var d = digits.indexOf(s[i]);
      out += (d !== -1) ? String(d) : s[i];
    }
    var n = parseInt(out, 10);
    return isNaN(n) ? null : n;
  }

  function optionValues(listId) {
    var src = document.getElementById(listId);
    if (!src) return [];
    return Array.prototype.map.call(src.querySelectorAll("option"), function (o) {
      return o.value;
    });
  }

  /* ═══ تأكيد الأسماء الجديدة عند حفظ المربعات (مشترك بين التاب والمودال) ═══ */
  function enhanceForms(root) {
    (root || document).querySelectorAll("form[data-ragboxes]").forEach(function (form) {
      if (form.dataset.ragReady) return;
      form.dataset.ragReady = "1";
      form.addEventListener("submit", function () {
        var slot = form.querySelector(".rag-slot");
        var known = slot ? optionValues(slot.getAttribute("data-combo")) : [];
        var fresh = [];
        form.querySelectorAll(".rag-slot").forEach(function (input) {
          var name = (input.value || "").trim();
          if (!name) return;
          if (known.indexOf(name) === -1 &&
              fresh.indexOf(name) === -1 &&
              !window.confirm("«" + name + "» مش موجود في قوة الجهة.\n" +
                              "هل تريد إضافته كقوة دائمة للجهة؟")) {
            input.value = "";            /* رفض → المربع يفضى ولا يُحفظ */
          } else if (known.indexOf(name) === -1) {
            fresh.push(name);            /* موافقة → يُضاف للقوة الدائمة */
          }
        });
        var box = form.querySelector(".rg-new-names");
        if (box) box.value = JSON.stringify(fresh);
      });
    });
  }

  window.RagBoxes = { enhance: enhanceForms };
  enhanceForms(document);

  /* ═══ مودال التأميدات ═══ */
  var modal = document.getElementById("rgModal");
  if (!modal) return;
  var body = document.getElementById("rgModalBody");
  var cat = "officers";
  var sid = modal.getAttribute("data-sid") || "";

  /* اليوم المُتَّبع = حقل «من يوم» في فورم التأميدة، ولو فاضي يوم الصفحة. */
  function currentDay() {
    var field = document.getElementById("tmDayFrom");
    var n = field ? parseArabicInt(field.value) : null;
    if (n && n >= 1 && n <= 31) return n;
    var iso = modal.getAttribute("data-day") || "";
    return parseArabicInt(iso.split("-")[2]) || 1;
  }

  function entityName() {
    var field = document.getElementById("tmEntity");
    return field ? field.value.trim() : "";
  }

  function swap(html) {
    body.innerHTML = html;
    window.RagBoxes.enhance(body);
    bind(body);
  }

  function fetchText(url, options) {
    fetch(url, Object.assign({ credentials: "same-origin" }, options || {}))
      .then(function (r) { return r.text(); })
      .then(swap)
      .catch(function () {
        body.innerHTML = '<p class="rg-note err">⛔ تعذر التنفيذ — جرّب تاني</p>';
      });
  }

  function loadPanel() {
    var params = ["en=" + encodeURIComponent(entityName()), "d=" + currentDay(),
                  "c=" + cat];
    if (sid) params.push("sid=" + encodeURIComponent(sid));
    body.innerHTML = '<p class="rg-dim">… جاري تحميل كشف الراغبين</p>';
    fetchText("/raghibin/panel?" + params.join("&"));
  }

  function formField(root, name) {
    var form = root.querySelector("form");
    return form ? form.querySelector("[name=" + name + "]") : null;
  }

  function setFilledCount(root) {
    var filled = 0;
    root.querySelectorAll(".rag-slot").forEach(function (i) {
      if (i.value.trim()) filled++;
    });
    var chip = root.querySelector(".rg-filled-count");
    if (chip) chip.textContent = toArabic(filled);
  }

  function slotByName(root, name) {
    var found = null;
    root.querySelectorAll(".rag-slot").forEach(function (i) {
      if (!found && i.value.trim() === name) found = i;
    });
    return found;
  }

  function toggleByName(root, name, checked) {
    Array.prototype.forEach.call(
      root.querySelectorAll(".rg-force-toggle"), function (c) {
        if (c.getAttribute("data-name") === name) c.checked = checked;
      });
  }

  function bind(root) {
    /* تويبات الفئتين */
    Array.prototype.forEach.call(root.querySelectorAll(".rg-ctab"), function (btn) {
      btn.addEventListener("click", function () {
        cat = btn.getAttribute("data-cat");
        loadPanel();
      });
    });

    /* بحث القوة */
    var search = root.querySelector(".rg-force-search");
    if (search) search.addEventListener("input", function () {
      var q = search.value.trim();
      Array.prototype.forEach.call(root.querySelectorAll(".rg-force-item"),
        function (item) {
          item.hidden = !!q && item.getAttribute("data-name").indexOf(q) === -1;
        });
    });

    /* تبديل رتب «الإضافة السريعة» حسب الفئة */
    var catSel = root.querySelector(".rg-qa-cat");
    var rankSel = root.querySelector(".rg-qa-rank");
    var mapEl = root.querySelector(".rg-ranks-map");
    var ranksMap = {};
    try { ranksMap = mapEl ? JSON.parse(mapEl.textContent) : {}; } catch (e) {}
    if (catSel && rankSel) catSel.addEventListener("change", function () {
      var opts = ranksMap[catSel.value] || [];
      rankSel.innerHTML = opts.map(function (r) {
        return '<option value="' + r + '">' + r + "</option>";
      }).join("");
    });

    /* إضافة عضو سريع للقوة */
    var qaBtn = root.querySelector(".rg-qa-add");
    if (qaBtn) qaBtn.addEventListener("click", function () {
      var nameInput = root.querySelector(".rg-qa-name");
      if (!nameInput || !nameInput.value.trim()) {
        if (nameInput) nameInput.focus();
        return;
      }
      var data = new FormData();
      var entity = formField(root, "e");
      data.append("e", entity ? entity.value : "");
      data.append("d", (formField(root, "d") || {}).value || currentDay());
      data.append("sid", (formField(root, "sid") || {}).value || "");
      ["qa_cat", "qa_rank", "qa_name", "qa_note"].forEach(function (n) {
        var el = root.querySelector("[name=" + n + "]");
        data.append(n, el ? el.value : "");
      });
      fetchText("/raghibin/panel/quick_add", { method: "POST", body: data });
    });

    /* حذف اسم من القوة */
    Array.prototype.forEach.call(root.querySelectorAll(".rg-force-del"),
      function (btn) {
        btn.addEventListener("click", function () {
          if (!window.confirm("حذف «" + btn.getAttribute("data-name") +
                              "» من قوة الجهة نهائيًا؟")) return;
          var data = new FormData();
          var entity = formField(root, "e");
          data.append("e", entity ? entity.value : "");
          data.append("d", (formField(root, "d") || {}).value || currentDay());
          data.append("sid", (formField(root, "sid") || {}).value || "");
          fetchText("/raghibin/panel/delete/" + btn.getAttribute("data-person"),
                    { method: "POST", body: data });
        });
      });

    /* تشيك القوة ↔ المربعات */
    Array.prototype.forEach.call(root.querySelectorAll(".rg-force-toggle"),
      function (chk) {
        chk.addEventListener("change", function () {
          var name = chk.getAttribute("data-name");
          if (chk.checked) {
            var first = null;
            root.querySelectorAll(".rag-slot").forEach(function (i) {
              if (!first && !i.value.trim()) first = i;
            });
            if (first) { first.value = name; first.dataset.prev = name; }
          } else {
            var slot = slotByName(root, name);
            if (slot) { slot.value = ""; slot.dataset.prev = ""; }
          }
          setFilledCount(root);
        });
      });

    /* المربعات ↔ التشيك + عداد «تم تحديث» */
    Array.prototype.forEach.call(root.querySelectorAll(".rag-slot"),
      function (input) {
        input.dataset.prev = input.value.trim();
        input.addEventListener("input", function () {
          var v = input.value.trim();
          var prev = input.dataset.prev || "";
          if (v !== prev) {
            if (prev) toggleByName(root, prev, false);
            if (v) toggleByName(root, v, true);
            input.dataset.prev = v;
          }
          setFilledCount(root);
        });
      });
    setFilledCount(root);

    /* إلغاء */
    var cancel = root.querySelector("[data-rgcancel]");
    if (cancel) cancel.addEventListener("click", function () { closeModal(); });
  }

  function openModal() {
    modal.hidden = false;
    loadPanel();
  }

  function closeModal() { modal.hidden = true; }

  var opener = document.getElementById("tmRagNamesBtn");
  if (opener) opener.addEventListener("click", openModal);
  var closer = document.getElementById("rgModalClose");
  if (closer) closer.addEventListener("click", closeModal);
  modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  });

  /* تغيير جهة/يوم التأميدة والمودال مفتوح = إعادة تحميل الكشف فورًا */
  ["tmDayFrom", "tmEntity"].forEach(function (id) {
    var field = document.getElementById(id);
    if (!field) return;
    ["input", "change"].forEach(function (ev) {
      field.addEventListener(ev, function () {
        if (!modal.hidden) loadPanel();
      });
    });
  });
})();
