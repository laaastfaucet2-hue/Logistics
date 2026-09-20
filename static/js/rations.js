// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* سكربتات صفحات المقررات: نافذة المخصص + تأكيدات الحذف + تخصيص أيام الجهات */
(function () {
  "use strict";

  // ---------- نافذة المقرر المخصص ----------
  var modal = document.getElementById("customModal");
  if (modal) {
    var form = document.getElementById("customForm");
    var nameSpan = document.getElementById("customItemName");

    function close() { modal.classList.remove("show"); }
    document.getElementById("customClose").addEventListener("click", close);
    document.getElementById("customCancel").addEventListener("click", close);
    modal.addEventListener("click", function (e) { if (e.target === modal) close(); });

    document.querySelectorAll(".custom-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        var name = btn.getAttribute("data-name") || "";
        var entries = [];
        try { entries = JSON.parse(btn.getAttribute("data-custom") || "[]"); } catch (e) {}

        nameSpan.textContent = name;
        // الوجبات بترتيب الأعمدة في الجدول
        var meals = ["breakfast", "lunch", "dinner"];
        for (var d = 0; d < 7; d++) {
          meals.forEach(function (m) {
            var inp = form.querySelector('input[name="c_' + d + '_' + m + '"]');
            if (inp) inp.value = "";
          });
        }
        entries.forEach(function (en) {
          var inp = form.querySelector('input[name="c_' + en.weekday + '_' + en.meal + '"]');
          if (inp) inp.value = en.qty;
        });
        // ضبط رابط الحفظ على الصنف المطلوب
        var tpl = form.getAttribute("data-template");
        form.setAttribute("action", tpl.replace(/\/0$/, "/" + id));
        modal.classList.add("show");
      });
    });
  }

  // ---------- تأكيد الحذف ----------
  document.querySelectorAll("form.js-del").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!confirm("تأكيد حذف الصنف نهائيًا؟")) e.preventDefault();
    });
  });
  document.querySelectorAll("form.js-del-ent").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!confirm("⚠️ حذف الجهة سيحذف جدولها بالكامل — متابعة؟")) e.preventDefault();
    });
  });

  // ---------- تخصيص أيام التوزيع (صفحة الجهات) ----------
  document.querySelectorAll(".dist-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var td = btn.closest(".days-td");
      var form = td ? td.querySelector(".days-form") : null;
      if (!form) return;
      var open = !form.hasAttribute("hidden");
      if (open) {
        form.setAttribute("hidden", "");
        btn.textContent = "تخصيص";
      } else {
        form.removeAttribute("hidden");
        btn.textContent = "إغلاق";
      }
    });
  });
})();
