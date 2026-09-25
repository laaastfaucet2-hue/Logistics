/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md */
/* قائمة منسدلة مخصوصة (Combo) — نفس ثيم قائمة الشهور: خلفية كحلية + تحديد ذهبي.
   أي حقل input عليه data-combo="<datalist-id>" يتحوّل لقائمة مخصوصة بدل datalist المتصفح البيضاء. */
(function () {
  "use strict";

  function build(input) {
    if (input.dataset.comboReady) return;
    input.dataset.comboReady = "1";
    var srcId = input.getAttribute("data-combo");
    var src = document.getElementById(srcId);
    if (!src) return;

    var wrap = document.createElement("div");
    wrap.className = "combo-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var list = document.createElement("div");
    list.className = "combo-list";
    list.hidden = true;
    wrap.appendChild(list);

    var items = [];
    var active = -1;

    function options() {
      return Array.prototype.map.call(src.querySelectorAll("option"), function (o) {
        return o.value;
      });
    }

    function render() {
      var q = input.value.trim();
      if (input.id === "ctxYear" || input.id === "ctxMonth") q = "";
      list.innerHTML = "";
      items = options()
        .filter(function (v) { return !q || v.indexOf(q) !== -1; })
        .map(function (v) {
          var d = document.createElement("div");
          d.className = "combo-item" + (v === q && q ? " sel" : "");
          d.textContent = v;
          d.addEventListener("mousedown", function (e) {
            e.preventDefault();           // قبل blur — عشان القيمة تتحط الأول
            input.value = v;
            close();
            input.dispatchEvent(new Event("change", {bubbles:true}));
          });
          list.appendChild(d);
          return d;
        });
      if (!items.length) {
        var empty = document.createElement("div");
        empty.className = "combo-empty";
        empty.textContent = "لا توجد نتائج — اكتب قيمة جديدة";
        list.appendChild(empty);
      }
      active = -1;
    }

    function open() { render(); list.hidden = false; }
    function close() { list.hidden = true; active = -1; }

    input.addEventListener("focus", open);
    input.addEventListener("input", open);
    input.addEventListener("blur", function () { setTimeout(close, 150); });
    input.addEventListener("keydown", function (e) {
      if (list.hidden && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
        e.preventDefault();
        open();
        return;
      }
      if (e.key === "Escape") { close(); return; }
      if (list.hidden || !items.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        active += (e.key === "ArrowDown" ? 1 : -1);
        if (active < 0) active = items.length - 1;
        if (active >= items.length) active = 0;
        items.forEach(function (el, i) { el.classList.toggle("hover", i === active); });
        items[active].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter" && active >= 0) {
        e.preventDefault();
        input.value = items[active].textContent;
        close();
        input.dispatchEvent(new Event("change", {bubbles:true}));
      }
    });
  }

  function enhance(root) { root.querySelectorAll("input[data-combo]").forEach(build); }
  window.LogisticsCombo = { enhance: enhance };
  enhance(document);
})();
