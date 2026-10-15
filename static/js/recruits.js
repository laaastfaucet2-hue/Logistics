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
    "سجن": "var(--orange)", "محكمة": "#5eead4", "جزاء": "#f472b6",
  };
  document.querySelectorAll(".rc-status").forEach(function (sel) {
    function paint() {
      sel.style.borderColor = COLORS[sel.value] || "";
      sel.style.color = COLORS[sel.value] || "";
    }
    sel.addEventListener("change", paint);
    paint();
  });

  // اليومية: تغيير الحالة ⇒ «من» = يوم اليومية و«إلى» فاضية (مفتوحة) — والرجوع
  // للحالة الأصلية يرجّع تواريخها (توجيه ١٥/١٠)
  var jform = document.querySelector(".rc-jform");
  if (jform) {
    var D = window.LogisticsDates;
    var dayIso = jform.getAttribute("data-day-iso") || "";
    var dayText = D && dayIso ? D.format(dayIso) : dayIso;
    jform.querySelectorAll(".rc-status").forEach(function (inp) {
      var row = inp.closest("tr");
      var from = row ? row.querySelector('input[name^="from_"]') : null;
      var to = row ? row.querySelector('input[name^="to_"]') : null;
      if (!from || !to) return;
      var orig = { st: inp.value, from: from.value, to: to.value };
      inp.addEventListener("change", function () {
        if (inp.value === orig.st) {
          from.value = orig.from;
          to.value = orig.to;
        } else {
          from.value = inp.value ? dayText : "";
          to.value = "";
        }
      });
    });
  }

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

  // بحث أصل القوة — بالاسم أو الرقم العسكري (أرقام عربية أو لاتينية)
  var searchInp = document.getElementById("rcSearch");
  if (searchInp) {
    var ARABIC = "٠١٢٣٤٥٦٧٨٩";
    var toWestern = function (s) {
      return (s || "").replace(/[\u0660-\u0669]/g,
        function (d) { return String(ARABIC.indexOf(d)); });
    };
    searchInp.addEventListener("input", function () {
      var q = toWestern(searchInp.value.trim()).toLowerCase();
      var rows = document.querySelectorAll(".table-wrap .rt-table tbody tr");
      var shown = 0;
      rows.forEach(function (tr) {
        var nameEl = tr.querySelector(".rc-sname");
        var milEl = tr.querySelector(".rc-smil");
        var hay = toWestern(
          (nameEl ? nameEl.textContent : "") + " " + (milEl ? milEl.textContent : "")
        ).toLowerCase();
        var hit = !q || hay.indexOf(q) !== -1;
        tr.style.display = hit ? "" : "none";
        if (hit) shown++;
      });
      var cnt = document.getElementById("rcSearchCount");
      if (cnt) cnt.textContent = q ? (shown + " من " + rows.length + " نتيجة") : "";
    });
  }
})();