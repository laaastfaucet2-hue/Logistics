// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* سكربتات صفحات المقررات: نافذة المخصص + تأكيدات الحذف + أعمدة أيام التوزيع */
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
        var tpl = form.getAttribute("data-template");
        form.setAttribute("action", tpl.replace(/\/0$/, "/" + id));
        modal.classList.add("show");
      });
    });
  }

  // ---------- تأكيدات الحذف ----------
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

  // تأكيد إعادة السحب من المقرر النشط
  document.querySelectorAll("form.js-resync").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!confirm("🔄 هيتم مسح أصناف الجهة الحالية وإعادة سحبها من المقرر النشط — متابعة؟")) {
        e.preventDefault();
      }
    });
  });

  // ---------- أعمدة أيام التوزيع: الشيك يفعّل حقل الكمية — والحفظ دفعة واحدة بزر 💾 ----------
  function syncCell(cell) {
    var ck = cell.querySelector(".ck");
    var dq = cell.querySelector(".dq");
    if (!ck || !dq) return;
    var row = cell.closest("tr");
    var anyChecked = row.querySelectorAll(".daycell .ck:checked").length > 0;
    cell.classList.toggle("on", ck.checked);
    if (ck.checked) {
      dq.disabled = false;
      if (!dq.value) dq.value = dq.dataset.gen || "";
    } else {
      dq.disabled = true;
      // لو الصف رجع «يوميًا» (ولا يوم محدد) نعرض القيمة العامة تحت كل يوم
      dq.value = anyChecked ? "" : (dq.dataset.gen || "");
    }
  }

  document.querySelectorAll(".daycell .ck").forEach(function (ck) {
    ck.addEventListener("change", function () {
      var cell = ck.closest(".daycell");
      ck.closest("tr").querySelectorAll(".daycell").forEach(syncCell);
      if (ck.checked && cell) {
        var dq = cell.querySelector(".dq");
        if (dq) dq.focus();
      }
    });
  });
})();
