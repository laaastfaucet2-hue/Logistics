// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* منظومة مخازن التعيينات — سكربتات الواجهة */
(function () {
  "use strict";

  // Fixed day/month/year in Cairo, regardless of browser/Windows regional settings.
  function refreshDate() {
    const dates = window.LogisticsDates;
    if (!dates) return;
    const text = dates.format(dates.today());
    document.querySelectorAll('#todayDate, #dashDate, [data-today-date]').forEach(function (el) {
      el.textContent = text;
    });
  }
  refreshDate();
  setInterval(refreshDate, 60000);

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
    var blue = theme.getPropertyValue("--blue").trim();
    var gold = theme.getPropertyValue("--brand-gold").trim();
    Chart.defaults.font.family = theme.fontFamily;
    Chart.defaults.font.size = 14;
    Chart.defaults.color = theme.color;

    var gridColor = "rgba(255,255,255,.07)";

    // حركة آخر 7 أيام
    var chMove = document.getElementById("chMove");
    if (chMove) {
      new Chart(chMove, {
        type: "bar",
        data: {
          labels: window.DASH.days,
          datasets: [
            { label: "صرف", data: window.DASH.disb, backgroundColor: blue,
              hoverBackgroundColor: blue, borderRadius: 8, borderSkipped: false },
            { label: "توريد", data: window.DASH.supp, backgroundColor: gold,
              hoverBackgroundColor: gold, borderRadius: 8, borderSkipped: false }
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
            backgroundColor: [gold, blue, "#6ee7b7", "#f87171", "#a78bfa"],
            borderColor: theme.getPropertyValue("--card").trim(), borderWidth: 4, hoverOffset: 10
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

// زر ✕ داخل رسائل التنبيه — قابلة للإغلاق دائمًا (طلب المستخدم)
document.addEventListener("click", function (ev) {
  var x = ev.target.closest(".flash-x");
  if (!x) return;
  var flash = x.closest(".flash");
  if (flash) { flash.style.animation = "none"; flash.remove(); }
});

// زر ✕ داخل التوستات المنبثقة — تُغلق فورًا (بلاغ المستخدم)
document.addEventListener("click", function (ev) {
  var x = ev.target.closest(".toast-x");
  if (!x) return;
  var toast = x.closest(".toast");
  if (toast) toast.remove();
});
