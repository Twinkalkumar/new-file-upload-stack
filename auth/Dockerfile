FROM python:3.11-slim
RUN pip install --upgrade pip setuptools wheel
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth_service.py .
CMD ["python", "auth_service.py"]
