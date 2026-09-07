from flask import Flask, request, jsonify, Response, stream_with_context
from functools import wraps
from urllib.parse import quote
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
import jwt
import mimetypes
import os
from datetime import datetime, timezone

app = Flask(__name__)

STORAGE_ACCOUNT_NAME = os.environ.get('STORAGE_ACCOUNT_NAME', '').strip()
CONTAINER_NAME = os.environ.get('CONTAINER_NAME', '').strip()
JWT_SECRET = os.environ.get('JWT_SECRET', '').strip()
MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', '100'))
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

if not STORAGE_ACCOUNT_NAME or not CONTAINER_NAME or not JWT_SECRET:
    raise RuntimeError('STORAGE_ACCOUNT_NAME, CONTAINER_NAME and JWT_SECRET are required')

account_url = f'https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net'
credential = DefaultAzureCredential()
blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)


def guess_content_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or 'application/octet-stream'


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify(error='Missing Authorization header'), 401
        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            request.user = payload.get('sub')
        except jwt.ExpiredSignatureError:
            return jsonify(error='Token expired'), 401
        except jwt.InvalidTokenError:
            return jsonify(error='Invalid token'), 401
        return fn(*args, **kwargs)
    return wrapper


@app.route('/api/files', methods=['GET'])
@jwt_required
def list_files():
    items = []
    for blob in container_client.list_blobs():
        items.append({
            'name': blob.name,
            'size': getattr(blob, 'size', None),
            'last_modified': blob.last_modified.isoformat() if getattr(blob, 'last_modified', None) else None,
        })
    items.sort(key=lambda x: (x['last_modified'] or ''), reverse=True)
    return jsonify(items)


@app.route('/api/upload', methods=['POST'])
@jwt_required
def upload_file():
    if 'file' not in request.files:
        return jsonify(error='No file part in request'), 400
    incoming = request.files['file']
    if incoming.filename == '':
        return jsonify(error='No file selected'), 400

    blob_name = incoming.filename
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        incoming.stream,
        overwrite=True,
        content_settings=ContentSettings(content_type=incoming.mimetype or guess_content_type(blob_name))
    )
    return jsonify(message='Upload successful', file_name=blob_name, uploaded_by=request.user)


@app.route('/api/download/<path:blob_name>', methods=['GET'])
@jwt_required
def download_file(blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    props = blob_client.get_blob_properties()
    downloader = blob_client.download_blob()
    headers = {
        'Content-Type': props.content_settings.content_type or guess_content_type(blob_name),
        'Content-Length': str(props.size),
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(os.path.basename(blob_name))}"
    }
    def generate():
        for chunk in downloader.chunks():
            yield chunk
    return Response(stream_with_context(generate()), headers=headers)


@app.route('/api/healthz', methods=['GET'])
def healthz():
    return jsonify(status='ok', time=datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000) #nosec B104
