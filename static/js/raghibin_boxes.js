/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md */
/* مربعات الراغبين الذكية + مودال «كشف وتسجيل أسماء الضباط والأفراد الراغبين»
   في التأميدات (ربط ١٠٠٪ بالاتجاهين مع تاب الراغبين — نفس الـ endpoints).
   سلوك المربعات (توجيه المستخدم ٣٠/٠٩/٢٠٢٦): الاسم يُجلب بالبحث الذكي من قوة
   «الجهات والكوادر»؛ وأي اسم جديد يسأل: هل تريد إضافته كقوة دائمة للجهة؟ */
(function () {
  "use strict";

  /* ═══ ١) تأكيد الأسماء الجديدة عند حفظ المربعات ═══ */
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
        var listId = null;
        var slot = form.querySelector(".rag-slot");
        if (slot) listId = slot.getAttribute("data-combo");
        var known = optionValues(listId);
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

  /* ═══ ٢) مودال التأميدات — يجلب نفس جزء المربعات من تاب الراغبين ═══ */
  var modal = document.getElementById("rgModal");
  if (!modal) return;

  var body = document.getElementById("rgModalBody");
  var entitySelect = document.getElementById("rgModalEntity");
  var dayLabel = document.getElementById("rgModalDay");
  var cat = "officers";
  var sid = modal.getAttribute("data-sid") || "";

  /* اليوم المُتَّبع = حقل «من يوم» في فورم التأميدة (بأرقام عربية أو إنجليزية)،
     ولو فاضي: يوم الصفحة من data-day — الحفظ والأسماء ليوم التأميدة نفسه. */
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

  function currentDay() {
    var field = document.getElementById("tmDayFrom");
    var n = field ? parseArabicInt(field.value) : null;
    if (n && n >= 1 && n <= 31) return n;
    var iso = modal.getAttribute("data-day") || "";
    return parseArabicInt(iso.split("-")[2]) || 1;
  }

  function refreshDayLabel() {
    if (dayLabel) dayLabel.textContent = String(currentDay());
  }

  function loadPanel() {
    var entityName = entitySelect ? entitySelect.value : "";
    var params = ["en=" + encodeURIComponent(entityName), "d=" + currentDay(),
                  "c=" + cat, "back=tameedat", "source=tamida"];
    if (sid) params.push("sid=" + encodeURIComponent(sid));
    body.innerHTML = '<p class="rg-dim">… جاري تحميل المربعات</p>';
    fetch("/raghibin/panel?" + params.join("&"), { credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        body.innerHTML = html;
        window.RagBoxes.enhance(body);
      })
      .catch(function () {
        body.innerHTML = '<p class="rg-note err">⛔ تعذر تحميل المربعات — جرّب تاني</p>';
      });
  }

  function setCat(next) {
    cat = next;
    modal.querySelectorAll(".rg-cat-btn").forEach(function (btn) {
      btn.classList.toggle("gold", btn.getAttribute("data-cat") === cat);
    });
    loadPanel();
  }

  function openModal() {
    var tameedEntity = document.getElementById("tmEntity");
    if (tameedEntity && entitySelect) {
      var current = tameedEntity.value.trim();
      Array.prototype.forEach.call(entitySelect.options, function (o) {
        if (o.value === current) entitySelect.value = current;
      });
    }
    refreshDayLabel();
    modal.hidden = false;
    loadPanel();
  }

  function closeModal() { modal.hidden = true; }

  var opener = document.getElementById("tmRagNamesBtn");
  if (opener) opener.addEventListener("click", openModal);
  var closer = document.getElementById("rgModalClose");
  if (closer) closer.addEventListener("click", closeModal);
  modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
  if (entitySelect) entitySelect.addEventListener("change", loadPanel);
  modal.querySelectorAll(".rg-cat-btn").forEach(function (btn) {
    btn.addEventListener("click", function () { setCat(btn.getAttribute("data-cat")); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  });
  /* المودال يتبع «من يوم» لحظيًا — تغيير اليوم والمودال مفتوح = إعادة تحميل المربعات */
  ["tmDayFrom", "tmDayTo"].forEach(function (id) {
    var field = document.getElementById(id);
    if (!field) return;
    ["input", "change"].forEach(function (ev) {
      field.addEventListener(ev, function () {
        refreshDayLabel();
        if (!modal.hidden && id === "tmDayFrom") loadPanel();
      });
    });
  });
})();
