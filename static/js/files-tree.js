/* 📁 شجرة حصر الملفات المحلية — عرض لحظي من القرص (توجيه المستخدم ٠٦/١٠/٢٠٢٦).
   كل نداء يجيب الحالة الحقيقية للملفات: الاسم + الحجم + وقت آخر تحديث،
   والملف اللي اتحدث في آخر ثوانٍ يتعلّم «اتحدث الآن» بلون أخضر. */
(function () {
  var zone = document.getElementById('ftZone');
  if (!zone) return;
  var head = document.getElementById('ftToggle');
  var body = document.getElementById('ftBody');
  var tree = document.getElementById('ftTree');
  var chips = document.getElementById('ftChips');
  var where = document.getElementById('ftWhere');
  var live = document.getElementById('ftLive');
  var refresh = document.getElementById('ftRefresh');
  var url = zone.dataset.tree;
  var fresh = Number(zone.dataset.fresh || 25);
  var open = false;
  var lastSignature = '';
  var timer = null;
  var ICON = { json: '🧾', xlsx: '📗', xls: '📗', db: '🗃️', docx: '📘', svg: '🖼️' };

  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function arabic(text) {
    return String(text == null ? '' : text).replace(/[0-9]/g, function (d) {
      return '٠١٢٣٤٥٦٧٨٩'[Number(d)];
    });
  }

  function folderHtml(node) {
    var rows = node.children.map(nodeHtml).join('');
    var inner = rows ? '<ul class="ft-list">' + rows + '</ul>' : '<ul class="ft-list"></ul>';
    return '<li class="ft-folder closed">' +
      '<div class="ft-row' + (node.fresh ? ' fresh' : '') + '">' +
      '<button type="button" class="ft-arrow" aria-label="فتح/إغلاق">▾</button>' +
      '<span class="ft-ico">📁</span>' +
      '<span class="ft-name">' + esc(node.name) + '</span>' +
      '<span class="ft-meta"><span>' + arabic(node.files) + ' ملف</span>' +
      '<span>' + esc(node.size_text) + '</span>' +
      (node.fresh ? '<b class="ft-now">اتحدث الآن</b>' : '') + '</span></div>' + inner + '</li>';
  }

  function fileHtml(node) {
    var icon = ICON[node.ext] || '📄';
    return '<li><div class="ft-row' + (node.fresh ? ' fresh' : '') + '">' +
      '<span class="ft-arrow" aria-hidden="true"></span>' +
      '<span class="ft-ico">' + icon + '</span>' +
      '<span class="ft-name">' + esc(node.name) + '</span>' +
      '<span class="ft-meta">' +
      (node.fresh ? '<b class="ft-now">اتحدث الآن</b>' : '') +
      '<span>' + esc(node.size_text) + '</span>' +
      '<span>🕒 ' + esc(node.mtime_text) + '</span></span></div></li>';
  }

  function nodeHtml(node) {
    return node.type === 'dir' ? folderHtml(node) : fileHtml(node);
  }

  function signatureOf(node) {
    if (node.type === 'file') {
      return node.rel + '|' + node.size + '|' + Math.round(node.mtime) + '|' + (node.fresh ? 1 : 0);
    }
    return node.name + '{' + node.children.map(signatureOf).join(',') + '}';
  }

  function render(data) {
    var signature = data.children.map(signatureOf).join(';');
    if (signature === lastSignature) return;              // لا إعادة رسم بلا تغيير
    lastSignature = signature;
    tree.innerHTML = data.children.length
      ? '<ul class="ft-list">' + data.children.map(nodeHtml).join('') + '</ul>'
      : '<div class="ft-empty">📂 الفولدر لسه فاضي — أول حفظ في القسم هينشئ ملفاته هنا فورًا.</div>';
    if (where) where.innerHTML = '📂 <bdi dir="ltr">' + esc(data.root) + '</bdi>';
    if (live) live.innerHTML = '<i class="ft-dot"></i>مزامنة لحظية — آخر حصر ' + esc(data.checked_at);
    if (open) chips.innerHTML =
      '<i class="ft-chip gold">' + arabic(data.files) + ' ملف</i>' +
      '<i class="ft-chip dim">' + arabic(data.folders) + ' فولدر</i>' +
      '<i class="ft-chip live">🕒 ' + esc(data.checked_at) + '</i>';
  }

  function header(data) {
    chips.innerHTML =
      '<i class="ft-chip gold">' + arabic(data.files) + ' ملف</i>' +
      '<i class="ft-chip dim">' + arabic(data.folders) + ' فولدر</i>' +
      '<i class="ft-chip live">🕒 ' + esc(data.checked_at) + '</i>';
  }

  function poll() {
    fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.ok) return;
        header(data);
        if (open) render(data);
      })
      .catch(function () { /* الشبكة المحلية — نتجاهل الخطأ ونعيد المحاولة */ });
  }

  function setOpen(value) {
    open = value;
    zone.classList.toggle('open', open);
    body.hidden = !open;
    head.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) poll();
  }

  head.addEventListener('click', function () { setOpen(!open); });
  if (refresh) refresh.addEventListener('click', function () { lastSignature = ''; poll(); });

  tree.addEventListener('click', function (event) {
    var arrow = event.target.closest('.ft-arrow');
    if (!arrow || arrow.tagName !== 'BUTTON') return;
    var folder = arrow.closest('.ft-folder');
    if (folder) folder.classList.toggle('closed');
  });

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') poll();       // رجوع للمتصفح = حصر فوري
  });

  poll();
  timer = setInterval(function () {
    if (document.visibilityState === 'visible') poll();       // كل ٥ ثوانٍ: عرض لحظي حقيقي
  }, 5000);
  window.addEventListener('beforeunload', function () { clearInterval(timer); });

  // أي حفظ في البرنامج يعيد التحميل — الحصر هنا يتبع الصفحة نفسها أيضًا
  window.LogisticsFilesTree = { refresh: poll };
})();
