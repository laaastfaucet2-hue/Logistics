/* Local Arabic calendar + fixed dd/mm/yyyy text inputs; no native US-format field. */
(function () {
  'use strict';
  const D = window.LogisticsDates;
  if (!D) return;
  let active = null, view = null, popover = null;
  const arrow = direction => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="${direction === 'right' ? 'm9 5 7 7-7 7' : 'm15 5-7 7 7 7'}"/></svg>`;

  function validate(input, normalize = true) {
    if (!input.value.trim()) {
      input.setCustomValidity(''); input.removeAttribute('aria-invalid'); return true;
    }
    const date = D.parse(input.value);
    const message = date ? '' : 'تاريخ غير صالح؛ اكتب يوم/شهر/سنة، مثال: ٢٢/٠٩/٢٠٢٦';
    input.setCustomValidity(message);
    if (date) {
      input.removeAttribute('aria-invalid');
      if (normalize) input.value = D.format(date);
    } else input.setAttribute('aria-invalid', 'true');
    return !!date;
  }
  function close(focus = false) {
    if (!active) return;
    const previous = active;
    previous.button.setAttribute('aria-expanded', 'false');
    popover.hidden = true;
    active = null;
    if (focus && previous.input.getClientRects().length) previous.input.focus();
  }
  function position() {
    if (!active) return;
    const field = active.input.getBoundingClientRect(), box = popover.getBoundingClientRect();
    const left = Math.max(12, Math.min(innerWidth - box.width - 12, field.right - box.width));
    const below = field.bottom + 7;
    const candidate = below + box.height <= innerHeight - 12 ? below : field.top - box.height - 7;
    const top = Math.max(12, Math.min(innerHeight - box.height - 12, candidate));
    popover.style.left = left + 'px'; popover.style.top = top + 'px';
  }
  function select(value) {
    if (!active) return;
    const input = active.input;
    input.value = value ? D.format(value) : '';
    validate(input);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    close(true);
  }
  function navigate(offset) {
    const month = D.utc(view.year, view.month + offset, 1);
    const next = D.parse({ year: month.getUTCFullYear(), month: month.getUTCMonth() + 1, day: 1 });
    if (next) { view = next; render(); }
  }
  function render(focusDate) {
    const selected = D.iso(active.input.value), today = D.iso(D.today());
    popover.querySelector('.date-month-title').textContent = D.config.months[view.month - 1] + ' ' + D.arabic(String(view.year).padStart(4, '0'));
    popover.querySelector('.date-month-input').value = D.config.months[view.month - 1];
    popover.querySelector('.date-year-input').value = D.arabic(String(view.year).padStart(4, '0'));
    popover.querySelector('.date-period-error').textContent = '';
    const grid = popover.querySelector('.date-days');
    grid.replaceChildren();
    const offset = (D.utc(view.year, view.month, 1).getUTCDay() + 1) % 7;
    for (let i = 0; i < offset; i++) grid.appendChild(document.createElement('span'));
    for (let day = 1; day <= D.daysInMonth(view.year, view.month); day++) {
      const value = { year: view.year, month: view.month, day }, key = D.iso(value);
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'date-day'; button.dataset.iso = key;
      button.textContent = D.arabic(day); button.title = D.format(value);
      button.setAttribute('aria-label', D.format(value));
      button.setAttribute('aria-pressed', String(key === selected));
      if (key === today) button.setAttribute('aria-current', 'date');
      button.addEventListener('click', () => select(value));
      button.addEventListener('keydown', event => {
        const offsets = { ArrowLeft: 1, ArrowRight: -1, ArrowUp: -7, ArrowDown: 7 };
        if (Object.hasOwn(offsets, event.key)) {
          event.preventDefault();
          const next = D.addDays(value, offsets[event.key]);
          if (next) { view = next; render(next); }
        } else if (event.key === 'PageUp' || event.key === 'PageDown') {
          event.preventDefault(); navigate((event.key === 'PageUp' ? -1 : 1) * (event.shiftKey ? 12 : 1));
          popover.querySelector('.date-day')?.focus();
        }
      });
      grid.appendChild(button);
    }
    popover.querySelector('[data-date-prev]').disabled = view.year === 1 && view.month === 1;
    popover.querySelector('[data-date-next]').disabled = view.year === 9999 && view.month === 12;
    position();
    if (focusDate) grid.querySelector(`[data-iso="${D.iso(focusDate)}"]`)?.focus();
  }
  function createPopover() {
    const box = document.createElement('section');
    box.id = 'arabicDatePicker'; box.className = 'date-popover'; box.hidden = true; box.dir = 'rtl'; box.lang = 'ar';
    box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'اختيار التاريخ — يوم/شهر/سنة');
    box.innerHTML = `<div class="date-calendar-head">
      <button type="button" class="icon-btn" data-date-prev title="الشهر السابق" aria-label="الشهر السابق">${arrow('right')}</button>
      <strong class="date-month-title" aria-live="polite"></strong>
      <button type="button" class="icon-btn" data-date-next title="الشهر التالي" aria-label="الشهر التالي">${arrow('left')}</button>
    </div>
    <div class="date-period-editor">
      <label>الشهر<input class="date-month-input" data-combo="datePickerMonths" autocomplete="off" aria-label="شهر التقويم"></label>
      <label>السنة<input class="date-year-input" inputmode="numeric" maxlength="4" dir="ltr" aria-label="سنة التقويم"></label>
      <button type="button" class="icon-btn date-period-go" title="عرض الشهر والسنة" aria-label="عرض الشهر والسنة">${arrow('left')}</button>
      <datalist id="datePickerMonths"></datalist>
    </div>
    <p class="date-period-error" role="status"></p>
    <div class="date-weekdays" aria-hidden="true"></div>
    <div class="date-days" role="group" aria-label="أيام الشهر"></div>
    <div class="date-calendar-foot"><button type="button" data-date-today><svg aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4m8-4v4M3 10h18m-12 4h3"/></svg>اليوم</button><button type="button" data-date-clear><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6m4-6v6"/></svg>مسح</button><button type="button" data-date-close><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m6 6 12 12M6 18 18 6"/></svg>إغلاق</button></div>`;
    D.config.months.forEach(name => {
      const option = document.createElement('option'); option.value = name;
      box.querySelector('datalist').appendChild(option);
    });
    D.config.weekdays.forEach(name => {
      const label = document.createElement('span'); label.textContent = name;
      box.querySelector('.date-weekdays').appendChild(label);
    });
    document.body.appendChild(box);
    window.LogisticsCombo?.enhance(box);
    box.querySelector('[data-date-prev]').onclick = () => navigate(-1);
    box.querySelector('[data-date-next]').onclick = () => navigate(1);
    box.querySelector('[data-date-today]').onclick = () => select(D.today());
    box.querySelector('[data-date-clear]').onclick = () => select(null);
    box.querySelector('[data-date-close]').onclick = () => close(true);
    const jump = () => {
      const month = D.config.months.indexOf(box.querySelector('.date-month-input').value) + 1;
      const year = Number(D.western(box.querySelector('.date-year-input').value));
      const value = D.parse({ year, month, day: 1 });
      if (!value) { box.querySelector('.date-period-error').textContent = 'اختر شهرًا وسنة صحيحين'; return; }
      view = value; render(); box.querySelector('.date-day')?.focus();
    };
    box.querySelector('.date-period-go').onclick = jump;
    box.querySelector('.date-year-input').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); jump(); } });
    box.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); close(true); } });
    box.addEventListener('focusout', () => setTimeout(() => {
      if (active && !box.contains(document.activeElement) && !active.wrapper.contains(document.activeElement)) close();
    }, 0));
    return box;
  }
  function open(input, button, wrapper) {
    if (active?.input === input) { close(true); return; }
    close();
    if (!popover) popover = createPopover();
    active = { input, button, wrapper }; view = D.parse(input.value) || D.today();
    popover.hidden = false; button.setAttribute('aria-expanded', 'true');
    render(view);
  }
  const forms = new Set();
  document.querySelectorAll('input[data-date]').forEach(input => {
    const wrapper = input.closest('.date-field'), button = wrapper.querySelector('.date-trigger');
    button.hidden = false; button.setAttribute('aria-controls', 'arabicDatePicker');
    button.addEventListener('click', () => open(input, button, wrapper));
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); open(input, button, wrapper); }
    });
    input.addEventListener('input', () => {
      input.setCustomValidity(''); input.removeAttribute('aria-invalid');
      if (/^[0-9]{8}$/.test(D.western(input.value)) && D.parse(input.value)) input.value = D.format(input.value);
    });
    input.addEventListener('blur', () => validate(input));
    if (input.form) forms.add(input.form);
  });
  forms.forEach(form => {
    form.addEventListener('submit', event => {
      const fields = [...form.querySelectorAll('input[data-date]')].filter(input => !input.disabled && !input.closest('[hidden]'));
      const invalid = fields.filter(input => !validate(input));
      if (invalid.length) { event.preventDefault(); invalid[0].focus(); invalid[0].reportValidity(); }
    }, true);
    form.addEventListener('reset', () => { close(); setTimeout(() => form.querySelectorAll('[data-date]').forEach(input => validate(input)), 0); });
  });
  document.addEventListener('pointerdown', e => { if (active && !popover.contains(e.target) && !active.wrapper.contains(e.target)) close(); });
  document.addEventListener('change', () => { if (active && !active.input.getClientRects().length) close(); });
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
})();
