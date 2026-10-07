/* فتح/إغلاق جدول تنبيهات الشهر + فلتر «التنبيهات فقط» (توجيه ٠٦/١٠/٢٠٢٦).
   اختيار الفلتر يُحفظ محليًا حتى لا يعيده المستخدم كل مرة. */
(function () {
  const zone = document.getElementById('alZone');
  const toggle = document.getElementById('alToggle');
  const body = document.getElementById('alBody');
  if (!zone || !toggle || !body) return;

  const STORE = 'logistics.alerts';
  const state = { open: false, only: true };
  try {
    Object.assign(state, JSON.parse(localStorage.getItem(STORE) || '{}'));
  } catch (e) { /* تخزين معطّل — نكمل بالافتراضي */ }

  function paint() {
    zone.classList.toggle('open', state.open);
    toggle.setAttribute('aria-expanded', state.open ? 'true' : 'false');
    body.hidden = !state.open;
    const box = document.getElementById('alOnlyIssues');
    if (box) box.checked = state.only;
    filter();
  }

  function filter() {
    document.querySelectorAll('.al-row').forEach(function (row) {
      const hasIssues = row.dataset.issues === '1';
      row.classList.toggle('hide', state.only && !hasIssues);
    });
  }

  toggle.addEventListener('click', function () {
    state.open = !state.open;
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
    paint();
  });

  const only = document.getElementById('alOnlyIssues');
  if (only) {
    only.addEventListener('change', function () {
      state.only = only.checked;
      try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
      filter();
    });
  }
  paint();
})();
