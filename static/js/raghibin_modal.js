/* ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر
/* برمجة جديدة كاملة (٣٠/٠٩/٢٠٢٦ مساءً — توجيه المستخدم «عيد من الأول»):
   • زرار التأميدات يفتح صفحة كشف الراغبين الكاملة بتصفح عادي (بلا fetch نهائيًا).
   • داخل صفحة الكشف: بحث القوة + تبديل رتب الإضافة السريعة + التشيك ↔ المربعات
     + عداد «تم تحديث» — كلها لمس داخل الصفحة بلا أي طلبات خلفية.
   • الحفظ/الإضافة/التبديل كلها نماذج عادية تتصفح بـ sid في الرابط.
/* ١٤/١٠ — مودال منبثق من فورم التأميدة:
   • زر «تسجيل أسماء الضباط والأفراد الراغبين» في فورم التأميدة (حتى غير
     المحفوظ) يفتح القائمة **منبثقة** فوق الفورم — الفورم يفضل حي تحتها.
   • عدّادات الفورم (ضابط/فرد) تتمرر (o/i) فتفتح المربعات بعددها حتى لو
     التأميدة ماحفظتش — والمحفوظة لها الأولوية لو موجودة.
   • الحفظ جوه المودال بيحفظ الأسماء بس (لا يحفظ التأميدة) — الطلبات
     fetch جوه المودال والرجوع للجزء نفسه (الصفحة اللي تحت بتفضل مكانها).
   • من تاب الراغبين (الصفحة الكاملة) كل حاجة بتفضل تصفح عادي زي قبل. */
(function () {
  "use strict";

  /* ١٤/١٠: آخر جزء كشف معروض — نرجع له بعد الحفظ (في المودال أو الصفحة) */
  var ragPanelUrl = "";

  function toArabic(n) {
    var d = "٠١٣٤٥٦٧٨٩";
    return String(n).replace(/\d/g, function (x) { return d[+x]; });
  }

  function parseArabicInt(text) {
    var digits = "٠١٢٣٤٥٦٧٨٩";
    var s = String(text || "").trim();
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var d = digits.indexOf(s[i]);
      out += (d !== -1) ? String(d) : s[i];
    }
    var n = parseInt(out, 10);
    return isNaN(n) ? null : n;
  }

  function urlParam(name) {
    var m = new RegExp("[?&]" + name + "=([^&]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
  }

  /* ═══ تأكيد الأسماء الجديدة عند حفظ المربعات ═══ */
  function optionValues(listId) {
    var src = document.getElementById(listId);
    if (!src) return [];
    return Array.prototype.map.call(src.querySelectorAll("option"), function (o) {
      return o.value;
    });
  }

  /* ═══ الرتبة جزء من هوية الشخص (١٤/١٠) ═══
     «محمد أحمد محمد» برتبة مقدم ≠ «محمد أحمد محمد» برتبة عقيد.
     بنجمع كل أزواج (الرتبة، الاسم) المتاحة، من:
     • سكربت JSON محلي جوه الفورم (.rg-slot-ranks) — {اسم: رتبة}
     • سكربت JSON عام (#rgPersonRankData) — {فئة: [[رتبة, اسم], …]}
     اللي مالوش بيانات رتب يفضل على السلوك القديم (الاسم بس). */
  function addRankPair(map, rank, name) {
    name = String(name || "").trim();
    if (!name) return;
    if (!map[name]) map[name] = {};
    map[name][String(rank || "").trim()] = 1;
  }

  function rankMapFor(form) {
    var map = {};
    var nodes = [];
    if (form) {
      var local = form.querySelector(".rg-slot-ranks");
      if (local) nodes.push(local);
    }
    var global = document.getElementById("rgPersonRankData");
    if (global && nodes.indexOf(global) === -1) nodes.push(global);
    nodes.forEach(function (el) {
      var data;
      try { data = JSON.parse(el.textContent || "{}"); } catch (e) { return; }
      if (!data || typeof data !== "object") return;
      Object.keys(data).forEach(function (key) {
        var value = data[key];
        if (typeof value === "string") { addRankPair(map, value, key); return; }
        if (Object.prototype.toString.call(value) === "[object Array]") {
          value.forEach(function (pair) {
            if (Object.prototype.toString.call(pair) === "[object Array]") {
              addRankPair(map, pair[0], pair[1]);
            }
          });
        }
      });
    });
    return map;
  }

  /* true = مسجل بنفس رتبة الصف | false = موجود برتبة تانية (شخص جديد)
     | undefined = مفيش بيانات رتب → نرجع للسلوك القديم */
  function personKnown(input) {
    var row = input.closest(".rg-slotrow") || input.closest(".rg-slotcell");
    var sel = row ? row.querySelector(".rag-slot-rank") : null;
    if (!sel) return undefined;
    var name = (input.value || "").trim();
    if (!name) return true;
    var ranks = rankMapFor(input.closest("form"))[name];
    if (!ranks) return undefined;
    var rank = (sel.value || "").trim();
    if (!rank) return true;
    return !!(ranks[rank] || ranks[""]);
  }

  /* ١٣/١٠: كتابة اسم معروف تملأ مربع الرتبة في صفه تلقائيًا
     (بدون ما تفرغ اختيار صريح كان المستخدم عمليه). */
  function autoFillRank(input) {
    var row = input.closest(".rg-slotrow") || input.closest(".rg-slotcell");
    var sel = row ? row.querySelector(".rag-slot-rank") : null;
    var v = (input.value || "").trim();
    if (!sel || !v || sel.value) return;
    var maps = [];
    var form = input.closest("form");
    if (form) {
      var local = form.querySelector(".rg-slot-ranks");
      if (local) {
        try { maps.push(JSON.parse(local.textContent || "{}")); } catch (e) {}
      }
    }
    var g = document.getElementById("rgPersonRankData");
    if (g) {
      try {
        var gd = JSON.parse(g.textContent || "{}");
        var m = {};
        Object.keys(gd).forEach(function (k) {
          (gd[k] || []).forEach(function (pr) { if (pr[1]) m[pr[1]] = pr[0]; });
        });
        maps.push(m);
      } catch (e) {}
    }
    for (var i = 0; i < maps.length; i++) {
      var r = Object.prototype.hasOwnProperty.call(maps[i], v) ? maps[i][v] : "";
      if (!r) continue;
      for (var j = 0; j < sel.options.length; j++) {
        if (sel.options[j].value === r) { sel.value = r; return; }
      }
    }
  }

  function enhanceForms(root) {
    (root || document).querySelectorAll("form[data-ragboxes]").forEach(function (form) {
      if (form.dataset.ragReady) return;
      form.dataset.ragReady = "1";
      form.addEventListener("submit", function () {
        var slot = form.querySelector(".rag-slot");
        var known = slot ? optionValues(slot.getAttribute("data-combo")) : [];
        var box = form.querySelector(".rg-new-names");
        var fresh = [];
        try { fresh = JSON.parse(box ? box.value : "[]"); } catch (e) { fresh = []; }
        form.querySelectorAll(".rag-slot").forEach(function (input) {
          var name = (input.value || "").trim();
          if (!name) return;
          /* أسماء اتأكد منها فورًا (التنبيه تحت المربع) مش بيتسأل عنها تاني */
          if (fresh.indexOf(name) !== -1) return;
          /* ١٤/١٠: الرتبة جزء من الاسم — نفس الاسم برتبة مختلفة بيتسأل عشان
             يُضاف كشخص جديد، بدل ما يتجاهله السجل بصمت */
          var flag = personKnown(input);
          if (flag === true) return;
          if (flag === undefined && known.indexOf(name) !== -1) return;
          var ask = (flag === false)
            ? "«" + name + "» مسجّل في القوة برتبة مختلفة.\n" +
              "هل تريد إضافته كشخص جديد بنفس الاسم؟"
            : "«" + name + "» غير مسجّل في قوة هذه الجهة.\n" +
              "هل تريد إضافته كقوة دائمة للجهة؟";
          if (!window.confirm(ask)) {
            input.value = "";            /* رفض → المربع يفضى ولا يُحفظ */
          } else {
            fresh.push(name);            /* موافقة → يُضاف للقوة الدائمة */
          }
        });
        if (box) box.value = JSON.stringify(fresh);
      });
      /* تزامن الرتبة عند الكتابة في المربع (بحث ذكي / لصق) */
      form.querySelectorAll(".rag-slot").forEach(function (input) {
        input.addEventListener("change", function () { autoFillRank(input); });
      });
    });
  }

  window.RagBoxes = { enhance: enhanceForms };

  /* ═══════════════════════════════════════════════════════════════
     نطاق المودال — كل التفاعلات المحلية (تشتغل في الصفحة الكاملة
     وفي المودال المنبثق معًا)
     ═══════════════════════════════════════════════════════════════ */
  function bindModalScope(root) {
    if (!root || root.dataset.rgBound) return;
    root.dataset.rgBound = "1";

    function setFilledCount() {
      var filled = 0;
      root.querySelectorAll(".rag-slot").forEach(function (i) {
        if (i.value.trim()) filled++;
      });
      var chip = root.querySelector(".rg-filled-count");
      if (chip) chip.textContent = toArabic(filled);
    }

    function slotByName(name) {
      var found = null;
      root.querySelectorAll(".rag-slot").forEach(function (i) {
        if (!found && i.value.trim() === name) found = i;
      });
      return found;
    }

    function toggleByName(name, checked) {
      Array.prototype.forEach.call(
        root.querySelectorAll(".rg-force-toggle"), function (c) {
          if (c.getAttribute("data-name") === name) c.checked = checked;
        });
    }

    /* بحث القوة */
    var search = root.querySelector(".rg-force-search");
    if (search) search.addEventListener("input", function () {
      var q = search.value.trim();
      Array.prototype.forEach.call(root.querySelectorAll(".rg-force-item"),
        function (item) {
          item.hidden = !!q && item.getAttribute("data-name").indexOf(q) === -1;
        });
    });

    /* ═══ البحث الذكي المرتبط: قائمة الرتب + الأسماء تفلتر على الرتبة ═══ */
    var catSel = root.querySelector(".rg-qa-cat");
    var rankSel = root.querySelector(".rg-qa-rank");
    var nameDl = document.getElementById("rgNameDl");
    var rankOpts = {}, personRank = {};
    try { rankOpts = JSON.parse(document.getElementById("rgRankOptions").textContent || "{}"); } catch (e) {}
    try { personRank = JSON.parse(document.getElementById("rgPersonRankData").textContent || "{}"); } catch (e) {}
    function fillRankSel(cat) {
      if (!rankSel) return;
      var opts = rankOpts[cat] || [];
      rankSel.innerHTML = opts.map(function (r) {
        return "<option value=\"" + r + "\">" + r + "</option>";
      }).join("");
    }
    function fillNameDl(cat, rank) {
      if (!nameDl) return;
      var r = (rank || "").trim();
      var names = [];
      (personRank[cat] || []).forEach(function (pr) {
        if (!r || pr[0] === r) names.push(pr[1]);
      });
      nameDl.innerHTML = names.map(function (n) {
        return "<option value=\"" + n + "\"></option>";
      }).join("");
    }
    function refreshRegSearch() {
      var cat = catSel ? catSel.value : "officers";
      fillRankSel(cat);
      fillNameDl(cat, rankSel ? rankSel.value : "");
    }
    if (catSel) catSel.addEventListener("change", function () {
      refreshRegSearch();   /* غيّر الفئة → رتبها وأسماءها تتجدد */
    });
    if (rankSel) rankSel.addEventListener("change", function () {
      fillNameDl(catSel ? catSel.value : "officers", rankSel.value);
    });
    refreshRegSearch();

    /* ═══ تنبيه فوري للاسم اللي مش مسجل: إضافة كقوة دائمة / إلغاء ═══ */
    var approvedBox = root.querySelector(".rg-new-names");
    function approvedNames() {
      if (!approvedBox) return [];
      try { return JSON.parse(approvedBox.value || "[]"); } catch (e) { return []; }
    }
    function hideWarn(input) {
      var row = input.closest(".rg-slotrow");
      if (!row) return;
      var old = row.querySelector(".rg-slot-warn");
      if (old) old.remove();
    }
    function checkSlot(input) {
      hideWarn(input);
      var v = input.value.trim();
      if (!v) return;
      var known = {};
      optionValues(input.getAttribute("data-combo")).forEach(function (n) { known[n] = 1; });
      approvedNames().forEach(function (n) { known[n] = 1; });
      /* ١٤/١٠: الرتبة جزء من الاسم — نفس الاسم برتبة مختلفة = شخص جديد */
      var flag = personKnown(input);
      if (flag === true) return;
      if (flag === undefined && known[v]) return;
      var row = input.closest(".rg-slotrow");
      if (!row) return;
      var div = document.createElement("div");
      div.className = "rg-slot-warn";
      /* ١٤/١٠: «مش مسجل في الجهات والكوادر» كانت بتطلع لاسم مسجّل في جهة
         تانية أو برتبة تانية — الصياغة بقت عن قوة الجهة الحالية نفسها */
      var msg = (flag === false)
        ? "«" + v + "» مسجّل في القوة برتبة مختلفة — إضافته كشخص جديد بنفس الاسم؟"
        : "«" + v + "» غير مسجّل في قوة هذه الجهة — إضافته كقوة دائمة للجهة؟";
      div.innerHTML =
        "<span>" + msg + "</span>" +
        "<button type=\"button\" class=\"rg-warn-add\">إضافة كقوة دائمة</button>" +
        "<button type=\"button\" class=\"rg-warn-cancel\">إلغاء</button>";
      div.querySelector(".rg-warn-add").addEventListener("click", function () {
        var list = approvedNames();
        if (list.indexOf(v) === -1) { list.push(v); approvedBox.value = JSON.stringify(list); }
        hideWarn(input);
      });
      div.querySelector(".rg-warn-cancel").addEventListener("click", function () {
        input.value = "";
        input.dataset.prev = "";
        hideWarn(input);
        setFilledCount();
      });
      row.appendChild(div);
    }

    /* تشيك القوة ↔ المربعات */
    Array.prototype.forEach.call(root.querySelectorAll(".rg-force-toggle"),
      function (chk) {
        chk.addEventListener("change", function () {
          var name = chk.getAttribute("data-name");
          if (chk.checked) {
            var first = null;
            root.querySelectorAll(".rag-slot").forEach(function (i) {
              if (!first && !i.value.trim()) first = i;
            });
            if (first) {
              first.value = name; first.dataset.prev = name;
              /* ١٣/١٠: مربع الرتبة في نفس الصف ياخد رتبة العضو من القوة */
              var row = first.closest(".rg-slotrow");
              var sel = row && row.querySelector(".rag-slot-rank");
              if (sel && chk.dataset.rank) {
                for (var i = 0; i < sel.options.length; i++) {
                  if (sel.options[i].value === chk.dataset.rank) {
                    sel.value = chk.dataset.rank; break;
                  }
                }
              }
            }
          } else {
            var slot = slotByName(name);
            if (slot) { slot.value = ""; slot.dataset.prev = ""; }
          }
          setFilledCount();
        });
      });

    /* المربعات ↔ التشيك + عداد «تم تحديث» */
    Array.prototype.forEach.call(root.querySelectorAll(".rag-slot"),
      function (input) {
        input.dataset.prev = input.value.trim();
        input.addEventListener("input", function () {
          var v = input.value.trim();
          var prev = input.dataset.prev || "";
          if (v !== prev) {
            if (prev) toggleByName(prev, false);
            if (v) toggleByName(v, true);
            input.dataset.prev = v;
          }
          setFilledCount();
          checkSlot(input);
        });
      });
    setFilledCount();

    /* ═══ المودال المنبثق (١٤/١٠): الطلبات fetch جوه الديالوق —
       الفورم اللي تحت (التأميدة) يفضل حي، والحفظ ما يمشيش الصفحة. ═══ */
    var dialog = root.closest ? root.closest("dialog") : null;
    if (!dialog) return;
    var body = dialog.querySelector("#tmRagDialogBody") ||
               dialog.querySelector(".tm-rgdialog-body");
    if (!body) return;

    function toPanelUrl(u) {
      var m = u.match(/^(.*\/raghibin\/)(modal|panel)(.*)$/);
      return m ? m[1] + "panel" + m[3] : u;
    }

    /* السنة/الشهر من الصفحة — لينكات الجزء مش بتمررهم، فبنحافظ على السياق */
    var ctxYear = urlParam("year"), ctxMonth = urlParam("month");
    function withCtx(u) {
      var p;
      try { p = new URL(u, window.location.href); } catch (e) { return u; }
      if (ctxYear && !p.searchParams.has("year")) p.searchParams.set("year", ctxYear);
      if (ctxMonth && !p.searchParams.has("month")) p.searchParams.set("month", ctxMonth);
      return p.toString();
    }

    function swapFragment(html) {
      var doc = new DOMParser().parseFromString(html, "text/html");
      var frag = doc.querySelector(".rg-modal-form");
      if (!frag) {
        body.innerHTML = '<p class="rg-note err">لم يتحمل الكشف — جرّب مرة أخرى.</p>';
        return;
      }
      body.innerHTML = "";
      body.appendChild(frag);
      /* enhanceForms قبل bindModalScope — تأكيد الأسماء الجديدة لازم
         يمشي قبل ما FormData تتبنى في معالج الـ submit (نفس العنصر) */
      enhanceForms(frag);
      bindModalScope(frag);
      body.scrollTop = 0;
    }

    function loadPanel(url) {
      ragPanelUrl = url;
      fetch(withCtx(url), { credentials: "same-origin" })
        .then(function (r) {
          if (!r.ok) throw new Error("http " + r.status);
          return r.text();
        })
        .then(swapFragment)
        .catch(function () {
          body.innerHTML = '<p class="rg-note err">تعذّر تحميل القائمة — جرّب مرة أخرى.</p>';
        });
    }

    /* ١٤/١٠: بعد الحفظ السيرفر بيرجّع تحويل لصفحة كاملة (اليومية أو الراغبين)
       والرسالة بتبقى في الـquery — فبنرجّع الجزء تاني بنفس السياق + الرسالة. */
    function resumePanel(fd, finalUrl) {
      var base = ragPanelUrl;
      if (!base) return false;
      var p;
      try { p = new URL(base, window.location.href); } catch (e) { return false; }
      ["ok", "warn", "err"].forEach(function (k) { p.searchParams.delete(k); });
      /* اليوم/الفئة من الفورم نفسه — لو اتغيروا جوه النافذة */
      var fdDay = fd.get("d");
      if (fdDay && String(fdDay) !== "") p.searchParams.set("d", fdDay);
      var fdCat = fd.get("cat");
      if (fdCat && String(fdCat) !== "") p.searchParams.set("c", fdCat);
      var got = false;
      try {
        var src = new URL(finalUrl, window.location.href);
        ["ok", "warn", "err", "sid"].forEach(function (k) {
          var v = src.searchParams.get(k);
          if (v) { p.searchParams.set(k, v); got = true; }
        });
      } catch (e) { /* رابط غير قابل للقراءة — بنكمل بالرسالة الافتراضية */ }
      if (!got) p.searchParams.set("ok", "تم حفظ الكشف ✓");
      p.searchParams.set("_v", Date.now());   /* نسخة جديدة — بلا كاش */
      loadPanel(p.toString());
      return true;
    }

    /* كل النماذج جوه المودال → fetch + رجوع للجزء (بلا تصفح) */
    root.addEventListener("submit", function (e) {
      var f = e.target;
      if (!f || f.tagName !== "FORM" || !f.action) return;
      e.preventDefault();
      var method = (f.method || "get").toUpperCase();
      var action = f.action;
      var fd = new FormData(f);
      if (ctxYear && !fd.has("year")) fd.set("year", ctxYear);
      if (ctxMonth && !fd.has("month")) fd.set("month", ctxMonth);
      /* ١٤/١٠: كانت `redirect: "manual"` — والمتصفحات بترجّع رد مقفول
         (بدون حالة ولا مكان تحويل) فالحفظ كان بيتقري «فشل» رغم إنه بيتم
         فعلًا. دلوقتي بنتبع التحويل ونقرا الصفحة النهائية ونستخرج الجزء. */
      var opts = { credentials: "same-origin", method: method };
      if (method === "GET") {
        var query = [];
        fd.forEach(function (value, key) {
          query.push(encodeURIComponent(key) + "=" + encodeURIComponent(String(value)));
        });
        action += (action.indexOf("?") === -1 ? "?" : "&") + query.join("&");
        /* تغيير جهة القائمة داخل الديالوج: نطلب الجزء مباشرة ونحدّث رابط
           الرجوع، وإلا الحفظ التالي كان يرجع للجهة القديمة. */
        action = toPanelUrl(action);
        ragPanelUrl = withCtx(action);
      } else {
        opts.body = fd;
      }
      fetch(withCtx(action), opts)
        .then(function (r) {
          if (!r.ok) throw new Error("http " + r.status);
          var finalUrl = r.url || "";
          return r.text().then(function (t) { return { html: t, url: finalUrl }; });
        })
        .then(function (res) {
          var d = new DOMParser().parseFromString(res.html, "text/html");
          if (d.querySelector(".rg-modal-form")) {
            swapFragment(res.html);      /* الرد نفسه فيه الجزء → نستبدله */
            return;
          }
          /* الرد صفحة كاملة (اليومية/الراغبين) → نرجع الجزء بالرسالة */
          if (resumePanel(fd, res.url)) return;
          if (res.url.indexOf("/raghibin/modal") !== -1) {
            loadPanel(toPanelUrl(res.url));
            return;
          }
          throw new Error("no fragment");
        })
        .catch(function () {
          body.innerHTML = '<p class="rg-note err">تعذّر الحفظ — جرّب مرة أخرى.</p>';
        });
    });

    /* تابات الفئة + أي لينك /raghibin/modal → الجزء المنبثق مش صفحة */
    root.addEventListener("click", function (e) {
      var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
      if (!a) return;
      var href = a.getAttribute("href") || "";
      if (href.indexOf("/raghibin/modal") !== -1) {
        e.preventDefault();
        loadPanel(toPanelUrl(new URL(href, window.location.href).toString()));
        return;
      }
      /* «إلغاء» (الرجوع للتاميدات) → يقفل الديالوق والفورم تحت يفضل */
      if (href.indexOf("/tameedat") !== -1) {
        e.preventDefault();
        dialog.close();
      }
    });
  }

  /* صفحة الكشف الكاملة (من تاب الراغبين) — تفاعلاتها المحلية */
  var pageRoot = document.querySelector(".rg-modal-form");
  if (pageRoot) {
    bindModalScope(pageRoot);
    enhanceForms(pageRoot);
  }

  /* ═══ زرار «تسجيل أسماء» في فورم التاميدة → مودال منبثق (١٤/١٠) ═══ */
  var opener = document.getElementById("tmRagNamesBtn");
  if (opener) {
    opener.addEventListener("click", function () {
      var entityField = document.getElementById("tmEntity");
      var dayField = document.getElementById("tmDayFrom");
      var entity = entityField ? entityField.value.trim() : "";
      if (!entity) {
        window.alert("اكتب اسم القطاع في فورم التأميدة أولًا — ثم اضغط الزرار تاني.");
        return;
      }
      var day = parseArabicInt(dayField ? dayField.value : "") || 1;
      var sid = urlParam("sid");
      /* origin=tameedat يقصر قائمة الجهة على تأميدات اليوم فقط؛ draft_en
         يضيف جهة الفورم الحالية للقائمة حتى قبل حفظ تأميدتها. */
      var url = "/raghibin/panel?c=officers&d=" + day +
                "&en=" + encodeURIComponent(entity) +
                "&origin=tameedat&draft_en=" + encodeURIComponent(entity);
      /* السنة/الشهر من الصفحة الحالية — المودال لازم يفتح بنفس سياق التاميدة */
      var y = urlParam("year"), m = urlParam("month");
      if (y) url += "&year=" + encodeURIComponent(y);
      if (m) url += "&month=" + encodeURIComponent(m);
      /* عدّادات الفورم (ضابط/فرد) — المربعات تتبع الرقم المكتوب
         حتى لو التأميدة غير محفوظة */
      var form = opener.closest("form");
      if (form) {
        function val(name) {
          var el = form.querySelector('input[name="' + name + '"]');
          return el ? el.value : "";
        }
        url += "&o=" + (parseArabicInt(val("officers")) || 0) +
               "&i=" + (parseArabicInt(val("individuals")) || 0);
        /* ١٤/١٠: نوع الجهة المعتمد من فورم التأميدة (شرطية/حربية) —
           كان بيفتح على نوع القاموس الإنجليزي (workshop/salon) */
        var picked = form.querySelector('input[name="type_choice"]:checked');
        var et = picked ? (picked.value || "").trim() : "";
        if (et === "أخرى") {
          var other = document.getElementById("tmTypeOther");
          et = other && other.value.trim() ? other.value.trim() : "أخرى";
        }
        if (et) url += "&et=" + encodeURIComponent(et);
      }
      if (sid) url += "&sid=" + encodeURIComponent(sid);
      openRagDialog(url);
    });
  }

  function fullModalUrl(url) {
    return url.replace("/raghibin/panel", "/raghibin/modal");
  }

  function openRagDialog(url) {
    var dialog = document.getElementById("tmRagDialog");
    var body = document.getElementById("tmRagDialogBody");
    /* بلا ديالوج أو متصفح مش داعم للنافذة المنبثقة → صفحة الكشف الكاملة
       (أحسن من صندوق مفتوح جوّه الصفحة شكله مكسور) */
    if (!dialog || !body || typeof dialog.showModal !== "function") {
      window.location.href = fullModalUrl(url);
      return;
    }
    body.innerHTML = '<p class="rg-dim">جارٍ التحميل…</p>';
    if (!dialog.open) dialog.showModal();   /* مفتوح بالفعل → تحديث المحتوى فقط */
    loadPanelInto(url, body, dialog);
  }

  function loadPanelInto(url, body, dialog) {
    fetch(url, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("http " + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var frag = doc.querySelector(".rg-modal-form");
        if (!frag) {
          body.innerHTML = '<p class="rg-note err">لم يتحمل الكشف.</p>';
          return;
        }
        ragPanelUrl = url;
        body.innerHTML = "";
        body.appendChild(frag);
        enhanceForms(frag);
        bindModalScope(frag);
        body.scrollTop = 0;
      })
      .catch(function () {
        /* فشل التحميل → بديل واضح: الصفحة الكاملة بنفس السياق */
        body.innerHTML = '<p class="rg-note err">تعذّر فتح القائمة — جرّب مرة أخرى.</p>' +
          '<p class="rg-open-full"><a href="' + fullModalUrl(url) + '">' +
          "فتح الكشف في صفحة كاملة</a></p>";
      });
  }

  var closer = document.getElementById("tmRagDialogClose");
  if (closer) {
    closer.addEventListener("click", function () {
      var d = document.getElementById("tmRagDialog");
      if (d) d.close();
    });
  }
})();
