// صفحة التوثيق والمناسبات — تكبير الصور داخل البرنامج (بلا إنترنت)
(function () {
  "use strict";
  var box = document.getElementById("ocLightbox");
  if (!box) return;
  var img = box.querySelector("img");
  function open(src) {
    img.src = src;
    box.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function close() {
    box.hidden = true;
    img.src = "";
    document.body.style.overflow = "";
  }
  Array.prototype.forEach.call(document.querySelectorAll(".oc-photo img"), function (el) {
    el.addEventListener("click", function () {
      open(el.getAttribute("data-full") || el.src);
    });
  });
  box.addEventListener("click", function (ev) {
    if (ev.target === box || ev.target.classList.contains("oc-lb-close")) close();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !box.hidden) close();
  });
})();
