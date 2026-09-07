from flask import Flask, request, jsonify
from pymongo import MongoClient
import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://mongodb:27017/')
MONGO_DB = os.environ.get('MONGO_DB', 'authdb')
JWT_SECRET = os.environ.get('JWT_SECRET', '').strip()
JWT_EXPIRES_MINUTES = int(os.environ.get('JWT_EXPIRES_MINUTES', '60'))

if not JWT_SECRET:
    raise RuntimeError('JWT_SECRET is required')

client = MongoClient(MONGO_URL)
db = client[MONGO_DB]
users = db['users']
users.create_index('username', unique=True)


def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': username,
        'iat': now,
        'exp': now + timedelta(minutes=JWT_EXPIRES_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify(error='Username and password are required'), 400
    if len(password) < 6:
        return jsonify(error='Password must be at least 6 characters'), 400
    if users.find_one({'username': username}):
        return jsonify(error='User already exists'), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    users.insert_one({'username': username, 'password': hashed})
    return jsonify(message='User created successfully'), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify(error='Username and password are required'), 400

    user = users.find_one({'username': username})
    if not user:
        return jsonify(error='Invalid username or password'), 401

    if not bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify(error='Invalid username or password'), 401

    token = create_token(username)
    return jsonify(token=token, username=username), 200


@app.route('/api/auth/healthz', methods=['GET'])
def healthz():
    return jsonify(status='ok'), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001) #nosec B104
