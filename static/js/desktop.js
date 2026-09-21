/* Small native bridge: window controls only. No shell commands or arbitrary file access. */
(function () {
  "use strict";
  if (document.body.dataset.desktop !== "1") return;
  document.querySelectorAll('[target="_blank"]').forEach(a => a.removeAttribute("target"));
  document.querySelectorAll("[data-window]").forEach(function (button) {
    button.addEventListener("click", async function () {
      const api = window.pywebview?.api;
      if (!api) return;
      try { await api.window_action(button.dataset.window); }
      catch (_) { alert("تعذّر تنفيذ الأمر. يمكنك مراجعة سجل التشغيل من مجلد بيانات البرنامج."); }
    });
  });
  document.querySelectorAll("a[href]").forEach(function (a) {
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) a.addEventListener("click", e => e.preventDefault());
  });
})();
