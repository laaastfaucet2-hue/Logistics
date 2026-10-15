/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md */
/* 🏬 إحصائيات المخازن والثلاجات:
   - حالة ملف التبويب تتحدث وحدها أثناء التحديث في الخلفية (✓ محدّث / ⏳ / 🔒).
   - الطباعة الرسمية تفتح كل الجداول المطوية ثم تعيدها كما كانت. */
(function () {
  "use strict";

  var status = document.getElementById("ssStatus");
  var tries = 0;

  function paint(data) {
    if (!status || !data || !data.state) return;
    status.textContent = data.text || "";
    status.className = "ss-status " + data.state;
    status.setAttribute("data-state", data.state);
  }

  function poll() {
    if (!status || status.getAttribute("data-state") === "fresh" || tries > 60) return;
    tries += 1;
    var url = status.getAttribute("data-url");
    if (!url || !window.fetch) return;
    window.fetch(url, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        paint(data);
        if (!data || data.state !== "fresh") window.setTimeout(poll, 2500);
      })
      .catch(function () { window.setTimeout(poll, 4000); });
  }

  var reopened = [];
  window.addEventListener("beforeprint", function () {
    reopened = [];
    document.querySelectorAll("details.ss-fold").forEach(function (d) {
      if (!d.open) { d.open = true; reopened.push(d); }
    });
  });
  window.addEventListener("afterprint", function () {
    reopened.forEach(function (d) { d.open = false; });
    reopened = [];
  });

  if (status && status.getAttribute("data-state") !== "fresh") window.setTimeout(poll, 1500);
})();
