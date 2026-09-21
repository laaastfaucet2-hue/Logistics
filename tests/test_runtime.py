import io
import json
import re
import threading
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from werkzeug.serving import make_server
from data_access import storage, dataguard, database
from services.data_import import import_database
from desktop.native import NativeApi


@pytest.mark.parametrize('path', ['/dashboard','/rations/tamween','/rations/contractor?tab=dist','/letterhead/',
    '/recruits/','/recruits/?tab=journal','/recruits/?tab=present','/recruits/?tab=leaves',
    '/recruits/?tab=absent','/recruits/?tab=other','/recruits/?tab=stats','/backups/'])
def test_every_page(client,path):
    response=client.get(path)
    assert response.status_code==200
    assert 'None' not in response.text
    assert 'fonts.googleapis' not in response.text
    assert 'cdn.jsdelivr' not in response.text


def test_http_real_requests_and_arabic_download_headers(app):
    server=make_server('127.0.0.1',0,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        assert json.load(urllib.request.urlopen(base+'/health'))['status']=='ready'
        token=database.create_session(1)
        response=urllib.request.urlopen(base+f'/rations/tamween/download-excel?year=2031&month=9&sid={token}')
        assert response.status==200 and "filename*=UTF-8" in response.headers['Content-Disposition']
        with zipfile.ZipFile(io.BytesIO(response.read())) as z:
            assert not z.testzip()
    finally:
        server.shutdown();thread.join(5);server.server_close()


def test_links_have_one_valid_query_separator(client):
    for path in ['/recruits/','/recruits/?tab=journal','/rations/tamween','/rations/contractor?tab=dist','/letterhead/']:
        response=client.get(path)
        for href in re.findall(r'(?:href|action)="([^"]+)"',response.text):
            assert href.count('?') <= 1,href


def test_invalid_period_rejected_before_writing(client):
    before=set(storage.DATA_DIR.rglob('*.db'))
    assert client.get('/recruits/?year=2099&month=13').status_code==400
    assert set(storage.DATA_DIR.rglob('*.db'))==before


def test_backup_and_first_install_import_preserve_source(app,tmp_path):
    source=storage.DATA_DIR
    original=database.get_setting('session_secret')
    result=dataguard.create_backup('manual')
    assert dataguard.valid_name(result['name'])
    with zipfile.ZipFile(result['path']) as z:
        assert not z.testzip()
        assert 'system.db' in z.namelist()
        assert not any('-wal' in name for name in z.namelist())
    dest=tmp_path/'installed'/'database'
    count=import_database(source,dest)
    assert count>0 and (source/'system.db').is_file()
    conn=database.get_conn(dest/'system.db',readonly=True)
    assert conn.execute("SELECT value FROM app_settings WHERE key='session_secret'").fetchone()[0]==original
    conn.close()
    with pytest.raises(ValueError):
        import_database(source,dest)


def test_zip_traversal_rejected(app):
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:
        for p in ['../bad','C:/bad','..\\bad','backups/x.zip','2031/ok.txt']:
            z.writestr(p,'test')
    with zipfile.ZipFile(f) as z:
        assert dataguard._safe_members(z)==['2031/ok.txt']


def test_bridge_rejects_untrusted_page_and_arbitrary_commands(tmp_path):
    class Window:
        def get_current_url(self):return 'https://untrusted.example'
    api=NativeApi(Window(),tmp_path,lambda _:None)
    api._origin='http://127.0.0.1:1234'
    with pytest.raises(PermissionError):api.window_action('data_folder')
    assert not api.begin_new()


def test_rule_code_line_limit_and_no_db_in_installer():
    root=Path(__file__).resolve().parents[1]
    for folder in ['core','data_access','services','documents','desktop','routes','templates','static/css','static/js','scripts']:
        for path in (root/folder).rglob('*'):
            if path.suffix in ('.py','.html','.css','.js','.ps1'):
                assert len(path.read_text(encoding='utf-8').splitlines()) <= 1000,path
    spec=(root/'scripts/installer/Logistics.spec').read_text()
    assert "root / 'database'" not in spec
    assert 'PrivilegesRequired=lowest' in (root/'scripts/installer/Logistics.iss').read_text()


def test_notifications_do_not_recreate_an_absent_year(app):
    from core import egtime
    from services import notifications
    year = egtime.today().year
    if year == 2031:
        return
    storage.delete_year(year)
    assert notifications.build_groups(1) == []
    assert year not in storage.list_years()
