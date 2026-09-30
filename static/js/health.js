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

    /* المطابقة: كل كلمة من اللي كتبته تكون موجودة في الاسم،
       والبادئة الأول أقوى — والحاضرين اليوم بينزلوا الأول دايمًا */
    function pick(q) {
      var toks = norm(q).split(" ").filter(Boolean);
      var out = [];
      RECRUITS.forEach(function (r) {
        var n = norm(r.name);
        if (toks.length && !toks.every(function (t) { return n.indexOf(t) >= 0; })) {
          return;
        }
        var prefix = toks.length === 1 && n.indexOf(toks[0]) === 0;
        out.push({ r: r, s: (prefix ? 0 : 1) + (r.present ? 0 : 10) });
      });
      out.sort(function (a, b) { return a.s - b.s; });
      return out.slice(0, 9).map(function (x) { return x.r; });
    }

    function openMenu(list, hint) {
      closeMenus();
      if (!list.length) return;
      var menu = document.createElement("div");
      menu.className = "hl-ac";
      if (hint) {
        var head = document.createElement("div");
        head.className = "hl-ac-hint";
        head.textContent = hint;
        menu.appendChild(head);
      }
      list.forEach(function (r) {
        var item = document.createElement("div");
        item.className = "hl-ac-item";
        var nm = document.createElement("span");
        nm.textContent = r.name;
        item.appendChild(nm);
        if (r.present) {
          var b = document.createElement("span");
          b.className = "hl-ac-pres";
          b.textContent = "✅ حاضر اليوم";
          item.appendChild(b);
        }
        item.addEventListener("mousedown", function (ev) {
          ev.preventDefault();
          input.value = r.name;
          rid.value = r.id;
          closeMenus();
          renderNames();
        });
        menu.appendChild(item);
      });
      row.appendChild(menu);
    }

    function refresh() {
      var q = input.value.trim();
      if (!q) {
        /* المربع فاضي: أظهر الحاضرين اليوم الأول وبعدين الباقي */
        var all = RECRUITS.slice(0).sort(function (a, b) {
          return (b.present ? 1 : 0) - (a.present ? 1 : 0);
        }).slice(0, 9);
        openMenu(all, "✅ الحاضرون اليوم الأول — اختار أو كمّل كتابة");
        return;
      }
      rid.value = "";                         // كتابة يدوية تلغي الربط
      openMenu(pick(q), "");
      renderNames();
    }

    input.addEventListener("focus", refresh);
    input.addEventListener("click", refresh);
    input.addEventListener("input", refresh);
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
