// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر
/* نافذة المقررات المخصصة على التأميدة — لقطة لهذه التأميدة فقط. */
(function () {
  "use strict";
  var btn = document.getElementById("tmCustomRationsBtn");
  var modal = document.getElementById("tmRationsModal");
  var jsonBox = document.getElementById("tmCustomRationsJson");
  if (!btn || !modal || !jsonBox) return;

  var previewUrl = (document.currentScript && document.currentScript.getAttribute("data-preview")) || "";
  var payload = {};
  try { payload = JSON.parse(jsonBox.value || "{}") || {}; } catch (e) { payload = {}; }

  var section = "tamween";
  var targetKey = "main";
  var list = document.getElementById("tmRatList");

  function western(text) {
    return String(text || "")
      .replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
      .replace(/[۰-۹]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹".indexOf(d); });
  }
  function ar(n) {
    return String(n).replace(/[0-9]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[d]; });
  }
  function formVal(name) {
    var el = document.querySelector("#tmRecordForm [name=\"" + name + "\"]");
    return el ? el.value : "";
  }
  function dayNum(id) {
    var n = parseInt(western(document.getElementById(id) && document.getElementById(id).value), 10);
    return isNaN(n) ? 1 : n;
  }
  function mainName() {
    return (formVal("entity_name") || "").replace(/\s+/g, " ").trim();
  }
  function attNames() {
    return Array.prototype.map.call(
      document.querySelectorAll("#tmAttList input[name=\"att_name\"]"),
      function (el) { return el.value.replace(/\s+/g, " ").trim(); }
    ).filter(Boolean);
  }
  function entityNow() {
    if (targetKey === "main") return mainName();
    return document.getElementById("tmRatEntity").value.replace(/\s+/g, " ").trim();
  }
  function fillEntityCombo() {
    var dl = document.getElementById("tmRatEntities");
    var names = [mainName() || "الجهة الرئيسية"].concat(attNames());
    dl.innerHTML = names.map(function (n) {
      return "<option value=\"" + n.replace(/"/g, "") + "\">";
    }).join("");
    var input = document.getElementById("tmRatEntity");
    if (targetKey === "main") input.value = mainName();
    if (window.LogisticsCombo && window.LogisticsCombo.enhance) {
      window.LogisticsCombo.enhance(modal);
    }
    document.getElementById("tmRatAttTab").textContent =
      "الجهات التابعة (" + ar(attNames().length) + ")";
  }

  function dumpLines(lines) {
    var bucket = payload[targetKey] || (payload[targetKey] = {});
    bucket[section] = lines.map(function (ln) {
      return { name: ln.name, day: ln.day, qty: ln.qty, on: ln.on, unit: ln.unit };
    });
    jsonBox.value = JSON.stringify(payload);
  }

  function render(lines) {
    if (!lines.length) {
      list.innerHTML = "<p class=\"tm-hint\">لا أصناف في هذا المقرر لهذه الجهة — أضفها من صفحة المقررات أو توزيع الجهات.</p>";
      return;
    }
    list.innerHTML = lines.map(function (ln, i) {
      return "<div class=\"tm-rat-row" + (ln.on ? "" : " off") + "\" data-i=\"" + i + "\">" +
        "<button type=\"button\" class=\"tm-rat-day\" data-i=\"" + i + "\">" + ln.weekday +
        "<small>" + ar(ln.day) + "</small></button>" +
        "<span class=\"tm-rat-name\">" + ln.name + (ln.unit ? " <small>(" + ln.unit + ")</small>" : "") + "</span>" +
        "<input class=\"tm-rat-qty\" data-i=\"" + i + "\" inputmode=\"decimal\" value=\"" +
        (ln.on ? ar(ln.qty) : "٠") + "\"" + (ln.on ? "" : " disabled") + ">" +
        "</div>";
    }).join("");
    list._lines = lines;
  }

  function load() {
    var entity = entityNow();
    if (!entity) {
      list.innerHTML = "<p class=\"tm-hint\">اكتب اسم الجهة أولًا.</p>";
      return;
    }
    var url = previewUrl + (previewUrl.indexOf("?") >= 0 ? "&" : "?") +
      "section=" + encodeURIComponent(section) +
      "&entity=" + encodeURIComponent(entity) +
      "&target=" + encodeURIComponent(targetKey) +
      "&from=" + dayNum("tmDayFrom") +
      "&to=" + dayNum("tmDayTo") +
      "&draft=" + encodeURIComponent(JSON.stringify(payload));
    var rec = document.querySelector("#tmRecordForm input[name=\"id\"], #tmRecordForm [data-record]");
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) { render(data.lines || []); })
      .catch(function () { list.innerHTML = "<p class=\"tm-hint\">تعذّر تحميل المقررات.</p>"; });
  }

  btn.addEventListener("click", function () {
    fillEntityCombo();
    modal.hidden = false;
    load();
  });
  document.getElementById("tmRationsClose").addEventListener("click", function () {
    modal.hidden = true;
  });

  Array.prototype.forEach.call(document.querySelectorAll(".tm-rat-tab[data-sec]"), function (tab) {
    tab.addEventListener("click", function () {
      Array.prototype.forEach.call(document.querySelectorAll(".tm-rat-tab[data-sec]"), function (t) {
        t.classList.toggle("on", t === tab);
      });
      section = tab.getAttribute("data-sec");
      document.getElementById("tmRatSection").value =
        section === "contractor" ? "مقررات المتعهد" : "المقررات التموينية";
      load();
    });
  });
  document.getElementById("tmRatMainTab").addEventListener("click", function () {
    targetKey = "main";
    this.classList.add("on");
    document.getElementById("tmRatAttTab").classList.remove("on");
    document.getElementById("tmRatEntity").value = mainName();
    load();
  });
  document.getElementById("tmRatAttTab").addEventListener("click", function () {
    var names = attNames();
    if (!names.length) return;
    targetKey = names[0];
    this.classList.add("on");
    document.getElementById("tmRatMainTab").classList.remove("on");
    document.getElementById("tmRatEntity").value = names[0];
    load();
  });
  document.getElementById("tmRatEntity").addEventListener("change", function () {
    var v = this.value.replace(/\s+/g, " ").trim();
    targetKey = (v === mainName() || !v) ? "main" : v;
    load();
  });
  document.getElementById("tmRatSection").addEventListener("change", function () {
    section = this.value.indexOf("متعهد") >= 0 ? "contractor" : "tamween";
    load();
  });

  list.addEventListener("click", function (ev) {
    var dayBtn = ev.target.closest(".tm-rat-day");
    if (!dayBtn || !list._lines) return;
    var i = parseInt(dayBtn.getAttribute("data-i"), 10);
    list._lines[i].on = !list._lines[i].on;
    if (!list._lines[i].on) list._lines[i].qty = 0;
    render(list._lines);
  });
  list.addEventListener("input", function (ev) {
    if (!ev.target.classList.contains("tm-rat-qty") || !list._lines) return;
    var i = parseInt(ev.target.getAttribute("data-i"), 10);
    var n = parseFloat(western(ev.target.value));
    list._lines[i].qty = isNaN(n) ? 0 : n;
    list._lines[i].on = list._lines[i].qty > 0;
  });
  document.getElementById("tmRationsSave").addEventListener("click", function () {
    if (list._lines) dumpLines(list._lines);
    modal.hidden = true;
  });

  var namesBtn = document.getElementById("tmRagNamesBtn");
  var namesModal = document.getElementById("tmRagNamesModal");
  function closeNames() { if (namesModal) namesModal.hidden = true; }
  if (namesBtn && namesModal) {
    namesBtn.addEventListener("click", function () { namesModal.hidden = false; });
    var namesClose = document.getElementById("tmRagNamesClose");
    var namesOk = document.getElementById("tmRagNamesOk");
    if (namesClose) namesClose.addEventListener("click", closeNames);
    if (namesOk) namesOk.addEventListener("click", closeNames);
  }
})();
