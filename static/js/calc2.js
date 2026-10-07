// ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر
/* قائمة التأميدات حسب اليوم + مربع الإذن مجمّع حسب التأميدة. */
(function () {
  "use strict";
  var dataEl = document.getElementById("c2PicksData");
  var box = document.getElementById("c2Box");
  var jsonBox = document.getElementById("c2SelectedJson");
  var list = document.getElementById("c2List");
  if (!box || !jsonBox) return;
  var picks = [];
  try { picks = JSON.parse(dataEl && dataEl.textContent || "[]"); } catch (e) { picks = []; }
  var byKey = {};
  picks.forEach(function (p) { byKey[p.key] = p; });

  function ar(n) {
    return String(n).replace(/[0-9]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[d]; });
  }
  function chosen() {
    try {
      var raw = JSON.parse(jsonBox.value || "[]");
      return Array.isArray(raw) ? raw.filter(function (k) { return byKey[k]; }) : [];
    } catch (e) { return []; }
  }
  function forceTxt(p) {
    return "القوة: " + ar(p.officers + p.individuals + p.recruits) +
      " (ضباط " + ar(p.officers) + " · أفراد " + ar(p.individuals) +
      " · مجندين " + ar(p.recruits) + ")";
  }
  function groupsOf(keys) {
    var order = [], map = {};
    keys.forEach(function (k) {
      var p = byKey[k];
      if (!p) return;
      var rid = String(p.record_id);
      if (!map[rid]) {
        map[rid] = {
          record_id: p.record_id, title: p.group_title, color: p.color,
          range_label: p.range_label, day: p.day, day_to: p.day_to, picks: []
        };
        order.push(map[rid]);
      }
      map[rid].picks.push(p);
    });
    order.sort(function (a, b) { return a.day - b.day || a.record_id - b.record_id; });
    return order;
  }
  function markList(keys) {
    if (!list) return;
    var set = {};
    keys.forEach(function (k) { set[k] = true; });
    Array.prototype.forEach.call(list.querySelectorAll(".c2-pickrow"), function (el) {
      el.classList.toggle("on", !!set[el.getAttribute("data-key")]);
    });
  }
  function renderBox(keys) {
    jsonBox.value = JSON.stringify(keys);
    box.innerHTML = "";
    var tms = groupsOf(keys);
    if (!tms.length) {
      var em = document.createElement("span");
      em.className = "c2-box-empty";
      em.id = "c2Empty";
      em.textContent = "المربع فاضي — اختر جهة من قائمة التأميدات بالأعلى";
      box.appendChild(em);
    } else {
      tms.forEach(function (tm) {
        var wrap = document.createElement("div");
        wrap.className = "c2-tm c" + tm.color;
        wrap.setAttribute("data-rid", tm.record_id);
        var head = document.createElement("div");
        head.className = "c2-tm-head";
        head.textContent = "تأميدة «" + tm.title + "» — " + tm.range_label;
        wrap.appendChild(head);
        tm.picks.forEach(function (p) {
          var span = document.createElement("span");
          span.className = "c2-chip";
          span.setAttribute("data-key", p.key);
          var b = document.createElement("b");
          b.textContent = p.name;
          span.appendChild(b);
          var sm = document.createElement("small");
          if (p.is_attachment) { sm.textContent = "ملحقة"; }
          else { sm.className = "main"; sm.textContent = "رئيسية"; }
          span.appendChild(sm);
          var fr = document.createElement("span");
          fr.className = "c2-chip-force";
          fr.textContent = forceTxt(p);
          span.appendChild(fr);
          var x = document.createElement("button");
          x.type = "button";
          x.className = "c2-x";
          x.setAttribute("aria-label", "إزالة");
          x.textContent = "×";
          span.appendChild(x);
          wrap.appendChild(span);
        });
        box.appendChild(wrap);
      });
    }
    var off = 0, ind = 0, rec = 0, names = [];
    keys.forEach(function (k) {
      var p = byKey[k];
      if (!p) return;
      off += p.officers; ind += p.individuals; rec += p.recruits;
      names.push(p.name);
    });
    var o = document.getElementById("c2Off");
    var i = document.getElementById("c2Ind");
    var r = document.getElementById("c2Rec");
    var lab = document.getElementById("c2Label");
    var f = document.getElementById("c2Force");
    var cnt = document.getElementById("c2BoxCount");
    if (o) o.value = ar(off);
    if (i) i.value = ar(ind);
    if (r) r.value = ar(rec);
    if (lab) lab.value = names.join(" + ");
    if (f) f.textContent = ar(off + ind + rec);
    if (cnt) cnt.textContent = "(" + ar(keys.length) + ")";
    markList(keys);
    loadRows(keys);
  }
  function qty3(n) {
    var x = Number(n);
    if (!isFinite(x)) x = 0;
    return ar(x.toFixed(3)).replace(".", "٫");
  }
  function mealCell(it) {
    var html = "<div class=\"c2-pp\">" +
      "<div class=\"c2-meal\"><span>فطار</span><b>" + qty3(it.breakfast) + "</b></div>" +
      "<div class=\"c2-meal\"><span>غداء</span><b>" + qty3(it.lunch) + "</b></div>" +
      "<div class=\"c2-meal\"><span>عشاء</span><b>" + qty3(it.dinner) + "</b></div>";
    if (it.customized) {
      html += "<div class=\"c2-pp-cus\"><em>مخصص من التأميدة</em>" +
        "<div class=\"c2-meal\"><span>فطار</span><b>" + qty3(it.custom_breakfast) + "</b></div>" +
        "<div class=\"c2-meal\"><span>غداء</span><b>" + qty3(it.custom_lunch) + "</b></div>" +
        "<div class=\"c2-meal\"><span>عشاء</span><b>" + qty3(it.custom_dinner) + "</b></div></div>";
    }
    return html + "</div>";
  }
  function fillBody(prefix, rows) {
    var tb = document.getElementById("c2Body-" + prefix);
    if (!tb) return;
    if (!rows || !rows.length) {
      tb.innerHTML = "<tr><td colspan=\"8\" class=\"empty\">أضف جهة للمربع بالأعلى لظهور الأصناف — أو خصّص المقررات من التأميدة.</td></tr>";
      return;
    }
    tb.innerHTML = rows.map(function (it) {
      var unit = it.unit ? " <small>" + it.unit + "</small>" : "";
      return "<tr>" +
        "<td class=\"num\" title=\"مسلسل\">" + ar(it.serial) + "</td>" +
        "<td class=\"name\"><b></b>" + unit + "</td>" +
        "<td>" + mealCell(it) + "</td>" +
        "<td class=\"num\">" + ar(it.days) + "</td>" +
        "<td class=\"num\">" + qty3(it.auto) + "</td>" +
        "<td><input name=\"actual_" + prefix + "_" + it.name + "\" class=\"c2-actual\" inputmode=\"decimal\" value=\"" + qty3(it.auto) + "\"></td>" +
        "<td class=\"num c2-avail\" data-item=\"" + it.name + "\"></td>" +
        "<td class=\"c2-state\" data-item=\"" + it.name + "\"></td>" +
        "</tr>";
    }).join("");
    Array.prototype.forEach.call(tb.querySelectorAll("td.name b"), function (b, i) {
      b.textContent = rows[i].name;
    });
  }
  var rowsUrl = (document.currentScript && document.currentScript.getAttribute("data-rows")) || "/calc2/rows";
  function loadRows(keys) {
    var fromEl = document.querySelector("[name=date_from]");
    var toEl = document.querySelector("[name=date_to]");
    var daysEl = document.querySelector("[name=issue_days]");
    var url = rowsUrl + (rowsUrl.indexOf("?") >= 0 ? "&" : "?") +
      "from=" + encodeURIComponent(fromEl ? fromEl.value : "") +
      "&to=" + encodeURIComponent(toEl ? toEl.value : "") +
      "&days=" + encodeURIComponent(daysEl ? daysEl.value : "") +
      "&selected=" + encodeURIComponent(JSON.stringify(keys || []));
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        fillBody("tamween", data.tamween || []);
        fillBody("contractor", data.contractor || []);
        refreshStock("tamween");
        refreshStock("contractor");
      })
      .catch(function () { /* الإبقاء على الجدول الحالي */ });
  }
  var stockUrl = (document.currentScript &&
    document.currentScript.getAttribute("data-stock-url")) || "/calc2/stock";
  function rowNeeded(prefix, name) {
    var input = document.querySelector("[name=\"actual_" + prefix + "_" + name + "\"]");
    var v = input ? input.value : "";
    v = String(v).replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
                 .replace("٫", ".");
    var n = parseFloat(v);
    return isFinite(n) ? n : 0;
  }
  function paint(prefix, info) {
    var tb = document.getElementById("c2Body-" + prefix);
    if (!tb) return;
    Object.keys(info.items || {}).forEach(function (name) {
      var st = info.items[name];
      var cell = tb.querySelector(".c2-avail[data-item=\"" + name + "\"]");
      var state = tb.querySelector(".c2-state[data-item=\"" + name + "\"]");
      if (cell) {
        cell.innerHTML = qty3(st.avail) + (st.unit ? " " + st.unit : "") +
          (st.pack ? " — " + st.pack : "") +
          "<small class=\"c2-aval-after\">بعد الإذن: " + qty3(st.remaining) +
          (st.unit ? " " + st.unit : "") + "</small>";
      }
      if (state) {
        state.className = "c2-state " + st.key;
        state.textContent = st.status;
      }
    });
    var legend = document.querySelector(".c2-stock-legend");
    if (legend && info.totals) {
      legend.innerHTML = "<i class=\"c2-dot safe\"></i> آمن " + ar(info.totals["آمن"] || 0) +
        "<i class=\"c2-dot low\"></i> يوشك على النفاذ " + ar(info.totals["يوشك على النفاذ"] || 0) +
        "<i class=\"c2-dot none\"></i> لا يوجد " + ar(info.totals["لا يوجد"] || 0);
    }
  }
  function refreshStock(prefix) {
    var tb = document.getElementById("c2Body-" + prefix);
    if (!tb) return;
    var parts = [];
    Array.prototype.forEach.call(tb.querySelectorAll(".c2-avail[data-item]"), function (cell) {
      var name = cell.getAttribute("data-item");
      parts.push(name + ":" + rowNeeded(prefix, name));
    });
    if (!parts.length) return;
    var url = stockUrl + (stockUrl.indexOf("?") >= 0 ? "&" : "?") +
      "section=" + encodeURIComponent(prefix) + "&items=" + encodeURIComponent(parts.join(","));
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (info) { paint(prefix, info); })
      .catch(function () { /* تبقى آخر أرصدة معروضة */ });
  }
  var stockTimer = null;
  document.addEventListener("input", function (ev) {
    var el = ev.target;
    if (!el || !el.classList || !el.classList.contains("c2-actual")) return;
    var m = /^actual_(tamween|contractor)_/.exec(el.getAttribute("name") || "");
    if (!m) return;
    clearTimeout(stockTimer);
    stockTimer = setTimeout(function () { refreshStock(m[1]); }, 600);
  });
  function toggle(key) {
    if (!key || !byKey[key]) return;
    var keys = chosen();
    var i = keys.indexOf(key);
    if (i >= 0) keys.splice(i, 1);
    else keys.push(key);
    renderBox(keys);
  }
  box.addEventListener("click", function (ev) {
    if (!ev.target.classList.contains("c2-x")) return;
    var chip = ev.target.closest(".c2-chip");
    if (chip) toggle(chip.getAttribute("data-key"));
  });
  if (list) {
    list.addEventListener("click", function (ev) {
      var row = ev.target.closest(".c2-pickrow");
      if (row) toggle(row.getAttribute("data-key"));
    });
  }
  renderBox(chosen());
})();
