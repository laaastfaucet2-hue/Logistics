/* نافذة «إجازة مجمّعة + تصريح» من تبويب الحضور (توجيه ١٤/١٠).
   تُفتح من الزر الثابت، تُبدّل بين «حاضرو اليوم» و«كل المجندين» (قائمة واحدة
   فالاختيار محفوظ)، تبحث بالاسم/الرقم، وتعرض معاينة حيّة بالتواريخ قبل التأكيد. */
(function () {
  "use strict";
  var modal = document.getElementById("rcJointModal");
  var form = document.getElementById("rcJlForm");
  var btn = document.getElementById("rcJointBtn");
  if (!modal || !form || !btn) return;

  var list = document.getElementById("rcJlList");
  var search = document.getElementById("rcJlSearch");
  var toInput = document.getElementById("rcJlTo");
  var prev = document.getElementById("rcJlPrev");
  var err = document.getElementById("rcJlErr");
  var dates = window.LogisticsDates;

  function boxes() { return Array.prototype.slice.call(form.querySelectorAll('input[name="rid"]')); }
  function chosen() { return boxes().filter(function (b) { return b.checked; }); }
  function startDay() {
    var radio = form.querySelector('input[name="start"]:checked');
    return Number.parseInt(form.dataset.today, 10) + (radio && radio.value === "tomorrow" ? 1 : 0);
  }
  function toDay() {
    var raw = dates ? dates.western(toInput.value) : toInput.value;
    var n = Number.parseInt(raw, 10);
    return Number.isInteger(n) ? n : startDay();
  }
  function label(day) {
    if (!dates) return day;
    var y = Number(form.dataset.year), m = Number(form.dataset.month);
    return dates.format(y + "-" + String(m).padStart(2, "0") + "-" + String(day).padStart(2, "0"));
  }

  function preview() {
    var n = chosen().length, f = startDay(), t = toDay();
    var eom = Number(form.dataset.eom);
    err.textContent = "";
    if (!n) { prev.textContent = "اختر مجندًا واحدًا على الأقل من القائمة."; return; }
    if (!(f <= t && t <= eom)) {
      prev.textContent = "";
      err.textContent = "«حتى يوم» لازم يكون من يوم " + label(f) + " لآخر الشهر (" + eom + ").";
      return;
    }
    var what = n > 1 ? "تصريح إجازة مجمّع" : "تصريح إجازة";
    prev.textContent = what + " لـ " + n + (n > 1 ? " مجندين" : " مجند") + ": من " + label(f) +
      (t > f ? " إلى " + label(t) + " (" + (t - f + 1) + " يومًا)" : " — يوم واحد") +
      (f === Number(form.dataset.today) ? " — التسجيل في اليومية فورًا" : " — يُسجّل من شريط تنبيه اليومية بضغطة واحدة");
  }

  function filter() {
    var q = search.value.trim().toLowerCase();
    var onlyPresent = list.classList.contains("only-present");
    boxes().forEach(function (b) {
      var row = b.closest(".rc-jl-p");
      var okPresence = !onlyPresent || row.dataset.present === "1";
      var okQuery = !q || row.dataset.search.toLowerCase().indexOf(q) >= 0;
      row.hidden = !(okPresence && okQuery);
    });
  }

  function open() { modal.hidden = false; filter(); preview(); }
  function close() { modal.hidden = true; }

  btn.addEventListener("click", open);
  document.getElementById("rcJlClose").addEventListener("click", close);
  modal.addEventListener("click", function (ev) { if (ev.target === modal) close(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !modal.hidden) close(); });

  modal.querySelectorAll(".rc-jl-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      modal.querySelectorAll(".rc-jl-tab").forEach(function (t) { t.classList.remove("on"); });
      tab.classList.add("on");
      list.classList.toggle("only-present", tab.dataset.jlTab === "present");
      filter();
    });
  });

  search.addEventListener("input", filter);
  document.getElementById("rcJlAll").addEventListener("click", function () {
    boxes().forEach(function (b) { if (!b.closest(".rc-jl-p").hidden) b.checked = true; });
    preview();
  });
  document.getElementById("rcJlClear").addEventListener("click", function () {
    boxes().forEach(function (b) { b.checked = false; });
    preview();
  });

  form.addEventListener("change", function (ev) {
    if (ev.target.name === "start") modal.classList.toggle("tomorrow", ev.target.value === "tomorrow");
    if (ev.target.name === "rid" || ev.target.name === "start") preview();
  });
  toInput.addEventListener("input", preview);
  form.addEventListener("submit", function (ev) {
    if (!chosen().length) { ev.preventDefault(); preview(); err.textContent = "اختر مجندًا واحدًا على الأقل."; }
  });
  filter();
})();
