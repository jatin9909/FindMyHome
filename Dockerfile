FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure Python can import from src/
ENV PYTHONPATH=/app/src

EXPOSE 8000

# Run the API with uvicorn. PORT can be overridden by the platform.
CMD ["sh", "-c", "uvicorn findmyhome.api.server:app --host 0.0.0.0 --port ${PORT}"]

