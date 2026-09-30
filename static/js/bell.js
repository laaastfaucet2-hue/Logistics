/* جرس الإشعارات — الجرس يفتح لوحة الإشعارات، والشرطة الحمراء تطويه لعلامة + */
(function () {
  "use strict";
  var wrap = document.getElementById("bellWrap");
  if (!wrap) return;
  var panel = document.getElementById("bellPanel");
  var btn = document.getElementById("bellBtn");
  var toggle = document.getElementById("bellToggle");

  // استرجاع وضع الطي المحفوظ
  if (localStorage.getItem("bell-collapsed") === "1") {
    wrap.classList.add("collapsed");
    toggle.textContent = "+";
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    var collapsed = wrap.classList.toggle("collapsed");
    toggle.textContent = collapsed ? "+" : "−";
    toggle.title = collapsed ? "إظهار جرس الإشعارات" : "طي الجرس";
    if (collapsed && panel) panel.classList.remove("open");
    localStorage.setItem("bell-collapsed", collapsed ? "1" : "0");
  });

  if (btn) {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      panel.classList.toggle("open");
    });
  }
  if (panel) {
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
  }
  document.addEventListener("click", function () {
    if (panel && panel.classList.contains("open")) panel.classList.remove("open");
  });
})();
