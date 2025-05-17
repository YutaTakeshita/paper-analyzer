# Stage 1: Download CERMINE fat‑jar
FROM eclipse-temurin:17-jre AS cermine
WORKDIR /cermine
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl unzip \
 && rm -rf /var/lib/apt/lists/*
RUN curl -L -o /cermine.jar \
    https://storage.googleapis.com/cermine-assets/cermine.jar

# Stage 2: Build Python HTTP service
FROM python:3.11-slim
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir requests

# Copy application code and CERMINE jar
COPY . .

# Expose HTTP port
EXPOSE 8080

# Launch FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]