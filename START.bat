@echo off
rem ============================================================
rem  منظومة مخازن التعيينات — زر التشغيل الذكي
rem  يبحث عن بايثون (حتى لو مش متسطب) + المكتبات، ويثبّت الناقص تلقائيًا،
rem  ثم يشغّل البرنامج ويفتح المتصفح — بدون أي خطوة يدوية.
rem ============================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul
title منظومة مخازن التعيينات
cd /d "%~dp0"

echo.
echo  ========================================================
echo    منظومة مخازن التعيينات — تشغيل تلقائي
echo  ========================================================
echo.

rem ---------- 1) البحث عن بايثون في كل الأماكن المعروفة ----------
set "PY="
where py >nul 2>nul && (py -3 --version >nul 2>nul && set "PY=py -3")
if not defined PY (where python >nul 2>nul && (python --version >nul 2>nul && set "PY=python"))
if not defined PY (where python3 >nul 2>nul && (python3 --version >nul 2>nul && set "PY=python3"))
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)
if not defined PY (
  for /d %%D in ("%ProgramFiles%\Python3*" "C:\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)

rem ---------- 2) مش موجود؟ نحاول التثبيت الصامت عبر winget ----------
if not defined PY (
  echo  [1/4] بايثون غير موجود — جار تثبيته تلقائيًا ^(winget^)...
  where winget >nul 2>nul && (
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements >nul 2>nul
  )
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)

rem ---------- 3) الحل الأخير: نسخة بايثون محمولة داخل مجلد البرنامج ----------
if not defined PY (
  echo  [1/4] تعذر winget — جار تنزيل نسخة بايثون محمولة داخل البرنامج...
  if not exist runtime mkdir runtime
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip' -OutFile 'runtime\py.zip'" || goto :nopy
  powershell -NoProfile -Command "Expand-Archive -Force 'runtime\py.zip' 'runtime\py'" || goto :nopy
  del /q runtime\py.zip >nul 2>nul
  rem تفعيل import site في النسخة المحمولة (ضروري لـ pip)
  for %%P in (runtime\py\python*._pth) do (
    powershell -NoProfile -Command "(Get-Content '%%P') -replace '#import site','import site' | Set-Content '%%P'"
  )
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'runtime\get-pip.py'" || goto :nopy
  runtime\py\python.exe runtime\get-pip.py --quiet >nul 2>nul
  set "PY=runtime\py\python.exe"
)
echo  [✔] بايثون جاهز: %PY%

rem ---------- 4) تثبيت/تحديث المكتبات تلقائيًا ----------
echo  [2/4] جار التأكد من مكتبات البرنامج...
%PY% -m pip install --quiet --disable-pip-version-check --no-warn-script-location -r requirements.txt
if errorlevel 1 (
  echo  [محاولة أخرى] تثبيت المكتبات لمستخدم الجهاز فقط...
  %PY% -m pip install --user --quiet --disable-pip-version-check --no-warn-script-location -r requirements.txt
)
echo  [✔] المكتبات جاهزة.

rem ---------- 5) التشغيل + فتح المتصفح ----------
echo  [3/4] جار تشغيل البرنامج...
start "" "http://127.0.0.1:5000"
echo.
echo  ========================================================
echo    البرنامج يعمل الآن — المتصفح انفتح على الشاشة الرئيسية
echo    لإيقاف البرنامج: أغلق هذه النافذة فقط.
echo  ========================================================
echo.
%PY% app.py

echo.
echo  تم إيقاف البرنامج.
pause
exit /b 0

:nopy
echo.
echo  [خطأ] تعذر الحصول على بايثون تلقائيًا.
echo  السبب غالبًا: لا يوجد اتصال بالإنترنت في أول تشغيل.
echo  صِل الجهاز بالإنترنت مرة واحدة فقط وشغّل هذا الملف من جديد.
echo.
pause
exit /b 1
