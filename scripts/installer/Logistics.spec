# Windows build only. Never collect the local database or runtime folders.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).parents[1]
web_data, web_bins, web_hidden = collect_all('webview')
datas = [(str(root / 'templates'), 'templates'), (str(root / 'static'), 'static'),
         (str(root / 'desktop' / 'welcome.html'), 'desktop')]
datas += web_data + collect_data_files('tzdata')
a = Analysis([str(root / 'desktop' / 'entry.py')], pathex=[str(root)],
             binaries=web_bins, datas=datas, hiddenimports=web_hidden,
             excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Logistics', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'static' / 'img' / 'app.ico'),
          version=str(root / 'scripts' / 'installer' / 'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Logistics')
