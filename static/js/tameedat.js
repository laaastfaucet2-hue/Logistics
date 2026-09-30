// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* تفاعلات قسم التاميدات: إجمالي تلقائي، نوع «أخرى»، ملحقات ديناميكية،
   تنبيه الجهة غير المسجلة، تأكيدات الحذف القوية، بحث القاموس. */
(function () {
  "use strict";

  // أرقام عربية → غربية للحسابات المحلية فقط (التخزين والعرض النهائي من الخادم)
  function toWestern(text) {
    return (text || "")
      .replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
      .replace(/[۰-۹]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹".indexOf(d); });
  }
  function intVal(input) {
    var n = parseInt(toWestern(input && input.value), 10);
    return isNaN(n) || n < 0 ? 0 : n;
  }

  // الإجمالي التلقائي: ضباط + أفراد + مجندين (بأرقام عربية في العرض)
  var countsForm = document.getElementById("tmRecordForm");
  if (countsForm) {
    var totalBox = document.getElementById("tmTotal");
    function arDigits(n) {
      return String(n).replace(/[0-9]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[d]; });
    }
    function refreshTotal() {
      var sum = ["officers", "individuals", "recruits"].reduce(function (acc, name) {
        return acc + intVal(countsForm.querySelector('input[name="' + name + '"]'));
      }, 0);
      if (totalBox) totalBox.value = arDigits(sum);
    }
    ["officers", "individuals", "recruits"].forEach(function (name) {
      var input = countsForm.querySelector('input[name="' + name + '"]');
      if (input) input.addEventListener("input", refreshTotal);
    });
    refreshTotal();

    // قفل الزر أثناء الحفظ مباشرةً (طلب المستخدم) + توكن الحفظ الخادمي الاحتياطي —
    // الضغط المزدوج/إعادة الإرسال لا ينشئ مطلقًا تأميدتين.
    countsForm.addEventListener("submit", function () {
      var saveBtn = countsForm.querySelector(".tm-save");
      if (saveBtn && !saveBtn.disabled) {
        saveBtn.disabled = true;
        saveBtn.textContent = "⏳ جارٍ الحفظ في البيانات المحلية…";
      }
    });
    // لو رجع المستخدم للصفحة من ذاكرة المتصفح (زر رجوع/تقدم) يعود الزر نشطًا فورًا
    window.addEventListener("pageshow", function (ev) {
      if (!ev.persisted) return;
      var saveBtn = countsForm.querySelector(".tm-save");
      if (saveBtn && saveBtn.disabled) {
        saveBtn.disabled = false;
        saveBtn.textContent = "💾 حفظ التأميدة في البيانات المحلية";
      }
    });

    // زرّ «إضافة تأميدة جديدة لهذا اليوم» — يفتح نموذج التسجيل ويقفله (طلب المستخدم)
    var newToggle = document.getElementById("tmNewToggle");
    var formCard = document.getElementById("tmFormCard");
    if (newToggle && formCard) {
      newToggle.addEventListener("click", function () {
        formCard.hidden = !formCard.hidden;
        newToggle.classList.toggle("open", !formCard.hidden);
        newToggle.setAttribute("aria-expanded", formCard.hidden ? "false" : "true");
        if (!formCard.hidden) formCard.scrollIntoView({ block: "nearest", behavior: "smooth" });
      });
    }

    // «من يوم / إلى يوم» — تحويل الأرقام للعربية فورًا + تلميح عدد أيام السريان المباشر
    var dayFrom = document.getElementById("tmDayFrom");
    var dayTo = document.getElementById("tmDayTo");
    var rangeHint = document.getElementById("tmRangeDaysHint");
    var maxDay = parseInt((dayFrom && dayFrom.getAttribute("data-max")) || "31", 10);
    function normDay(el) {
      if (!el) return 0;
      // الأرقام تدخل بالعربية دائمًا — لو كتب المستخدم لاتينية نحوّلها فورًا داخل الحقل
      el.value = arDigits(toWestern(el.value).replace(/[^\d]/g, ""));
      var v = parseInt(toWestern(el.value), 10);
      return (v >= 1 && v <= maxDay) ? v : 0;
    }
    function refreshRange() {
      var f = normDay(dayFrom), t = normDay(dayTo);
      if (!rangeHint) return;
      var span = (f && t && t >= f) ? t - f + 1 : 0;
      rangeHint.hidden = span === 0;
      if (t && f && t < f) {
        rangeHint.hidden = false;
        rangeHint.textContent = "⚠️ «إلى يوم» لا يسبق «من يوم» — عدّل النهاية.";
      } else if (span > 1) {
        rangeHint.textContent = "التأميدة سارية " + arDigits(span) + " أيام — من يوم " + arDigits(f) + " إلى يوم " + arDigits(t) + ".";
      } else if (span === 1) {
        rangeHint.textContent = "تأميدة يوم واحد فقط — من يوم " + arDigits(f) + " إلى يوم " + arDigits(t) + " (نفس اليوم).";
      }
    }
    if (dayFrom) dayFrom.addEventListener("input", refreshRange);
    if (dayTo) dayTo.addEventListener("input", refreshRange);
    refreshRange();

    // «أخرى» تُظهر حقل النوع الحر (لجهة جديدة فقط)
    countsForm.querySelectorAll('input[name="type_choice"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        var other = countsForm.querySelector('input[name="type_other"]');
        if (other) other.hidden = countsForm.querySelector('input[name="type_choice"]:checked').value !== "أخرى";
      });
    });

    // تنبيه الجهة غير المسجلة في قاموس الشهر — قبل الإضافة الفعلية عند الحفظ
    var entityInput = document.getElementById("tmEntity");
    var warn = document.getElementById("tmUnknownWarn");
    var known = [];
    try { known = JSON.parse(document.getElementById("tmEntities").textContent); } catch (e) { known = []; }
    if (entityInput && warn) {
      entityInput.addEventListener("input", function () {
        var name = entityInput.value.trim().replace(/\s+/g, " ");
        warn.hidden = !name || known.indexOf(name) !== -1;
      });
    }
  }

  // حقل النوع الحر في نموذج القاموس
  document.querySelectorAll("fieldset.tm-types").forEach(function (fs) {
    var other = fs.querySelector('input[name="type_other"]');
    if (!other) return;
    fs.querySelectorAll('input[name="type_choice"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        other.hidden = fs.querySelector('input[name="type_choice"]:checked').value !== "أخرى";
      });
    });
  });

  // صفوف الملحقات الديناميكية
  var attAdd = document.getElementById("tmAttAdd");
  var attList = document.getElementById("tmAttList");
  var attTpl = document.getElementById("tmAttTpl");
  if (attAdd && attList && attTpl) {
    attAdd.addEventListener("click", function () {
      var row = attTpl.content.cloneNode(true);
      attList.appendChild(row);
      // قاعدة: كل قائمة منسدلة كومبو متمثّم — حتى المضافة لاحقًا
      if (window.LogisticsCombo) window.LogisticsCombo.enhance(attList);
    });
    attList.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".tm-att-del");
      if (btn) btn.closest(".tm-att").remove();
    });
  }

  // تأكيد قوي لحذف جهة القاموس — يوضح مصير تأميداتها في هذا الشهر فقط
  document.querySelectorAll("form.js-del-dict").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      var name = form.dataset.name || "هذه الجهة";
      var count = parseInt(form.dataset.count || "0", 10);
      var msg = "⚠️ حذف نهائي داخل هذا الشهر فقط:\n" +
        "ستُحذف الجهة «" + name + "» من قاموس الشهر" +
        (count > 0 ? " ومعها " + count + " تأميدة مسجلة باسمها في هذا الشهر وملحقاتها" : "") +
        ".\nلا يمكن التراجع بعد التنفيذ — متابعة؟";
      if (!confirm(msg)) ev.preventDefault();
    });
  });

  // قائمة «أيام التميد بالتواريخ» المنبثقة في تبويب المومدة
  var daysModal = document.getElementById("tmDaysModal");
  if (daysModal) {
    var daysList = document.getElementById("tmDaysList");
    var daysTitle = document.getElementById("tmDaysTitle");
    function closeDays() { daysModal.hidden = true; }
    document.querySelectorAll(".tm-days-open").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tpl = document.getElementById(btn.dataset.daysSrc);
        if (!tpl) return;
        daysList.innerHTML = tpl.innerHTML;
        daysTitle.textContent = "أيام التميد بالتواريخ — " + (btn.dataset.daysName || "");
        daysModal.hidden = false;
      });
    });
    document.getElementById("tmDaysClose").addEventListener("click", closeDays);
    daysModal.addEventListener("click", function (ev) {
      if (ev.target === daysModal) closeDays();          // النقر على الغلالة يغلق
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !daysModal.hidden) closeDays();
    });
    document.getElementById("tmDaysPrint").addEventListener("click", function () {
      document.body.classList.add("printing-days");      // لا تُطبع سوى القائمة
      setTimeout(function () {
        window.print();
        document.body.classList.remove("printing-days");
      }, 60);
    });
  }

  // بحث فوري في جدول القاموس
  var dictSearch = document.getElementById("tmDictSearch");
  var dictTable = document.getElementById("tmDictTable");
  if (dictSearch && dictTable) {
    dictSearch.addEventListener("input", function () {
      var q = dictSearch.value.trim();
      dictTable.querySelectorAll("tbody tr").forEach(function (row) {
        row.style.display = !q || row.textContent.indexOf(q) !== -1 ? "" : "none";
      });
    });
  }
})();
