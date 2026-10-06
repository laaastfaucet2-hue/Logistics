/* المساعد المحلي 🤖 — واجهة الشات: زر جانبي يُفتح ويُغلق مثل الإشعارات (٠٦/١٠/٢٠٢٦).
   كل الردود من /assistant/ask داخل البرنامج — لا إنترنت ولا خدمة خارجية. */
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
  const script = document.currentScript;
  if (!wrap || !btn || !panel || !form) return;

  const ASK = script.dataset.ask;
  const PROMPTS = script.dataset.prompts;
  const KEY = 'logistics.assistant.collapsed';

  function say(text, who) {
    const bubble = document.createElement('div');
    bubble.className = 'asst-msg ' + (who || 'bot');
    bubble.textContent = text;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  function links(container, items) {
    if (!items || !items.length) return;
    const box = document.createElement('div');
    box.className = 'asst-links';
    items.forEach(function (item) {
      const a = document.createElement('a');
      a.className = 'asst-link';
      a.href = item.href;
      a.textContent = '↗ ' + item.label;
      box.appendChild(a);
    });
    container.appendChild(box);
  }

  function chips(items) {
    promptsBox.innerHTML = '';
    (items || []).forEach(function (text) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'asst-chip';
      chip.textContent = text;
      chip.addEventListener('click', function () { send(text); });
      promptsBox.appendChild(chip);
    });
  }

  let busy = false;
  async function send(text) {
    const question = (text || input.value || '').trim();
    if (!question || busy) return;
    busy = true;
    input.value = '';
    say(question, 'me');
    const thinking = say('… بيفكر', 'bot');
    thinking.classList.add('asst-typing');
    try {
      const response = await fetch(ASK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
        body: new URLSearchParams({ q: question }),
        credentials: 'same-origin'
      });
      const data = await response.json();
      thinking.classList.remove('asst-typing');
      thinking.textContent = data.reply || 'معلش، مفيش رد دلوقتي.';
      links(thinking, data.links);
      if (data.navigate) { window.location.href = data.navigate; }
    } catch (error) {
      thinking.classList.remove('asst-typing');
      thinking.textContent = 'تعذّر الوصول للمساعد المحلي — جرّب تحديث الصفحة.';
    }
    busy = false;
    input.focus();
  }

  function openPanel(open) {
    panel.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open && !log.children.length) {
      say('أهلاً بيك 🤖 أنا المساعد المحلي للمنظومة.\n'
        + 'اكتب «مساعدة» أشوفك كل الأوامر، أو «افتح التاميدات»/«الراغبين»/«تنبيهات الشهر».');
      input.focus();
    }
  }

  btn.addEventListener('click', function () {
    openPanel(!panel.classList.contains('open'));
  });
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

  fetch(PROMPTS, { credentials: 'same-origin' })
    .then(function (response) { return response.json(); })
    .then(function (data) { chips(data.prompts); })
    .catch(function () { chips([]); });
})();
