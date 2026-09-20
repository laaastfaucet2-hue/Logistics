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
  if (window.DASH && typeof Chart !== "undefined") {
    Chart.defaults.font.family = "'Cairo', sans-serif";
    Chart.defaults.color = "#9aa6c7";

    var gridColor = "rgba(255,255,255,.06)";

    // حركة آخر 7 أيام
    var chMove = document.getElementById("chMove");
    if (chMove) {
      new Chart(chMove, {
        type: "bar",
        data: {
          labels: window.DASH.days,
          datasets: [
            { label: "صرف", data: window.DASH.disb, backgroundColor: "rgba(251,146,60,.75)",
              hoverBackgroundColor: "#fb923c", borderRadius: 8, borderSkipped: false },
            { label: "توريد", data: window.DASH.supp, backgroundColor: "rgba(52,211,153,.7)",
              hoverBackgroundColor: "#34d399", borderRadius: 8, borderSkipped: false }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "top", labels: { boxWidth: 14, padding: 18, font: { weight: "700" } } } },
          scales: {
            x: { grid: { color: gridColor }, ticks: { font: { weight: "700" } } },
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
            backgroundColor: ["#e3b341", "#34d399", "#60a5fa", "#f87171", "#a78bfa"],
            borderColor: "#0a1230", borderWidth: 4, hoverOffset: 10
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: "62%",
          plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 14, font: { weight: "700" } } } }
        }
      });
    }
  }
})();
