FROM python:3.11-slim
RUN pip install --no-cache-dir --upgrade pip==26.2.0 wheel
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
CMD ["python", "app.py"]
