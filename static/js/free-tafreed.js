// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر
/* حسابة الصرف الفورية لصفحة التفاريد الحرة — قراءة حساب فقط، بلا أي كتابة. */
(function () {
  "use strict";
  var dataEl = document.getElementById("ftData");
  var cfg = {};
  try { cfg = JSON.parse((dataEl && dataEl.textContent) || "{}"); } catch (e) { cfg = {}; }
  var button = document.getElementById("ftComputeBtn");
  var body = document.getElementById("ftComputeBody");
  if (!button || !body) return;

  function ar(n) {
    return String(n).replace(/[0-9]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[d]; });
  }
  function qty(n) {
    var x = Number(n);
    if (!isFinite(x)) x = 0;
    return ar(x.toFixed(3)).replace(".", "٫").replace(/٫?0+$/, "") || "٠";
  }
  function value(id) {
    var el = document.getElementById(id);
    var raw = el ? String(el.value || "") : "";
    raw = raw.replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
             .replace("٫", ".");
    var num = parseFloat(raw);
    return isFinite(num) ? num : 0;
  }
  function run() {
    var params = "force=" + encodeURIComponent(value("ftForce")) +
      "&days=" + encodeURIComponent(value("ftDays")) +
      "&kind=" + encodeURIComponent((document.getElementById("ftKind") || {}).value || "");
    if (cfg.sid) params += "&sid=" + encodeURIComponent(cfg.sid);
    fetch((cfg.compute || "/free-tafreed/compute") + "?" + params, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var rows = data.rows || [];
        if (!rows.length) {
          body.innerHTML = "<tr><td colspan=\"7\" class=\"empty\">لا أصناف مفعّلة — " +
            "اسحب الأصناف من تاب «معدلات الأصناف».</td></tr>";
          return;
        }
        // نفس أعمدة كشف الإكسل (cols_ft_sheet): م · الصنف · الوحدة · المعدل · أيام الصرف ·
        // إجمالي الحصة المجمعة · ملاحظات — والملاحظة تُبيّن الوحدة المخزنية عند اختلافها.
        body.innerHTML = rows.map(function (row) {
          var note = (row.shown_unit && row.shown_unit !== row.unit)
            ? "بالوحدة المخزنية: " + qty(row.shown) + " " + row.shown_unit : "";
          return "<tr><td class=\"num\">" + ar(row.serial) + "</td>" +
            "<td class=\"name\"><b>" + row.name + "</b></td>" +
            "<td>" + (row.unit || "—") + "</td>" +
            "<td class=\"num\">" + qty(row.rate) + "</td>" +
            "<td class=\"num\">" + ar(row.days) + "</td>" +
            "<td class=\"num\"><b>" + qty(row.total) + " " + (row.unit || "") + "</b></td>" +
            "<td class=\"note\">" + note + "</td></tr>";
        }).join("");
      })
      .catch(function () { body.innerHTML = "<tr><td colspan=\"7\" class=\"empty\">تعذر الحساب الآن — أعد المحاولة.</td></tr>"; });
  }
  button.addEventListener("click", run);
  ["ftForce", "ftDays", "ftKind"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("change", run);
  });
})();

/* عرض/إخفاء نقاط التوزيع الصفرية — كما في السكرين شوت */
(function () {
  "use strict";
  document.querySelectorAll(".ft-zeros-toggle").forEach(function (box) {
    function apply() {
      document.querySelectorAll(".ft-point.ft-zero").forEach(function (el) {
        el.style.display = box.checked ? "" : "none";
      });
    }
    box.addEventListener("change", apply);
    apply();
  });
})();
