/* قسم «الصحة» — أزرار التحديد السريعة + بث حي لورق المعاينة */
(function () {
  "use strict";

  /* ================== أزرار تحديد المكتوشين ================== */
  function boxes() {
    return Array.prototype.slice.call(
      document.querySelectorAll('.hl-recruits input[name="recruits"]'));
  }
  function paint() {
    boxes().forEach(function (b) {
      b.closest(".hl-rec").classList.toggle("picked", b.checked);
    });
    renderNames();
  }
  var all = document.getElementById("hl-all");
  var sugg = document.getElementById("hl-sugg");
  var none = document.getElementById("hl-none");
  if (all) all.addEventListener("click", function () {
    boxes().forEach(function (b) { b.checked = true; }); paint();
  });
  if (none) none.addEventListener("click", function () {
    boxes().forEach(function (b) { b.checked = false; }); paint();
  });
  if (sugg) sugg.addEventListener("click", function () {
    boxes().forEach(function (b) { b.checked = false; });
    document.querySelectorAll(".hl-rec.sugg input[name=\"recruits\"]")
      .forEach(function (b) { b.checked = true; });
    paint();
  });
  boxes().forEach(function (b) { b.addEventListener("change", paint); });

  /* ================== قائمة الأسماء في الورق ================== */
  function renderNames() {
    var target = document.querySelector("[data-hnames]");
    if (!target) return;
    var names = boxes().filter(function (b) { return b.checked; }).map(function (b) {
      var lab = b.closest(".hl-rec");
      var el = lab && lab.querySelector(".hl-name");
      return el ? el.textContent.trim() : "";
    }).filter(Boolean);
    target.innerHTML = "";
    names.forEach(function (n) {
      var li = document.createElement("li");
      li.textContent = n;
      target.appendChild(li);
    });
    var emptyEl = document.querySelector(".hl-paper-none");
    if (emptyEl) emptyEl.style.display = names.length ? "none" : "";
  }

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
  paint();
})();
