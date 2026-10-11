/* فتح/إغلاق جدول تنبيهات الشهر + فلتر «التنبيهات فقط» + زرار «تجاهل التنبيه» (توجيه ٠٨/١٠).
   اختيار الفلاتر يُحفظ محليًا حتى لا يعيدها المستخدم كل مرة. */
(function () {
  const zone = document.getElementById('alZone');
  const toggle = document.getElementById('alToggle');
  const body = document.getElementById('alBody');
  if (!zone || !toggle || !body) return;

  const STORE = 'logistics.alerts';
  const state = { open: false, only: true, showIgnored: false };
  try {
    Object.assign(state, JSON.parse(localStorage.getItem(STORE) || '{}'));
  } catch (e) { /* تخزين معطّل — نكمل بالافتراضي */ }

  const levelChips = {
    danger: document.querySelector('.al-chip.danger'),
    warn: document.querySelector('.al-chip.warn'),
    info: document.querySelector('.al-chip.info'),
  };
  const okChip = document.querySelector('.al-chip.ok');
  const igToggle = document.getElementById('alShowIgnored');

  function persist() {
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
  }

  function visibleIssues(row) {
    return Array.prototype.filter.call(row.querySelectorAll('.al-issues li'),
      function (li) { return !li.classList.contains('al-ignored'); });
  }

  function recount() {
    const counts = { danger: 0, warn: 0, info: 0 };
    let anyVisible = false;
    document.querySelectorAll('.al-row').forEach(function (row) {
      visibleIssues(row).forEach(function (li) {
        const lvl = ['danger', 'warn', 'info'].find(function (l) {
          return li.classList.contains('lvl-' + l);
        });
        if (lvl) counts[lvl]++;
        anyVisible = true;
      });
    });
    Object.keys(levelChips).forEach(function (lvl) {
      if (!levelChips[lvl]) return;
      levelChips[lvl].hidden = counts[lvl] === 0;
      levelChips[lvl].textContent = (lvl === 'danger' ? 'خطر ' : lvl === 'warn' ? 'تنبيه ' : 'معلومة ') +
        arNum(counts[lvl]);
    });
    if (okChip) okChip.hidden = anyVisible;
  }

  function arNum(n) {
    return String(n).replace(/[0-9]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'[d]; });
  }

  function paintIgnored() {
    document.querySelectorAll('.al-issues li.al-ignored').forEach(function (li) {
      li.hidden = !state.showIgnored;
    });
    if (igToggle) igToggle.checked = state.showIgnored;
  }

  function filter() {
    document.querySelectorAll('.al-row').forEach(function (row) {
      const hasVisible = visibleIssues(row).length > 0;
      const hasIgnored = (parseInt(row.dataset.ignored || '0', 10) || 0) > 0;
      const show = hasVisible || (state.showIgnored && hasIgnored);
      row.classList.toggle('hide', state.only && !show);
    });
    paintIgnored();
  }

  function paint() {
    zone.classList.toggle('open', state.open);
    toggle.setAttribute('aria-expanded', state.open ? 'true' : 'false');
    body.hidden = !state.open;
    const box = document.getElementById('alOnlyIssues');
    if (box) box.checked = state.only;
    recount();
    filter();
  }

  toggle.addEventListener('click', function () {
    state.open = !state.open;
    persist();
    paint();
  });

  const only = document.getElementById('alOnlyIssues');
  if (only) {
    only.addEventListener('change', function () {
      state.only = only.checked;
      persist();
      filter();
    });
  }

  if (igToggle) {
    igToggle.addEventListener('change', function () {
      state.showIgnored = igToggle.checked;
      persist();
      filter();
    });
  }

  /* «تجاهل التنبيه» / «رجّع» — POST JSON بلا إعادة تحميل الصفحة */
  zone.addEventListener('click', function (ev) {
    const btn = ev.target.closest('.al-ig-btn');
    if (!btn || btn.disabled) return;
    const li = btn.closest('li');
    if (!li) return;
    const act = btn.dataset.act === 'restore' ? 'restore' : 'ignore';
    btn.disabled = true;
    const payload = {
      entity_id: parseInt(li.dataset.entity || '0', 10),
      day: parseInt(li.dataset.day || '0', 10),
      key: li.dataset.key || ''
    };
    fetch('/tameedat/alerts/' + act, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) throw new Error(data.err || 'عملية فشلت');
        li.classList.toggle('al-ignored', act === 'ignore');
        btn.dataset.act = act === 'ignore' ? 'restore' : 'ignore';
        btn.textContent = act === 'ignore' ? 'رجّع' : 'تجاهل';
        btn.title = act === 'ignore' ? 'رجّع التنبيه' : 'تجاهل التنبيه';
        const row = li.closest('.al-row');
        const vis = visibleIssues(row).length;
        const ig = Array.prototype.filter.call(row.querySelectorAll('.al-issues li'),
          function (x) { return x.classList.contains('al-ignored'); }).length;
        row.dataset.issues = vis ? '1' : '0';
        row.dataset.ignored = String(ig);
        const first = visibleIssues(row)[0];
        const lvl = first && ['danger', 'warn', 'info'].find(function (l) {
          return first.classList.contains('lvl-' + l);
        });
        row.className = 'al-row ' + (lvl || 'ok');
        recount();
        filter();
      })
      .catch(function (err) {
        window.alert('تعذر تحديث حالة التنبيه: ' + err.message);
      })
      .finally(function () { btn.disabled = false; });
  });

  paint();
})();
