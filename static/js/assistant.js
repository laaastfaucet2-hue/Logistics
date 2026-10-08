/* المساعد المحلي — واجهة الشات: زر جانبي يُفتح ويُغلق مثل الإشعارات.
   كل الردود من /assistant/ask داخل البرنامج — لا إنترنت ولا خدمة خارجية.
   الردود كتل منظمة (نص/تعداد/جدول/ملاحظة) تُبنى بعناصر DOM آمنة بلا innerHTML. */
(function () {
  const wrap = document.getElementById('asstWrap');
  const btn = document.getElementById('asstBtn');
  const toggle = document.getElementById('asstToggle');
  const panel = document.getElementById('asstPanel');
  const close = document.getElementById('asstClose');
  const log = document.getElementById('asstLog');
  const form = document.getElementById('asstForm');
  const input = document.getElementById('asstInput');
  const promptsBox = document.getElementById('asstPrompts');
  const historyBox = document.getElementById('asstHistory');
  const script = document.currentScript;
  if (!wrap || !btn || !panel || !form) return;

  const ASK = script.dataset.ask;
  const PROMPTS = script.dataset.prompts;
  const CAPABILITIES = script.dataset.capabilities;
  const MODEL_SELECT = script.dataset.modelselect;
  const SID = script.dataset.sid || '';   // توكن الجلسة — يضمن عمل الطلبات لو الكوكي اختفى
  const modelInput = document.getElementById('asstModelInput');
  const modelList = document.getElementById('asstModelList');
  const modelState = document.getElementById('asstModelState');
  let lastModel = null;      // آخر حالة معروفة للقائمة (لإرجاعها لو فشل الطلب)
  let modelLabelMap = {};    // القيمة المعروضة في القائمة ← الاسم اللي بيتبعت
  const KEY = 'logistics.assistant.collapsed';
  const HISTORY_KEY = 'logistics.assistant.history';
  const HISTORY_MAX = 8;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function say(who) {
    const bubble = el('div', 'asst-msg ' + (who || 'bot'));
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  /* ---------- رسم كتل الإجابة ---------- */
  function renderBlocks(container, title, blocks) {
    if (title) container.appendChild(el('div', 'asst-title', title));
    (blocks || []).forEach(function (block) {
      const kind = block.type;
      if (kind === 'p') {
        container.appendChild(el('p', 'asst-p', block.text));
      } else if (kind === 'note') {
        container.appendChild(el('p', 'asst-note', block.text));
      } else if (kind === 'bullets') {
        const list = el('ul', 'asst-bullets');
        (block.items || []).forEach(function (item) { list.appendChild(el('li', null, item)); });
        container.appendChild(list);
      } else if (kind === 'kv') {
        const box = el('dl', 'asst-kv');
        (block.items || []).forEach(function (pair) {
          box.appendChild(el('dt', null, pair[0]));
          box.appendChild(el('dd', null, pair[1]));
        });
        container.appendChild(box);
      } else if (kind === 'table') {
        const scroll = el('div', 'asst-tablescroll');
        const table = el('table', 'asst-table');
        const thead = el('thead');
        const headRow = el('tr');
        (block.headers || []).forEach(function (header) { headRow.appendChild(el('th', null, header)); });
        thead.appendChild(headRow);
        table.appendChild(thead);
        const tbody = el('tbody');
        (block.rows || []).forEach(function (row) {
          const tr = el('tr');
          row.forEach(function (cell) { tr.appendChild(el('td', null, cell)); });
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        scroll.appendChild(table);
        container.appendChild(scroll);
      }
    });
  }

  function renderLinks(container, items) {
    if (!items || !items.length) return;
    const box = el('div', 'asst-links');
    items.forEach(function (item) {
      const link = el('a', 'asst-link', '↗ ' + item.label);
      link.href = item.href;
      box.appendChild(link);
    });
    container.appendChild(box);
  }

  function renderFollowups(items, onClick) {
    if (!items || !items.length) return;
    const box = el('div', 'asst-followups');
    items.slice(0, 4).forEach(function (text) {
      const chip = el('button', 'asst-fchip', text);
      chip.type = 'button';
      chip.addEventListener('click', function () { onClick(text); });
      box.appendChild(chip);
    });
    log.appendChild(box);
    log.scrollTop = log.scrollHeight;
  }

  /* ---------- الاقتراحات وسجل الأسئلة ---------- */
  function chips(items) {
    promptsBox.textContent = '';
    (items || []).forEach(function (text) {
      const chip = el('button', 'asst-chip', text);
      chip.type = 'button';
      chip.addEventListener('click', function () { send(text); });
      promptsBox.appendChild(chip);
    });
  }

  function history() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch (e) { return []; }
  }

  function remember(question) {
    const items = history().filter(function (item) { return item !== question; });
    items.unshift(question);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_MAX))); } catch (e) {}
    paintHistory();
  }

  function paintHistory() {
    const items = history();
    historyBox.textContent = '';
    if (!items.length) { historyBox.hidden = true; return; }
    historyBox.hidden = false;
    historyBox.appendChild(el('span', 'asst-history-label', 'آخر أسئلتك:'));
    items.slice(0, 5).forEach(function (text) {
      const chip = el('button', 'asst-chip ghost', text);
      chip.type = 'button';
      chip.addEventListener('click', function () { send(text); });
      historyBox.appendChild(chip);
    });
  }

  /* ---------- الإرسال ---------- */
  let busy = false;
  async function send(text) {
    const question = (text || input.value || '').trim();
    if (!question || busy) return;
    busy = true;
    input.value = '';
    say('me').textContent = question;
    const thinking = say('bot');
    const dots = el('span', 'asst-typing');
    dots.append(el('i'), el('i'), el('i'));
    thinking.appendChild(dots);
    try {
      const askBody = new URLSearchParams({ q: question });
      if (SID) askBody.set('sid', SID);
      const response = await fetch(ASK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
        body: askBody,
        credentials: 'same-origin'
      });
      if (response.redirected || !response.ok) {
        // انتهت الجلسة أو السيرفر رجع تحويلة — رسالة صادقة مع الحل (بلا «تعذّر» مبهمة)
        thinking.textContent = '';
        const box = el('div', 'asst-note',
          response.redirected ? 'انتهت جلسة الدخول — حدّث الصفحة وسجّل الدخول من جديد.'
                              : 'الخدمة غير جاهزة الآن — حدّث الصفحة وحاول تاني.');
        const again = el('button', 'asst-fchip', 'تحديث الصفحة الآن');
        again.type = 'button';
        again.addEventListener('click', function () { window.location.reload(); });
        thinking.appendChild(box);
        thinking.appendChild(again);
        busy = false;
        return;
      }
      const data = await response.json();
      thinking.textContent = '';
      renderBlocks(thinking, data.title, data.blocks);
      if (!data.blocks || !data.blocks.length) thinking.textContent = data.reply || 'معلش، مفيش رد.';
      renderLinks(thinking, data.links);
      renderFollowups(data.followups, function (next) { send(next); });
      remember(question);
      if (data.navigate) { window.location.href = data.navigate; }
    } catch (error) {
      thinking.textContent = '';
      renderBlocks(thinking, '', [{ type: 'note',
        text: 'تعذّر الوصول للمساعد المحلي — افحص أن البرنامج شغّال ثم حدّث الصفحة.' }]);
    }
    busy = false;
    input.focus();
  }

  /* ---------- الفتح والإغلاق ---------- */
  function openPanel(open) {
    panel.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) input.focus();
  }

  /* الأسئلة السريعة تحت اللوحة: ضغطة = سؤال فوري (توجيه المستخدم: أسئلة مش تابات) */
  document.querySelectorAll('.asst-qlink[data-ask]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      openPanel(true);
      send(chip.getAttribute('data-ask'));
    });
  });

  btn.addEventListener('click', function () { openPanel(!panel.classList.contains('open')); });
  close.addEventListener('click', function () { openPanel(false); });
  toggle.addEventListener('click', function () {
    const collapsed = wrap.classList.toggle('collapsed');
    try { localStorage.setItem(KEY, collapsed ? '1' : '0'); } catch (e) {}
    if (collapsed) openPanel(false);
  });
  try {
    if (localStorage.getItem(KEY) === '1') wrap.classList.add('collapsed');
  } catch (e) {}

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    send(input.value);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && panel.classList.contains('open')) openPanel(false);
  });

  /* ---------- تبديل الموديل: قائمة منسدلة في الشات نفسه (بتوجيه المستخدم) ---------- */
  /* الخيارات: «المكتبة الذكية» (محرك البرنامج بلا أي موديل لغوي) + كل ملف GGUF باسمه. */
  function arabicDigits(text) {
    return String(text).replace(/[0-9]/g, function (digit) {
      return '٠١٢٣٤٥٦٧٨٩'[+digit];
    });
  }

  function modelHint(model) {
    const engineOk = !!model.engine;
    const count = Number(model.count || (model.models || []).length || 0);
    const extra = count ? ' — وفيه ' + arabicDigits(count) + ' ملف موديل في الفولدر تقدر تختاره' : '';
    if ((model.mode || 'local') === 'local') {
      return { text: 'محرك البرنامج — بلا موديل',
               title: '«المكتبة الذكية» شغالة: المساعد يجاوب من محرك البرنامج نفسه' + extra + '.' };
    }
    return { text: engineOk ? 'المكتبة ✓ شغالة' : 'المكتبة ✗ ناقصة',
             title: 'الموديل المختار: ' + (model.name || '') + (engineOk
               ? ' — محرك المكتبة الذكية شغال، والأسئلة المفتوحة ترد من الموديل.'
               : ' — لكن محرّك llama-cpp-python غير مثبّت: نفّذ مرة واحدة  pip install -r requirements-ai.txt') };
  }

  function paintModelSelect(model) {
    if (!modelInput || !modelList) return;
    model = model || {};
    lastModel = model;
    const models = model.models || [];
    const localLabel = model.local_label || 'المكتبة الذكية';
    modelLabelMap = {};
    modelLabelMap[localLabel] = model.local_value || '';
    modelList.textContent = '';
    const localOption = el('option');
    localOption.value = localLabel;
    modelList.appendChild(localOption);
    let activeLabel = localLabel;
    models.forEach(function (row) {
      const label = (row.label || row.name || '').replace(/\.gguf$/i, '');
      const shown = label + (row.valid ? '' : ' — ملف غير صالح');
      const option = el('option');
      option.value = shown;
      modelList.appendChild(option);
      modelLabelMap[shown] = row.name || '';
      if ((model.mode || 'local') === 'model' && (row.name || '') === model.name) {
        activeLabel = shown;
      }
    });
    modelInput.value = activeLabel;
    modelInput.disabled = false;
    modelInput.classList.toggle('warn', !!((model.mode === 'model') && !model.engine));
    modelInput.title = 'اختَر: «المكتبة الذكية» (محرك البرنامج بلا موديل) أو موديل GGUF بالاسم'
      + (model.folder ? ' — الفولدر: ' + model.folder : '');
    if (modelState) {
      const info = modelHint(model);
      modelState.textContent = info.text;
      modelState.title = info.title;
      modelState.classList.toggle('warn', info.text.indexOf('✗') !== -1);
    }
  }

  function refreshCapabilities() {
    /* حالة النموذج المحلي تُعرض بصدق على القائمة والشارة (بلا تظاهر بالتوفّر). */
    fetch(SID ? CAPABILITIES + (CAPABILITIES.includes('?') ? '&' : '?') + 'sid=' + encodeURIComponent(SID) : CAPABILITIES, { credentials: 'same-origin' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        const model = data.model || {};
        paintModelSelect(model);
        const tag = document.getElementById('asstTag');
        if (!tag) return;
        if (model.enabled) {
          tag.textContent = 'نموذج محلي: ' + (model.name || 'مفعّل');
          tag.title = 'نموذج محلي صغير داخل جهازك (' + (model.backend || '') + ') — بلا إنترنت.';
        } else if (model.mode === 'model' && !model.engine) {
          tag.textContent = 'محلي · موديل بلا محرّك';
          tag.title = 'اخترت موديلًا لكن حزمة llama-cpp-python غير مثبتة — '
            + 'المساعد يعمل بمحرك البرنامج.';
        } else if (model.file_found) {
          tag.textContent = 'محلي · ملف نموذج بلا محرّك';
          tag.title = 'ملف النموذج موجود لكن حزمة llama-cpp-python غير مثبتة — '
            + 'المساعد يعمل بمحرك النوايا المحلي.';
        }
      })
      .catch(function () {});
  }

  if (modelInput) modelInput.addEventListener('change', function () {
    const chosen = modelInput.value.trim();
    const name = Object.prototype.hasOwnProperty.call(modelLabelMap, chosen)
      ? modelLabelMap[chosen] : chosen;
    modelInput.disabled = true;
    fetch(MODEL_SELECT, { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(SID ? { name: name, sid: SID } : { name: name }) })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        openPanel(true);
        const status = data.status || {};
        paintModelSelect(status);
        const box = say('bot');
        const notes = [data.ok
          ? (status.mode === 'model'
              ? { type: 'note', text: 'جرّب الموديل بسؤال مفتوح: «اكتبلي جملة ترحيب قصيرة».' }
              : { type: 'note', text: 'المساعد يجاوب أسئلتك العادية من محرك البرنامج نفسه — '
                  + 'والأسئلة المفتوحة ترد من موديل لو اخترته من القائمة.' })
          : { type: 'note', text: 'الفولدر: ' + (data.folder || 'database/assistant/models')
              + ' — الخطوات بالتفصيل في ملف «اقرأني» جواه.' }];
        renderBlocks(box, 'تبديل الموديل',
          [{ type: 'p', text: data.message || '' }].concat(notes));
        if (data.ok && status.mode === 'model') {
          const chip = el('button', 'asst-fchip', 'جرّب سؤالًا مفتوحًا');
          chip.type = 'button';
          chip.addEventListener('click', function () { send('اكتبلي جملة ترحيب قصيرة'); });
          box.appendChild(chip);
        }
        log.scrollTop = log.scrollHeight;
        refreshCapabilities();
      })
      .catch(function () {
        paintModelSelect(lastModel || {});
        const box = say('bot');
        renderBlocks(box, 'تبديل الموديل', [{ type: 'note',
          text: 'تعذّر التبديل الآن — افحص أن البرنامج شغّال ثم حدّث الصفحة.' }]);
      })
      .then(function () { modelInput.disabled = false; });
  });

  fetch(SID ? PROMPTS + (PROMPTS.includes('?') ? '&' : '?') + 'sid=' + encodeURIComponent(SID) : PROMPTS, { credentials: 'same-origin' })
    .then(function (response) { return response.json(); })
    .then(function (data) { chips(data.prompts); })
    .catch(function () { chips([]); });
  paintHistory();
  refreshCapabilities();
})();
