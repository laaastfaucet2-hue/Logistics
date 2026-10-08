// صفحة التوثيق والمناسبات — تكبير الصور بتنقّل كامل + رفع الملفات بالتقدم (بلا إنترنت)
(function () {
  "use strict";

  /* ——— ١) عارض الصور: تكبير + أسهم تنقّل + عدّاد بالعربي ——— */
  var box = document.getElementById("ocLightbox");
  if (box) {
    var img = box.querySelector("img");
    var count = document.getElementById("ocLbCount");
    var photos = [].slice.call(document.querySelectorAll(".oc-photo img"));
    var current = 0;
    var AR = "٠١٢٣٤٥٦٧٨٩";
    function arabic(n) {
      return String(n).replace(/\d/g, function (d) { return AR[+d]; });
    }
    function show(index) {
      if (!photos.length) return;
      current = (index + photos.length) % photos.length;
      var el = photos[current];
      img.src = el.getAttribute("data-full") || el.src;
      if (count) count.textContent = arabic(current + 1) + " / " + arabic(photos.length);
    }
    function open(index) {
      show(index);
      box.hidden = false;
      document.body.style.overflow = "hidden";
    }
    function close() {
      box.hidden = true;
      img.src = "";
      document.body.style.overflow = "";
    }
    photos.forEach(function (el, index) {
      el.style.cursor = "zoom-in";
      el.addEventListener("click", function () { open(index); });
    });
    var prev = document.getElementById("ocLbPrev");
    var next = document.getElementById("ocLbNext");
    if (prev) prev.addEventListener("click", function (ev) { ev.stopPropagation(); show(current - 1); });
    if (next) next.addEventListener("click", function (ev) { ev.stopPropagation(); show(current + 1); });
    box.addEventListener("click", function (ev) {
      if (ev.target === box || ev.target.classList.contains("oc-lb-close")) close();
      else if (ev.target === img) show(current + 1);
    });
    document.addEventListener("keydown", function (ev) {
      if (box.hidden) return;
      if (ev.key === "Escape") close();
      else if (ev.key === "ArrowLeft") show(current - 1);
      else if (ev.key === "ArrowRight") show(current + 1);
    });
  }

  /* ——— ٢) معاينة الورق الحية (مثل تاب الصحة): حقل ← ورق فورًا، وWord يُبنى من هنا ——— */
  var editForm = document.getElementById("ocEditForm");
  if (editForm) {
    var pvStatus = document.getElementById("ocPvStatus");
    function sayStatus(message, isError) {
      if (!pvStatus) return;
      pvStatus.textContent = message || "";
      pvStatus.hidden = !message;
      pvStatus.classList.toggle("err", !!isError);
    }
    function targets(key) {
      return [].slice.call(document.querySelectorAll('[data-ocval="' + key + '"]'));
    }
    function paint(key, value) {
      targets(key).forEach(function (target) {
        target.textContent = value === "" ? "—" : value;      // لا خانة فراغ في الورق
        target.classList.toggle("oc-live-dirty", !!value);
      });
    }
    function bindField(input, key) {
      if (!input || !targets(key).length) return;
      targets(key).forEach(function (target) {
        target.classList.add("oc-live");
        if (input.tagName === "TEXTAREA") target.style.whiteSpace = "pre-wrap";
      });
      input.addEventListener("input", function () { paint(key, input.value); });
    }
    [].slice.call(editForm.querySelectorAll("[data-ockey]")).forEach(function (input) {
      bindField(input, input.getAttribute("data-ockey"));
    });
    bindField(editForm.querySelector('[name="date_iso"]'), "date_iso");   // حقل التقويم بالماكرو

    /* الحفظ من المعاينة: كل أزرار الورق تمر من هنا — تبنى Word/Excel من القيم المعروضة */
    var reportBase = editForm.getAttribute("data-report") || "";
    var saving = false;
    function postSave(done, fail) {
      if (saving) return;
      saving = true;
      var body = new FormData(editForm);
      body.append("json", "1");
      fetch(editForm.action, { method: "POST", credentials: "same-origin", body: body,
          headers: { "Accept": "application/json" } })
        .then(function (response) {
          return response.json().then(function (data) { return { ok: response.ok, data: data }; });
        })
        .then(function (result) {
          if (!result.ok || !result.data.ok) {
            fail((result.data && result.data.message) || "تعذّر الحفظ — راجع الحقول وحاول تاني");
            return;
          }
          done(result.data);
        })
        .catch(function () {
          fail("تعذّر الحفظ الآن — تأكد أن البرنامج شغّال ثم حاول تاني");
        })
        .then(function () { saving = false; });
    }
    [].slice.call(document.querySelectorAll("[data-ocdl]")).forEach(function (button) {
      button.addEventListener("click", function () {
        var kind = button.getAttribute("data-ocdl");
        if (!reportBase) return;
        var label = kind === "docx" ? "Word" : "Excel";
        sayStatus("جارٍ حفظ التعديل وبناء «" + label + "»…");
        postSave(function () {
          sayStatus("تم الحفظ وبناء «" + label + "» — بدأ التنزيل");
          window.location.href = reportBase + "&kind=" + encodeURIComponent(kind);
        }, function (message) { sayStatus(message, true); });
      });
    });

    /* ——— التعديل مباشرة على الورق: اكتب جوّه الورق والنموذج يتبع، و«حفظ الورق» يبنى الملفات ——— */
    var paperBox = document.getElementById("ocPaper");
    var paperEditBtn = document.getElementById("ocPaperEdit");
    var paperSaveBtn = document.getElementById("ocPaperSave");
    var paperHint = document.getElementById("ocPaperHint");
    var EDIT_KEYS = ["title", "kind", "date_iso", "place", "force_text", "frame", "notes"];
    var editing = false;
    function paperCells(key) {
      return [].slice.call(document.querySelectorAll('#ocPaper [data-ocval="' + key + '"]'));
    }
    function paperEditMode(on) {
      editing = on;
      paperBox.classList.toggle("oc-editing", on);
      EDIT_KEYS.forEach(function (key) {
        paperCells(key).forEach(function (cell) {
          if (on) {
            cell.setAttribute("contenteditable", "true");
            cell.setAttribute("spellcheck", "false");
          } else {
            cell.removeAttribute("contenteditable");
          }
        });
      });
      paperEditBtn.textContent = on ? "إلغاء التعديل على الورق" : "تعديل على الورق";
      paperSaveBtn.hidden = !on;
      paperHint.textContent = on
        ? "اكتب في العنوان أو أي خانة على الورق — الخانة الفاضية «—» اكتب فوقها مباشرة"
        : "اضغط «تعديل على الورق» واكتب جوّه الورق نفسه — أو عدّل من الحقول، والاثنان متصلان";
      sayStatus("");
    }
    if (paperBox && paperEditBtn && paperSaveBtn && paperHint) {
      paperEditBtn.addEventListener("click", function () { paperEditMode(!editing); });
      EDIT_KEYS.forEach(function (key) {
        paperCells(key).forEach(function (cell) {
          cell.addEventListener("focus", function () {
            if (cell.innerText.trim() === "—" || cell.innerHTML === "&nbsp;") cell.textContent = "";
          });
          cell.addEventListener("input", function () {
            var value = cell.innerText.replace(/\n+$/, "");
            var field = editForm.querySelector('[name="' + key + '"]');
            if (field) field.value = value;                 // النموذج يتبع الورق في الحفظ والتنزيل
            paperCells(key).forEach(function (other) {
              if (other === cell) return;                   // الخانة اللي بتتكتب ما تتحركش من تحت المؤشر
              other.textContent = value === "" ? "—" : value;
              other.classList.toggle("oc-live-dirty", !!value);
            });
          });
          cell.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" && key !== "notes") {    // سطر واحد لكل بند إلا الوصف
              ev.preventDefault();
              cell.blur();
            }
          });
        });
      });
      paperSaveBtn.addEventListener("click", function () {
        sayStatus("جارٍ حفظ الورق وبناء Word وExcel…");
        postSave(function () {
          paperEditMode(false);
          sayStatus("تم حفظ الورق وبناء تقرير Word وExcel");
        }, function (message) { sayStatus(message, true); });
      });
    }

    /* ——— إخفاء/إظهار الورق لتوسيع مساحة الشغل — والاختيار يفضل محفوظ ——— */
    var pvPanel = document.getElementById("ocPvPanel");
    var pvToggle = document.getElementById("ocPvToggle");
    var HIDE_KEY = "ocPaperHidden";
    function setPaperHidden(hidden) {
      pvPanel.classList.toggle("oc-pv-off", hidden);
      pvToggle.textContent = hidden ? "إظهار الورق" : "إخفاء الورق";
      pvToggle.title = hidden ? "إظهار ورق المعاينة" : "إخفاء الورق وإظهاره لتوسيع مساحة الشغل";
      try { window.localStorage.setItem(HIDE_KEY, hidden ? "1" : "0"); } catch (err) { /* بلا تخزين محلي */ }
    }
    if (pvPanel && pvToggle) {
      var stored = null;
      try { stored = window.localStorage.getItem(HIDE_KEY); } catch (err) { stored = null; }
      setPaperHidden(stored === "1");
      pvToggle.addEventListener("click", function () {
        setPaperHidden(!pvPanel.classList.contains("oc-pv-off"));
      });
    }

    /* طباعة الورقة وحدها من المعاينة (بلا كروت الصفحة) */
    var printBtn = document.getElementById("ocPvPrint");
    if (printBtn) printBtn.addEventListener("click", function () {
      document.body.classList.add("oc-print-paper");
      window.print();
    });
    window.addEventListener("afterprint", function () {
      document.body.classList.remove("oc-print-paper");
    });
    sayStatus("");                                    // الحالة تظهر عند أول استخدام فقط
  }

  /* ——— ٢-ب) وضع العرض/التعديل في تاب البحث: زر «✏️ تعديل» يفتح الرفع والحذف والتعديل ——— */
  var editToggle = document.getElementById("ocEditToggle");
  var editAgain = document.querySelectorAll("[data-ocedit]");
  var searchPane = document.getElementById("ocMTabSearch");
  var editHint = document.getElementById("ocEditHint");
  var HINT_VIEW = "وضع العرض: التقرير الرسمي والصور والفيديو — اضغط «تعديل» لإضافة صور وفيديو أو تعديل البيانات والتقرير";
  var HINT_EDIT = "وضع التعديل: ارفع صورًا وفيديو، عدّل بيانات التقرير، أو احذف ملفًا — وللإنهاء اضغط «إنهاء التعديل»";
  if (searchPane && editToggle) {
    var setEditing = function (on) {
      searchPane.classList.toggle("oc-editing", on);
      editToggle.textContent = on ? "✔ إنهاء التعديل" : "✏️ تعديل";
      editToggle.setAttribute("aria-pressed", on ? "true" : "false");
      if (editHint) editHint.textContent = on ? HINT_EDIT : HINT_VIEW;
      [].slice.call(editAgain).forEach(function (button) { button.hidden = on; });
      if (on) window.scrollTo({ top: 0, behavior: "smooth" });
    };
    var toggleEditing = function () { setEditing(!searchPane.classList.contains("oc-editing")); };
    editToggle.addEventListener("click", toggleEditing);
    [].slice.call(editAgain).forEach(function (button) {
      button.addEventListener("click", function () { setEditing(true); });
    });
  }

  /* ——— ٣) تابا الصفحة: «تسجيل مناسبة» ↔ «🔎 البحث عن مناسبة» + فلترة فورية للفهرس ——— */
  var mainTabs = document.getElementById("ocMainTabs");
  if (mainTabs) {
    var panes = { create: document.getElementById("ocMTabCreate"),
                  search: document.getElementById("ocMTabSearch") };
    function openMainTab(name) {
      [].slice.call(mainTabs.querySelectorAll("[data-ocmain]")).forEach(function (button) {
        var on = button.getAttribute("data-ocmain") === name;
        button.classList.toggle("on", on);
        button.setAttribute("aria-selected", on ? "true" : "false");
      });
      Object.keys(panes).forEach(function (key) {
        if (panes[key]) panes[key].hidden = key !== name;
      });
      try {                                    // التاب يفضل محفوظ في الرابط لو حد عمل تحديث
        var url = new URL(window.location.href);
        url.searchParams.set("tab", name);
        window.history.replaceState(null, "", url);
      } catch (err) { /* بلا تاريخ متصفح */ }
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    [].slice.call(mainTabs.querySelectorAll("[data-ocmain]")).forEach(function (button) {
      button.addEventListener("click", function () { openMainTab(button.getAttribute("data-ocmain")); });
    });
  }

  /* فلترة فورية لفهرس المناسبات وانت بتكتب في خانة البحث (الإرسال يوسّع البحث للوصف والتواريخ) */
  var searchInput = document.getElementById("ocSearchInput");
  var indexItems = [].slice.call(document.querySelectorAll("#ocTabIndex .oc-item"));
  var indexNone = document.getElementById("ocIndexNone");
  if (searchInput && indexItems.length) {
    searchInput.addEventListener("input", function () {
      var term = searchInput.value.trim().toLowerCase();
      var shown = 0;
      indexItems.forEach(function (item) {
        var hit = !term || (item.getAttribute("data-search") || "").indexOf(term) >= 0;
        item.hidden = !hit;
        if (hit) shown += 1;
      });
      if (indexNone) indexNone.hidden = shown > 0;
    });
  }

  /* ——— ٤) رفع الصور والفيديو: ملفًا ملفًا مع شريط تقدم ورسالة عربية في الآخر ——— */
  var form = document.getElementById("ocUploadForm");
  if (!form || !window.XMLHttpRequest || !window.FormData) return;
  var folder = (form.querySelector('[name="folder"]') || {}).value || "";
  var bar = document.getElementById("ocProgress");
  var fill = document.getElementById("ocProgressFill");
  var text = document.getElementById("ocProgressText");
  var AR2 = "٠١٢٣٤٥٦٧٨٩";
  function ar(n) { return String(n).replace(/\d/g, function (d) { return AR2[+d]; }); }
  function say(message) { if (text) text.textContent = message; }
  function progress(done, total, ratio) {
    var value = Math.round(((done + (ratio || 0)) / Math.max(total, 1)) * 100);
    if (fill) fill.style.width = value + "%";
  }

  form.addEventListener("submit", function (ev) {
    if (!folder) {
      ev.preventDefault();
      window.alert("اختر مناسبة من الفهرس الأول، وبعدها ارفع أي ملفات إضافية — أو استخدم نموذج «تسجيل مناسبة» بالأعلى واختر الصور والفيديو معه.");
      return;
    }
    var picked = [];
    ["photos", "videos"].forEach(function (bucket) {
      var input = form.querySelector('[name="' + bucket + '"]');
      [].slice.call(input ? input.files : []).forEach(function (file) {
        picked.push({ bucket: bucket, file: file });
      });
    });
    if (!picked.length) return;                    // نموذج عادي: رسالة السيرفر العربية
    var limit = parseInt(form.getAttribute("data-limit") || "30", 10);
    if (picked.length > limit) {
      ev.preventDefault();
      window.alert("الحد الأقصى " + ar(limit) + " ملفًا في الرفعة الواحدة — اخترت " + ar(picked.length) + "؛ قسّمها على دفعتين.");
      return;
    }
    ev.preventDefault();
    if (bar) bar.hidden = false;
    var url = form.getAttribute("data-json") + "?sid=" + encodeURIComponent(form.getAttribute("data-sid")) +
              "&folder=" + encodeURIComponent(folder);
    var total = picked.length;
    var done = 0;
    var added = { photo: 0, video: 0 };
    var problems = [];
    function next() {
      if (done >= total) return finish();
      var item = picked[done];
      say("جارٍ رفع " + ar(done + 1) + " من " + ar(total) + " — " + item.file.name);
      var xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) progress(done, total, e.loaded / e.total);
      };
      xhr.onload = function () {
        var payload = null;
        try { payload = JSON.parse(xhr.responseText); } catch (err) { payload = null; }
        if (!payload || !payload.ok) problems.push((payload && payload.message) || "تعذّر رفع «" + item.file.name + "»");
        else { added.photo += payload.photo || 0; added.video += payload.video || 0; }
        done += 1;
        progress(done, total, 0);
        next();
      };
      xhr.onerror = function () { problems.push("انقطع الاتصال الداخلي أثناء رفع «" + item.file.name + "»"); done += 1; next(); };
      var body = new FormData();
      body.append("folder", folder);
      body.append(item.bucket, item.file, item.file.name);
      xhr.send(body);
    }
    function finish() {
      if (problems.length) { say(problems[0]); window.alert(problems.join("\n")); return; }
      var message = "أُضيف " + ar(added.photo) + " صورة و" + ar(added.video) + " فيديو داخل فولدر المناسبة";
      say(message);
      var back = form.getAttribute("data-page") + "?folder=" + encodeURIComponent(folder) +
                 "&sid=" + encodeURIComponent(form.getAttribute("data-sid")) + "&ok=" + encodeURIComponent(message);
      window.location.assign(back);
    }
    next();
  });
})();
