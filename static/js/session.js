/* Authentication token and explicit monthly context; all service URLs are relative. */
(function () {
  "use strict";
  const sid = document.body.dataset.sid;
  if (sid) { try { localStorage.setItem("rations_sid", sid); } catch (_) {} }
  document.querySelectorAll('a[href^="/"]').forEach(function (a) {
    const u = new URL(a.getAttribute("href"), location.origin);
    if (sid && !u.searchParams.has("sid")) u.searchParams.set("sid", sid);
    a.setAttribute("href", u.pathname + u.search);
    if (u.pathname === "/logout") a.addEventListener("click", function () {
      try { localStorage.removeItem("rations_sid"); } catch (_) {}
    });
  });
  document.querySelectorAll("form").forEach(function (form) {
    if (sid && !form.querySelector('[name="sid"]')) {
      const input = document.createElement("input");
      input.type = "hidden"; input.name = "sid"; input.value = sid; form.appendChild(input);
    }
    if ((form.method || "get").toLowerCase() === "get") {
      ["year", "month"].forEach(function (name) {
        if (!form.querySelector('[name="' + name + '"]') && document.body.dataset[name]) {
          const input = document.createElement("input");
          input.type = "hidden"; input.name = name; input.value = document.body.dataset[name]; form.appendChild(input);
        }
      });
    }
  });
})();
