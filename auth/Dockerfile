FROM python:3.11-slim
RUN python -m pip install --upgrade pip
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth_service.py .
CMD ["python", "auth_service.py"]
