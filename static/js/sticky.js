/* تثبيت مربع الأيام ورؤوس الجداول تحت الشريطين (طلب ١٤/١٠).
   بنقيس الارتفاع الحقيقي لشريط النافذة + الشريط العلوي (بيتغيروا مع المقاس
   ووضع سطح المكتب) ونحطهم في متغير CSS واحد --stick-top تستخدمه كل العناصر
   اللاصقة — من غير شبكة ولا مكتبات. */
(function () {
  "use strict";
  var root = document.documentElement;

  function measure() {
    var win = document.querySelector(".windowbar");
    var top = document.querySelector(".topbar");
    var h = (win ? win.offsetHeight : 0) + (top ? top.offsetHeight : 0);
    root.style.setProperty("--stick-top", (h + 6) + "px");
    /* في العمود الواحد مربع الأيام بيبقى فوق الجدول، فنزحزح رأس الجدول تحته
       بقدر ارتفاعه — في العمودين (شاشة واسعة) الزحزحة = صفر. */
    var box = document.querySelector(".rc-daysbox");
    var narrow = window.matchMedia("(max-width: 1100px)").matches;
    root.style.setProperty("--stick-rows", (box && narrow ? box.offsetHeight + 8 : 0) + "px");
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
    watch(document.querySelector(".rc-daysbox"));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
