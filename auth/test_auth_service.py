"""
Unit tests for auth_service.py
 
Because the module:
  - connects to MongoDB at import time
  - raises RuntimeError if JWT_SECRET is unset
we set env vars and patch pymongo.MongoClient BEFORE importing the module,
then force a reload so it picks up the mocked client.
"""
import sys
import importlib
import pytest
import mongomock
 
 
@pytest.fixture
def client(monkeypatch):
    # Required env vars must exist before the module is imported
    monkeypatch.setenv('JWT_SECRET', 'test-secret-key')
    monkeypatch.setenv('MONGO_URL', 'mongodb://localhost:27017/')
    monkeypatch.setenv('MONGO_DB', 'testdb')
 
    # Replace the real MongoClient with an in-memory fake
    monkeypatch.setattr('pymongo.MongoClient', mongomock.MongoClient)
 
    # Force a fresh import so module-level code re-runs with the mock + env vars
    sys.modules.pop('auth_service', None)
    import auth_service
    importlib.reload(auth_service)
 
    auth_service.app.config['TESTING'] = True
    with auth_service.app.test_client() as test_client:
        yield test_client
 
    # clean slate between tests
    auth_service.users.delete_many({})
 
 
# ---------- healthz ----------
 
def test_healthz_returns_ok(client):
    resp = client.get('/api/auth/healthz')
    assert resp.status_code == 200
    assert resp.get_json() == {'status': 'ok'}
 
 
# ---------- signup ----------
 
def test_signup_success(client):
    resp = client.post('/api/auth/signup', json={
        'username': 'alice',
        'password': 'supersecret'
    })
    assert resp.status_code == 201
    assert resp.get_json()['message'] == 'User created successfully'
 
 
def test_signup_missing_username(client):
    resp = client.post('/api/auth/signup', json={'password': 'supersecret'})
    assert resp.status_code == 400
    assert 'required' in resp.get_json()['error']
 
 
def test_signup_missing_password(client):
    resp = client.post('/api/auth/signup', json={'username': 'alice'})
    assert resp.status_code == 400
    assert 'required' in resp.get_json()['error']
 
 
def test_signup_password_too_short(client):
    resp = client.post('/api/auth/signup', json={
        'username': 'alice',
        'password': '123'
    })
    assert resp.status_code == 400
    assert 'at least 6 characters' in resp.get_json()['error']
 
 
def test_signup_duplicate_user(client):
    payload = {'username': 'bob', 'password': 'supersecret'}
    first = client.post('/api/auth/signup', json=payload)
    second = client.post('/api/auth/signup', json=payload)
 
    assert first.status_code == 201
    assert second.status_code == 409
    assert 'already exists' in second.get_json()['error']
 
 
# ---------- login ----------
 
def test_login_success(client):
    client.post('/api/auth/signup', json={
        'username': 'carol',
        'password': 'supersecret'
    })
 
    resp = client.post('/api/auth/login', json={
        'username': 'carol',
        'password': 'supersecret'
    })
    body = resp.get_json()
 
    assert resp.status_code == 200
    assert body['username'] == 'carol'
    assert 'token' in body and len(body['token']) > 0
 
 
def test_login_wrong_password(client):
    client.post('/api/auth/signup', json={
        'username': 'dave',
        'password': 'supersecret'
    })
 
    resp = client.post('/api/auth/login', json={
        'username': 'dave',
        'password': 'wrongpassword'
    })
    assert resp.status_code == 401
    assert 'Invalid username or password' in resp.get_json()['error']
 
 
def test_login_nonexistent_user(client):
    resp = client.post('/api/auth/login', json={
        'username': 'ghost',
        'password': 'whatever'
    })
    assert resp.status_code == 401
    assert 'Invalid username or password' in resp.get_json()['error']
 
 
def test_login_missing_fields(client):
    resp = client.post('/api/auth/login', json={'username': 'dave'})
    assert resp.status_code == 400
    assert 'required' in resp.get_json()['error']