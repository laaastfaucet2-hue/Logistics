/* قسم «الصحة» — مربعات أسماء المكتوشين ببحث ذكي + بث حي لورق المعاينة */
(function () {
  "use strict";

  /* ================== بحث ذكي على المجندين ================== */
  var RECRUITS = window.HL_RECRUITS || [];

  function norm(s) {
    return (s || "")
      .replace(/[\u064B-\u0652\u0640]/g, "")   // التشكيل والتطويل
      .replace(/[أإآ]/g, "ا").replace(/ى/g, "ي")
      .replace(/ة/g, "ه").replace(/\s+/g, " ").trim();
  }

  function boxesRoot() { return document.getElementById("hl-nameboxes"); }
  function rows() {
    return Array.prototype.slice.call(
      document.querySelectorAll(".hl-namebox-row"));
  }

  /* ================== قائمة الأسماء في ورق المعاينة ================== */
  function renderNames() {
    var target = document.querySelector("[data-hnames]");
    if (!target) return;
    var names = rows().map(function (row) {
      var inp = row.querySelector('input[name="names"]');
      return inp ? inp.value.trim() : "";
    }).filter(Boolean);
    target.innerHTML = "";
    names.forEach(function (n, i) {
      var d = document.createElement("div");
      d.className = "hl-paper-name";
      d.textContent = (i + 1).toLocaleString("ar-EG") + "- " + n;
      target.appendChild(d);
    });
    var emptyEl = document.querySelector(".hl-paper-none");
    if (emptyEl) emptyEl.style.display = names.length ? "none" : "";
  }

  /* ================== القائمة المنسدلة للاقتراحات ================== */
  function closeMenus() {
    document.querySelectorAll(".hl-ac").forEach(function (m) { m.remove(); });
  }

  function attachAutocomplete(row) {
    var input = row.querySelector('input[name="names"]');
    var rid = row.querySelector('input[name="recruit_ids"]');
    if (!input || input.dataset.acBound) return;
    input.dataset.acBound = "1";

    input.addEventListener("input", function () {
      rid.value = "";                       // كتابة يدوية تلغي الربط
      closeMenus();
      renderNames();
      var q = norm(input.value);
      if (!q) return;
      var matches = RECRUITS.map(function (r) {
        var n = norm(r.name);
        var score = n === q ? 0 : n.indexOf(q) === 0 ? 1 :
                    n.indexOf(q) >= 0 ? 2 : 9;
        return { r: r, score: score + (r.present ? 0 : 10) };
      }).filter(function (m) { return m.score < 9; })
        .sort(function (a, b) { return a.score - b.score; })
        .slice(0, 8);
      if (!matches.length) return;
      var menu = document.createElement("div");
      menu.className = "hl-ac";
      matches.forEach(function (m) {
        var item = document.createElement("div");
        item.className = "hl-ac-item";
        var nm = document.createElement("span");
        nm.textContent = m.r.name;
        item.appendChild(nm);
        if (m.r.present) {
          var b = document.createElement("span");
          b.className = "hl-ac-pres";
          b.textContent = "✅ حاضر اليوم";
          item.appendChild(b);
        }
        item.addEventListener("mousedown", function (ev) {
          ev.preventDefault();
          input.value = m.r.name;
          rid.value = m.r.id;
          closeMenus();
          renderNames();
        });
        menu.appendChild(item);
      });
      row.appendChild(menu);
    });
    input.addEventListener("blur", function () {
      setTimeout(closeMenus, 150);
      renderNames();
    });
  }

  /* ================== إضافة/حذف المربعات ================== */
  function addRow(name, id) {
    var root = boxesRoot();
    if (!root) return;
    var row = document.createElement("div");
    row.className = "hl-namebox-row";
    var input = document.createElement("input");
    input.type = "text"; input.name = "names"; input.dir = "rtl";
    input.placeholder = "اكتب اسم المجند…"; input.autocomplete = "off";
    input.value = name || "";
    var hidden = document.createElement("input");
    hidden.type = "hidden"; hidden.name = "recruit_ids"; hidden.value = id || "";
    var x = document.createElement("button");
    x.type = "button"; x.className = "hl-box-x"; x.title = "حذف المربع";
    x.textContent = "✕";
    x.addEventListener("click", function () { row.remove(); renderNames(); });
    row.appendChild(input); row.appendChild(hidden); row.appendChild(x);
    root.appendChild(row);
    attachAutocomplete(row);
    return input;
  }

  var addBtn = document.getElementById("hl-addbox");
  if (addBtn) addBtn.addEventListener("click", function () {
    var inp = addRow("", "");
    if (inp) inp.focus();
  });
  rows().forEach(function (r) {
    attachAutocomplete(r);
    var x = r.querySelector(".hl-box-x");
    if (x) x.addEventListener("click", function () {
      r.remove(); renderNames();
    });
  });
  if (boxesRoot() && !rows().length) addRow("", "");  // أول مربع فاضي

  /* ================== بث حي: حقل ← ورق ================== */
  function bindLive() {
    document.querySelectorAll("[data-hkey]").forEach(function (input) {
      var key = input.getAttribute("data-hkey");
      var target = document.querySelector('[data-hval="' + key + '"]');
      if (!target) return;
      var isArea = input.tagName === "TEXTAREA";
      target.classList.add("hl-live");
      input.addEventListener("input", function () {
        target.textContent = input.value;
        target.classList.toggle("hl-live-dirty", !!input.value);
      });
      if (isArea) target.style.whiteSpace = "pre-wrap";
    });
  }
  bindLive();

  /* ================== خط الورقة = خط ملف الوورد بالظبط ================== */
  var paper = document.getElementById("hl-paper");
  if (paper) paper.style.fontFamily =
    '"Cairo", "Segoe UI", Tahoma, Arial, sans-serif';

  renderNames();
})();
