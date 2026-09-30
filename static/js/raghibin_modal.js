/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* برمجة جديدة كاملة (٣٠/٠٩/٢٠٢٦ مساءً — توجيه المستخدم «عيد من الأول»):
   • زرار التأميدات يفتح صفحة كشف الراغبين الكاملة بتصفح عادي (بلا fetch نهائيًا).
   • داخل صفحة الكشف: بحث القوة + تبديل رتب الإضافة السريعة + التشيك ↔ المربعات
     + عداد «تم تحديث» — كلها لمس داخل الصفحة بلا أي طلبات خلفية.
   • الحفظ/الإضافة/التبديل كلها نماذج عادية تتصفح بـ sid في الرابط. */
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

  function urlParam(name) {
    var m = new RegExp("[?&]" + name + "=([^&]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
  }

  /* ═══ تأكيد الأسماء الجديدة عند حفظ المربعات ═══ */
  function optionValues(listId) {
    var src = document.getElementById(listId);
    if (!src) return [];
    return Array.prototype.map.call(src.querySelectorAll("option"), function (o) {
      return o.value;
    });
  }

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

  /* ═══ زرار التأميدات: تصفح عادي لصفحة الكشف — بلا أي جلب ═══ */
  var opener = document.getElementById("tmRagNamesBtn");
  if (opener) {
    opener.addEventListener("click", function () {
      var entityField = document.getElementById("tmEntity");
      var dayField = document.getElementById("tmDayFrom");
      var entity = entityField ? entityField.value.trim() : "";
      var day = parseArabicInt(dayField ? dayField.value : "") || 1;
      var sid = urlParam("sid");
      var url = "/raghibin/modal?c=officers&d=" + day +
                "&en=" + encodeURIComponent(entity);
      if (sid) url += "&sid=" + encodeURIComponent(sid);
      window.location.href = url;
    });
  }

  /* ═══ داخل صفحة الكشف: لمس محلي بلا طلبات خلفية ═══ */
  var root = document.querySelector(".rg-modal-form");
  if (!root) return;

  function setFilledCount() {
    var filled = 0;
    root.querySelectorAll(".rag-slot").forEach(function (i) {
      if (i.value.trim()) filled++;
    });
    var chip = root.querySelector(".rg-filled-count");
    if (chip) chip.textContent = toArabic(filled);
  }

  function slotByName(name) {
    var found = null;
    root.querySelectorAll(".rag-slot").forEach(function (i) {
      if (!found && i.value.trim() === name) found = i;
    });
    return found;
  }

  function toggleByName(name, checked) {
    Array.prototype.forEach.call(
      root.querySelectorAll(".rg-force-toggle"), function (c) {
        if (c.getAttribute("data-name") === name) c.checked = checked;
      });
  }

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
          var slot = slotByName(name);
          if (slot) { slot.value = ""; slot.dataset.prev = ""; }
        }
        setFilledCount();
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
          if (prev) toggleByName(prev, false);
          if (v) toggleByName(v, true);
          input.dataset.prev = v;
        }
        setFilledCount();
      });
    });
  setFilledCount();
})();
