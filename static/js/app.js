// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* منظومة مخازن التعيينات — سكربتات الواجهة */
(function () {
  "use strict";

  // التاريخ بالعربية
  try {
    var dateStr = new Date().toLocaleDateString("ar-EG", {
      weekday: "long", year: "numeric", month: "long", day: "numeric"
    });
    var d1 = document.getElementById("todayDate");
    var d2 = document.getElementById("dashDate");
    if (d1) d1.textContent = dateStr;
    if (d2) d2.textContent = dateStr;
  } catch (e) { /* ignore */ }

  // زر القائمة (موبايل)
  var menuBtn = document.getElementById("menuBtn");
  var sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    document.addEventListener("click", function (ev) {
      if (window.innerWidth <= 1024 && sidebar.classList.contains("open") &&
          !sidebar.contains(ev.target) && !menuBtn.contains(ev.target)) {
        sidebar.classList.remove("open");
      }
    });
  }

  // إخفاء التنبيهات تلقائياً
  document.querySelectorAll(".flash-success").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity .5s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 500);
    }, 4000);
  });

  // الرسوم البيانية
  document.fonts.ready.then(function () {
  if (window.DASH && typeof Chart !== "undefined") {
    var theme = getComputedStyle(document.body);
    var red = theme.getPropertyValue("--brand-red").trim();
    var yellow = theme.getPropertyValue("--brand-yellow").trim();
    Chart.defaults.font.family = theme.fontFamily;
    Chart.defaults.font.size = 14;
    Chart.defaults.color = theme.color;

    var gridColor = "rgba(22,22,22,.1)";

    // حركة آخر 7 أيام
    var chMove = document.getElementById("chMove");
    if (chMove) {
      new Chart(chMove, {
        type: "bar",
        data: {
          labels: window.DASH.days,
          datasets: [
            { label: "صرف", data: window.DASH.disb, backgroundColor: red,
              hoverBackgroundColor: red, borderRadius: 8, borderSkipped: false },
            { label: "توريد", data: window.DASH.supp, backgroundColor: yellow,
              hoverBackgroundColor: yellow, borderRadius: 8, borderSkipped: false }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "top", labels: { boxWidth: 14, padding: 18, font: { weight: "500" } } } },
          scales: {
            x: { grid: { color: gridColor }, ticks: { font: { weight: "500" } } },
            y: { beginAtZero: true, grid: { color: gridColor }, ticks: { stepSize: 1 } }
          }
        }
      });
    }

    // الأصناف الأكثر صرفاً
    var chTop = document.getElementById("chTop");
    if (chTop) {
      new Chart(chTop, {
        type: "doughnut",
        data: {
          labels: window.DASH.topLabels,
          datasets: [{
            data: window.DASH.topData,
            backgroundColor: [red, yellow, "#161616", "#69695f", "#deded6"],
            borderColor: "#ffffff", borderWidth: 4, hoverOffset: 10
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: "62%",
          plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 14, font: { weight: "500" } } } }
        }
      });
    }
  }
  });
})();
