FROM python:3.12-slim

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 7123

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7123", "--workers", "1"]
