# Python FastAPI Middleware Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./middleware/

EXPOSE 8000

ENV ENGINE_URL=http://engine:8080
ENV LOG_LEVEL=INFO

CMD ["uvicorn", "middleware.main:app", "--host", "0.0.0.0", "--port", "8000"]
