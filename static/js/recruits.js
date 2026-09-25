/* صفحة المجندين — ساعة القاهرة الحية + تلوين فوري لحالات اليومية */
(function () {
  "use strict";

  // ساعة حية بتوقيت القاهرة في شريط السياق
  var clock = document.getElementById("rc-clock");
  if (clock && window.Intl) {
    var fmt = new Intl.DateTimeFormat("ar-EG-u-nu-arab", {
      timeZone: "Africa/Cairo", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
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
        certDetails.querySelectorAll("input").forEach(function (inp) {
          inp.value = "";
          inp.setCustomValidity("");
          inp.removeAttribute("aria-invalid");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        });
      }
    });
  }

  // تلوين اختيارات الحالة لحظة التغيير (ألوان حالات واضحة على الخلفية الكحلية)
  var COLORS = {
    "حضور": "var(--green)", "إجازة": "var(--text)", "غياب": "var(--red)",
    "مأمورية": "var(--blue)", "مستشفى": "var(--status-other)", "أخرى": "var(--text)",
  };
  document.querySelectorAll(".rc-status").forEach(function (sel) {
    function paint() {
      sel.style.borderColor = COLORS[sel.value] || "";
      sel.style.color = COLORS[sel.value] || "";
    }
    sel.addEventListener("change", paint);
    paint();
  });

  // مدينة/قرية حسب المحافظة المختارة — مع الإبقاء على الكتابة اليدوية لأي اسم ناقص
  var govInp = document.getElementById("rcGov");
  var cityList = document.getElementById("cityList");
  var mapEl = document.getElementById("rcPlacesMap");
  if (govInp && cityList && mapEl) {
    var map = {};
    try { map = JSON.parse(mapEl.textContent); } catch (e) { map = {}; }
    function fillCities() {
      var gov = govInp.value.trim();
      var cities = [];
      function pushAll(arr) {
        (arr || []).forEach(function (c) {
          if (c && cities.indexOf(c) === -1) cities.push(c);
        });
      }
      if (gov && map[gov]) pushAll(map[gov]);
      else Object.keys(map).forEach(function (k) { if (k) pushAll(map[k]); });
      pushAll(map[""]);
      cityList.innerHTML = "";
      cities.forEach(function (c) {
        var opt = document.createElement("option");
        opt.value = c;
        cityList.appendChild(opt);
      });
    }
    govInp.addEventListener("change", fillCities);
    govInp.addEventListener("input", fillCities);
    fillCities();
  }
})();
