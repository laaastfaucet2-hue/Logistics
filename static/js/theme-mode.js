/* مفتاح ألوان البرنامج: كحلي / أبيض / أزرق — يُحفظ محليًا على الجهاز (توجيه ٠٦/١٠/٢٠٢٦).
   الوضع يُطبَّق على <html data-theme> فلا يلمس ألوان المستندات الرسمية المطبوعة. */
(function () {
  var KEY = 'logistics.theme';
  var MODES = ['slate', 'white', 'blue'];
  var root = document.documentElement;

  function current() {
    var value = root.dataset.theme || 'slate';
    return MODES.indexOf(value) === -1 ? 'slate' : value;
  }

  function apply(mode) {
    if (MODES.indexOf(mode) === -1) mode = 'slate';
    root.dataset.theme = mode;
    try { localStorage.setItem(KEY, mode); } catch (e) {}
    document.querySelectorAll('.ts-btn').forEach(function (btn) {
      var on = btn.dataset.themeMode === mode;
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.ts-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { apply(btn.dataset.themeMode); });
    });
    apply(current());
  });

  window.LogisticsTheme = { apply: apply, current: current };
})();
