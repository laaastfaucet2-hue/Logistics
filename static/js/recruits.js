/* صفحة المجندين — ساعة القاهرة الحية + تلوين فوري لحالات اليومية */
(function () {
  "use strict";

  // ساعة حية بتوقيت القاهرة في شريط السياق
  var clock = document.getElementById("rc-clock");
  if (clock && window.Intl) {
    var fmt = new Intl.DateTimeFormat("ar-EG-u-nu-latn", {
      timeZone: "Africa/Cairo", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
    setInterval(function () { clock.textContent = fmt.format(new Date()); }, 1000);
  }

  // علامة الصح «يملك شهادة صحية» تفتح تواريخ الشهادة — وإلغاؤها يغلقها ويصفّر القيم
  var hasCert = document.getElementById("hasCertCb");
  var certDetails = document.getElementById("certDetails");
  if (hasCert && certDetails) {
    hasCert.addEventListener("change", function () {
      certDetails.hidden = !hasCert.checked;
      if (!hasCert.checked) {
        certDetails.querySelectorAll("input").forEach(function (inp) { inp.value = ""; });
      }
    });
  }

  // تلوين اختيارات الحالة لحظة التغيير (حضور أخضر، إجازة ذهبي...)
  var COLORS = {
    "حضور": "#6ee7b7", "إجازة": "#f6d47c", "غياب": "#fca5a5",
    "مأمورية": "#93c5fd", "مستشفى": "#c4b5fd", "أخرى": "#cbd5e1",
  };
  document.querySelectorAll("select.rc-status").forEach(function (sel) {
    function paint() {
      sel.style.borderColor = COLORS[sel.value] || "";
      sel.style.color = COLORS[sel.value] || "";
    }
    sel.addEventListener("change", paint);
    paint();
  });
})();
