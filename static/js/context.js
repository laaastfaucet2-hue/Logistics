(function () {
  "use strict";
  const year = document.getElementById("ctxYear"), month = document.getElementById("ctxMonth");
  const sid = document.body.dataset.sid;
  function go(path, values) {
    const params = new URLSearchParams(values);
    params.set("next", location.pathname);
    if (sid) params.set("sid", sid);
    location.href = path + "?" + params.toString();
  }
  function apply() {
    const option = Array.from(document.querySelectorAll("#contextMonths option")).find(o => o.value === month.value);
    const validYear = Array.from(document.querySelectorAll("#contextYears option")).some(o => o.value === year.value);
    if (option && validYear) go("/context/set", {year:year.value, month:option.dataset.month});
  }
  if (year && month) { year.addEventListener("change", apply); month.addEventListener("change", apply); }
  document.getElementById("addYearBtn")?.addEventListener("click", function () {
    const value = prompt("السنة الجديدة — مثال: ٢٠٢٧");
    if (value?.trim()) go("/years/create", {year:value.trim()});
  });
  document.getElementById("archiveYearBtn")?.addEventListener("click", function () {
    if (confirm("نقل سنة " + year.value + " إلى الأرشيف محليًا؟\nتنتقل السنة بمجلداتها كاملة إلى فولدر «الأرشيف» — ولا يُسمح بالأرشفة إلا بعد انتهائها تمامًا.\nستبقى قابلة للاسترجاع يدويًا من داخل مجلد البيانات.")) go("/years/archive", {year:year.value});
  });
  document.getElementById("delYearBtn")?.addEventListener("click", function () {
    if (confirm("حذف سنة " + year.value + " وكل بياناتها؟ احتفظ بنسخة احتياطية أولًا. لا يمكن التراجع.")) go("/years/delete", {year:year.value});
  });
  const toast = document.getElementById("appToast");
  if (toast && !toast.classList.contains("err")) setTimeout(() => toast.classList.add("hide"), 6000);
})();
