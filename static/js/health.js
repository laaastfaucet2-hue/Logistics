/* قسم «الصحة» — أزرار تحديد سريعة لقائمة المكتوشين */
(function () {
  "use strict";
  function boxes() {
    return Array.prototype.slice.call(
      document.querySelectorAll('.hl-recruits input[name="recruits"]'));
  }
  function setAll(on) { boxes().forEach(function (b) { b.checked = on; }); }
  var all = document.getElementById("hl-all");
  var sugg = document.getElementById("hl-sugg");
  var none = document.getElementById("hl-none");
  if (all) all.addEventListener("click", function () { setAll(true); paint(); });
  if (none) none.addEventListener("click", function () { setAll(false); paint(); });
  if (sugg) sugg.addEventListener("click", function () {
    setAll(false);
    document.querySelectorAll(".hl-rec.sugg input[name=\"recruits\"]")
      .forEach(function (b) { b.checked = true; });
    paint();
  });
  function paint() {
    boxes().forEach(function (b) {
      b.closest(".hl-rec").classList.toggle("picked", b.checked);
    });
  }
  document.querySelectorAll('.hl-recruits input[name="recruits"]')
    .forEach(function (b) { b.addEventListener("change", paint); });
  paint();
})();
