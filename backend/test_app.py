"""
Unit tests for app.py (file upload/download backend)
 
The module:
  - raises RuntimeError if STORAGE_ACCOUNT_NAME / CONTAINER_NAME / JWT_SECRET are unset
  - constructs real DefaultAzureCredential() and BlobServiceClient(...) at import time
 
So we patch the Azure SDK classes BEFORE importing the module, set required
env vars, then force a reload. After that, `app_module.container_client`
is a MagicMock we control per test.
"""
import sys
import io
import importlib
from unittest.mock import MagicMock
 
import pytest
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
 
TEST_SECRET = 'test-secret-key'
 
 
def make_token(username='alice', expired=False):
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=30)
    return pyjwt.encode({'sub': username, 'exp': exp}, TEST_SECRET, algorithm='HS256')
 
 
@pytest.fixture
def app_module(monkeypatch):
    monkeypatch.setenv('STORAGE_ACCOUNT_NAME', 'teststorage')
    monkeypatch.setenv('CONTAINER_NAME', 'testcontainer')
    monkeypatch.setenv('JWT_SECRET', TEST_SECRET)
 
    import azure.identity
    import azure.storage.blob
 
    # Prevent any real Azure network/auth calls at import time
    monkeypatch.setattr(azure.identity, 'DefaultAzureCredential', lambda *a, **kw: MagicMock())
    monkeypatch.setattr(azure.storage.blob, 'BlobServiceClient', MagicMock())
 
    sys.modules.pop('app', None)
    import app as app_module
    importlib.reload(app_module)
 
    app_module.app.config['TESTING'] = True
    yield app_module
 
 
@pytest.fixture
def client(app_module):
    with app_module.app.test_client() as test_client:
        yield test_client
 
 
# ---------- healthz (no auth required) ----------
 
def test_healthz(client):
    resp = client.get('/api/healthz')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'
 
 
# ---------- auth guard ----------
 
def test_list_files_requires_token(client):
    resp = client.get('/api/files')
    assert resp.status_code == 401
    assert 'Missing Authorization header' in resp.get_json()['error']
 
 
def test_invalid_token_rejected(client):
    resp = client.get('/api/files', headers={'Authorization': 'Bearer not-a-real-token'})
    assert resp.status_code == 401
    assert 'Invalid token' in resp.get_json()['error']
 
 
def test_expired_token_rejected(client):
    token = make_token(expired=True)
    resp = client.get('/api/files', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 401
    assert 'Token expired' in resp.get_json()['error']
 
 
# ---------- list files ----------
 
def test_list_files_success(client, app_module):
    blob_a = MagicMock(name='blob_a')
    blob_a.name = 'a.txt'
    blob_a.size = 10
    blob_a.last_modified = datetime(2026, 1, 1, tzinfo=timezone.utc)
 
    blob_b = MagicMock(name='blob_b')
    blob_b.name = 'b.txt'
    blob_b.size = 20
    blob_b.last_modified = datetime(2026, 2, 1, tzinfo=timezone.utc)
 
    app_module.container_client.list_blobs.return_value = [blob_a, blob_b]
 
    token = make_token()
    resp = client.get('/api/files', headers={'Authorization': f'Bearer {token}'})
 
    assert resp.status_code == 200
    names = [item['name'] for item in resp.get_json()]
    assert names == ['b.txt', 'a.txt']  # sorted by last_modified, newest first
 
 
# ---------- upload ----------
 
def test_upload_requires_token(client):
    resp = client.post('/api/upload', data={})
    assert resp.status_code == 401
 
 
def test_upload_no_file_part(client):
    token = make_token()
    resp = client.post('/api/upload', headers={'Authorization': f'Bearer {token}'}, data={})
    assert resp.status_code == 400
    assert 'No file part' in resp.get_json()['error']
 
 
def test_upload_empty_filename(client):
    token = make_token()
    data = {'file': (io.BytesIO(b''), '')}
    resp = client.post(
        '/api/upload',
        headers={'Authorization': f'Bearer {token}'},
        data=data,
        content_type='multipart/form-data'
    )
    assert resp.status_code == 400
    assert 'No file selected' in resp.get_json()['error']
 
 
def test_upload_success(client, app_module):
    mock_blob_client = MagicMock()
    app_module.container_client.get_blob_client.return_value = mock_blob_client
 
    token = make_token(username='carol')
    data = {'file': (io.BytesIO(b'hello world'), 'notes.txt')}
    resp = client.post(
        '/api/upload',
        headers={'Authorization': f'Bearer {token}'},
        data=data,
        content_type='multipart/form-data'
    )
 
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['message'] == 'Upload successful'
    assert body['file_name'] == 'notes.txt'
    assert body['uploaded_by'] == 'carol'
    mock_blob_client.upload_blob.assert_called_once()
 
 
# ---------- download ----------
 
def test_download_requires_token(client):
    resp = client.get('/api/download/notes.txt')
    assert resp.status_code == 401
 
 
def test_download_success(client, app_module):
    mock_blob_client = MagicMock()
    mock_props = MagicMock()
    mock_props.content_settings.content_type = 'text/plain'
    mock_props.size = 11
    mock_blob_client.get_blob_properties.return_value = mock_props
 
    mock_downloader = MagicMock()
    mock_downloader.chunks.return_value = [b'hello ', b'world']
    mock_blob_client.download_blob.return_value = mock_downloader
 
    app_module.container_client.get_blob_client.return_value = mock_blob_client
 
    token = make_token()
    resp = client.get('/api/download/notes.txt', headers={'Authorization': f'Bearer {token}'})
 
    assert resp.status_code == 200
    assert resp.data == b'hello world'
    assert resp.headers['Content-Type'] == 'text/plain'
    assert "notes.txt" in resp.headers['Content-Disposition']
 
 
# ---------- utility ----------
 
def test_guess_content_type_known_extension(app_module):
    assert app_module.guess_content_type('report.pdf') == 'application/pdf'
 
 
def test_guess_content_type_unknown_extension(app_module):
    assert app_module.guess_content_type('mystery.unknownext') == 'application/octet-stream'