/* تثبيت رؤوس الجداول وزر الإجازة المجمّعة تحت الشريطين فقط.
   مربع «أيام الشهر» جزء عادي من الصفحة: لا يدخل في القياس ولا يثبت عند التمرير.
   نقيس الارتفاع الحقيقي لشريط النافذة + الشريط العلوي لأنه يتغير مع المقاس
   ووضع سطح المكتب، ثم نضعه في --stick-top للعناصر اللاصقة المقصودة. */
(function () {
  "use strict";
  var root = document.documentElement;

  function measure() {
    var win = document.querySelector(".windowbar");
    var top = document.querySelector(".topbar");
    var h = (win ? win.offsetHeight : 0) + (top ? top.offsetHeight : 0);
    root.style.setProperty("--stick-top", (h + 6) + "px");
  }

  function watch(el) {
    if (!el || !window.ResizeObserver) return;
    new window.ResizeObserver(measure).observe(el);
  }

  function boot() {
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("orientationchange", measure);
    watch(document.querySelector(".windowbar"));
    watch(document.querySelector(".topbar"));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
