/* Authentication token and explicit monthly context; all service URLs are relative.
   توجيه ١٥/١٠: الرمز بيتحقن كذلك في أي فورم بيتضاف للصفحة *بعد* التحميل (فورمات
   الجلب/الـ fetch) — قبل كده فورم بديل كان بيطلع من غير الرمز فيطرد المستخدم
   لشاشة الدخول (حالة «تطبيق الجرد» في ٦ مخازن). */
(function () {
  "use strict";
  const sid = document.body.dataset.sid;
  if (sid) { try { localStorage.setItem("rations_sid", sid); } catch (_) {} }

  function enhanceForm(form) {
    if (!form || !form.querySelectorAll) return;
    if (sid && !form.querySelector('[name="sid"]')) {
      const input = document.createElement("input");
      input.type = "hidden"; input.name = "sid"; input.value = sid; form.appendChild(input);
    }
    if ((form.method || "get").toLowerCase() === "get") {
      ["year", "month"].forEach(function (name) {
        if (!form.querySelector('[name="' + name + '"]') && document.body.dataset[name]) {
          const input = document.createElement("input");
          input.type = "hidden"; input.name = name; input.value = document.body.dataset[name];
          form.appendChild(input);
        }
      });
    }
  }
  function enhance(root) {
    (root || document).querySelectorAll("form").forEach(enhanceForm);
  }
  window.LogisticsSession = { sid: sid, enhance: enhance };

  document.querySelectorAll('a[href^="/"]').forEach(function (a) {
    const u = new URL(a.getAttribute("href"), location.origin);
    if (sid && !u.searchParams.has("sid")) u.searchParams.set("sid", sid);
    a.setAttribute("href", u.pathname + u.search);
    if (u.pathname === "/logout") a.addEventListener("click", function () {
      try { localStorage.removeItem("rations_sid"); } catch (_) {}
    });
  });
  enhance(document);

  /* أي فورم يدخل الصفحة بعد كده (استبدال ورقة/جدول بالـ fetch) ياخد الرمز وكمان
     سنة/شهر لفورمات GET — نفس قواعد التحميل الأول. */
  if (window.MutationObserver) {
    new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        Array.prototype.forEach.call(m.addedNodes, function (node) {
          if (!node || node.nodeType !== 1) return;
          if (node.tagName === "FORM") { enhanceForm(node); return; }
          if (node.querySelectorAll) enhance(node);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }
})();
