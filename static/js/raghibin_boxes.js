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
  var cat = "officers";
  var day = modal.getAttribute("data-day") || "";
  var sid = modal.getAttribute("data-sid") || "";

  function loadPanel() {
    var entityName = entitySelect ? entitySelect.value : "";
    var params = ["en=" + encodeURIComponent(entityName), "d=" + day.split("-")[2],
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
})();
