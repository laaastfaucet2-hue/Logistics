/* محاذاة رؤوس الجداول مع نوع البيانات الفعلي في كل عمود. */
(function () {
  "use strict";

  var selector = "table";
  var scheduled = false;

  function cellsWithColumns(row) {
    var column = 0;
    return Array.prototype.map.call(row.cells || [], function (cell) {
      var span = Math.max(1, Number(cell.colSpan) || 1);
      var item = {cell: cell, start: column, span: span};
      column += span;
      return item;
    });
  }

  function cellKind(cell) {
    if (cell.classList.contains("name")) return "start";
    if (cell.matches(".ops,.actions,.wh-row-actions,.tm-ops")) return "actions";
    if (cell.matches(".num,.mid,.center,.check,.checkbox,.iv-num,.hl-ptnum,.hl-tnum")) return "center";
    if (cell.querySelector("input[type=checkbox],input[type=radio]")) return "center";
    if (cell.querySelector("input[inputmode=numeric],input[inputmode=decimal],input[type=number],input[type=date]")) return "center";
    if (cell.querySelector("bdi[dir=ltr],.date-display,time")) return "center";
    var controls = cell.querySelectorAll("button,.rt-btn,.icon-btn,form");
    var plainText = (cell.textContent || "").trim();
    if (controls.length && plainText.length < 80) return "actions";
    var compact = plainText.replace(/\s+/g, "");
    if (compact && /^[٠-٩0-9.,٫٬٪%+\-−–—/:()✓✗⊘]+$/.test(compact)) return "center";
    return "start";
  }

  function vote(columns, index, kind, weight) {
    if (kind === "start") return;
    if (!columns[index]) columns[index] = {center: 0, actions: 0};
    columns[index][kind] += weight || 1;
  }

  function preferredKind(votes) {
    if (!votes) return "";
    if (votes.actions > votes.center) return "actions";
    if (votes.center) return "center";
    return "";
  }

  function applyKind(cell, kind) {
    cell.classList.toggle("ui-col-center", kind === "center");
    cell.classList.toggle("ui-col-actions", kind === "actions");
  }

  function normalizeTable(table) {
    if (!table || table.dataset.tableAlign === "off") return;
    var columns = {};

    Array.prototype.forEach.call(table.tHead ? table.tHead.rows : [], function (row) {
      cellsWithColumns(row).forEach(function (item) {
        if (item.span !== 1) return;
        vote(columns, item.start, cellKind(item.cell), 3);
        if (!item.cell.hasAttribute("scope")) item.cell.setAttribute("scope", "col");
      });
    });

    Array.prototype.forEach.call(table.tBodies || [], function (body) {
      Array.prototype.forEach.call(body.rows || [], function (row) {
        cellsWithColumns(row).forEach(function (item) {
          if (item.span === 1) vote(columns, item.start, cellKind(item.cell), 1);
        });
      });
    });

    Array.prototype.forEach.call(table.rows || [], function (row) {
      cellsWithColumns(row).forEach(function (item) {
        var kinds = [];
        for (var i = item.start; i < item.start + item.span; i += 1) {
          kinds.push(preferredKind(columns[i]));
        }
        var first = kinds[0] || "";
        var same = kinds.every(function (kind) { return kind === first; });
        applyKind(item.cell, same ? first : "");
      });
    });
    table.classList.add("ui-table-normalized");
  }

  function normalizeAll() {
    scheduled = false;
    document.querySelectorAll(selector).forEach(normalizeTable);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(normalizeAll);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", normalizeAll);
  } else {
    normalizeAll();
  }

  if (window.MutationObserver) {
    new MutationObserver(schedule).observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }
  window.LogisticsTables = { refresh: normalizeAll };
})();
