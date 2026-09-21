(function () {
  const input = document.getElementById("password"), toggle = document.getElementById("togglePassword");
  toggle.addEventListener("click", () => { input.type = input.type === "password" ? "text" : "password"; toggle.textContent = input.type === "password" ? "إظهار" : "إخفاء"; });
  try {
    if (new URLSearchParams(location.search).get("expired") === "1") {
      localStorage.removeItem("rations_sid"); document.getElementById("expiredMsg").style.display = "block";
    } else {
      const sid = localStorage.getItem("rations_sid");
      if (sid) location.replace("/dashboard?sid=" + encodeURIComponent(sid));
    }
  } catch (_) {}
})();
