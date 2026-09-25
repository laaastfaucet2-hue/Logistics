/* Day-first date logic. Digit alphabets/month names come from core via JSON.
   Date-only values are never passed to new Date(text), avoiding timezone shifts. */
(function () {
  'use strict';
  const node = document.getElementById('dateConfig');
  if (!node) return;
  const config = JSON.parse(node.textContent);
  const digits = config.digits;

  function western(value) {
    return String(value ?? '').replace(/[\u061c\u200e\u200f\u2066-\u2069]/g, '').trim()
      .split('').map(char => {
        const eastern = digits.eastern.indexOf(char), persian = digits.persian.indexOf(char);
        return eastern >= 0 ? digits.western[eastern] : persian >= 0 ? digits.western[persian] : char;
      }).join('');
  }
  function arabic(value) {
    return String(value).split('').map(char => {
      const index = digits.western.indexOf(char);
      return index >= 0 ? digits.eastern[index] : char;
    }).join('');
  }
  function utc(year, month, day) {
    const result = new Date(0);
    result.setUTCHours(0, 0, 0, 0);
    result.setUTCFullYear(year, month - 1, day);
    return result;
  }
  function checked(year, month, day) {
    if (![year, month, day].every(Number.isInteger) || year < 1 || year > 9999 || month < 1 || month > 12 || day < 1 || day > 31) return null;
    const result = utc(year, month, day);
    return result.getUTCFullYear() === year && result.getUTCMonth() + 1 === month && result.getUTCDate() === day ? { year, month, day } : null;
  }
  function parse(value) {
    if (value && typeof value === 'object') return checked(value.year, value.month, value.day);
    const text = western(value);
    let match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(text);
    if (match) return checked(+match[1], +match[2], +match[3]);
    match = /^([0-9]{1,2})\/([0-9]{1,2})\/([0-9]{4})$/.exec(text);
    if (match) return checked(+match[3], +match[2], +match[1]);
    if (/^[0-9]{8}$/.test(text)) return checked(+text.slice(4), +text.slice(2, 4), +text.slice(0, 2));
    return null;
  }
  function iso(value) {
    const d = parse(value);
    return d ? `${String(d.year).padStart(4, '0')}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}` : '';
  }
  function format(value) {
    const d = parse(value);
    return d ? arabic(`${String(d.day).padStart(2, '0')}/${String(d.month).padStart(2, '0')}/${String(d.year).padStart(4, '0')}`) : '';
  }
  function today() {
    try {
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: config.timeZone, calendar: 'gregory', numberingSystem: 'latn',
        year: 'numeric', month: '2-digit', day: '2-digit',
      }).formatToParts(new Date());
      const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
      return checked(+values.year, +values.month, +values.day) || parse(config.today);
    } catch (_) { return parse(config.today); }
  }
  function daysInMonth(year, month) { return utc(year, month + 1, 0).getUTCDate(); }
  function addDays(value, offset) {
    const d = parse(value);
    if (!d) return null;
    const result = utc(d.year, d.month, d.day + offset);
    return checked(result.getUTCFullYear(), result.getUTCMonth() + 1, result.getUTCDate());
  }
  window.LogisticsDates = { config, western, arabic, utc, parse, iso, format, today, daysInMonth, addDays };
})();
