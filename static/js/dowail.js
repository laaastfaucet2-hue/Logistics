// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
/* تفاعلات تفاريد الدولى: تخصيص المعدلات، فترات الخطوط، والأقسام القابلة للفتح. */
(function () {
  "use strict";

  if (window.LogisticsCombo) window.LogisticsCombo.enhance(document);

  document.querySelectorAll("[data-dw-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.getElementById(button.getAttribute("data-dw-toggle"));
      if (!target) return;
      target.hidden = !target.hidden;
      button.classList.toggle("on", !target.hidden);
    });
  });

  function arabicDigits(value) {
    return String(value || "").replace(/[0-9]/g, function (digit) {
      return "٠١٢٣٤٥٦٧٨٩"[Number(digit)];
    }).replace(".", "٫");
  }

  var lineSelect = document.getElementById("dwLineSelect");
  if (lineSelect) {
    lineSelect.addEventListener("change", function () {
      var option = lineSelect.options[lineSelect.selectedIndex];
      var fromInput = document.getElementById("dwPeriodFrom");
      var toInput = document.getElementById("dwPeriodTo");
      if (fromInput) {
        fromInput.value = arabicDigits(option.getAttribute("data-from"));
        fromInput.min = option.getAttribute("data-from") || "1";
        fromInput.max = option.getAttribute("data-to") || "31";
      }
      if (toInput) {
        toInput.value = arabicDigits(option.getAttribute("data-to"));
        toInput.min = option.getAttribute("data-from") || "1";
        toInput.max = option.getAttribute("data-to") || "31";
      }
    });
  }

  var modal = document.getElementById("customModal");
  if (!modal) return;
  var form = document.getElementById("customForm");
  var nameSpan = document.getElementById("customItemName");
  var rows = document.getElementById("dateCustomRows");
  var template = document.getElementById("dateCustomTemplate");
  var meals = ["breakfast", "lunch", "dinner"];

  function closeModal() {
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
  }

  function addDateRow(entry) {
    if (!template || !rows) return;
    var fragment = template.content.cloneNode(true);
    var row = fragment.querySelector(".dw-date-custom-row");
    if (entry) {
      row.querySelector('[name="date_day"]').value = arabicDigits(entry.day);
      row.querySelector('[name="date_meal"]').value = entry.meal || "breakfast";
      row.querySelector('[name="date_qty"]').value = arabicDigits(entry.qty);
      row.querySelector('[name="date_mode"]').value = entry.mode || "add";
    }
    row.querySelector(".js-remove-date").addEventListener("click", function () {
      row.remove();
    });
    rows.appendChild(fragment);
  }

  document.getElementById("customClose").addEventListener("click", closeModal);
  document.getElementById("customCancel").addEventListener("click", closeModal);
  modal.addEventListener("click", function (event) {
    if (event.target === modal) closeModal();
  });
  document.getElementById("addDateCustom").addEventListener("click", function () {
    addDateRow(null);
  });

  document.querySelectorAll(".custom-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var weekly = [];
      var dates = [];
      try { weekly = JSON.parse(button.getAttribute("data-weekly") || "[]"); } catch (ignore) {}
      try { dates = JSON.parse(button.getAttribute("data-dates") || "[]"); } catch (ignore) {}

      nameSpan.textContent = button.getAttribute("data-name") || "";
      document.getElementById("customSection").value = button.getAttribute("data-section") || "";
      document.getElementById("customName").value = button.getAttribute("data-name") || "";
      document.getElementById("customUnit").value = button.getAttribute("data-unit") || "";
      document.getElementById("customExtra").value = button.getAttribute("data-extra") || "0";

      for (var weekday = 0; weekday < 7; weekday += 1) {
        meals.forEach(function (meal) {
          var input = form.querySelector('[name="c_' + weekday + "_" + meal + '"]');
          if (input) input.value = "";
        });
      }
      weekly.forEach(function (entry) {
        var input = form.querySelector('[name="c_' + entry.weekday + "_" + entry.meal + '"]');
        if (input) input.value = arabicDigits(entry.qty);
      });
      rows.innerHTML = "";
      dates.forEach(addDateRow);

      var target = form.getAttribute("data-template") || "";
      form.action = target.replace("/custom/0", "/custom/" + (button.getAttribute("data-id") || "0"));
      modal.classList.add("show");
      modal.setAttribute("aria-hidden", "false");
    });
  });
})();
