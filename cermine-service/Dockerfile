# Stage 1: Download CERMINE fat‑jar
FROM eclipse-temurin:17-jre AS cermine
WORKDIR /cermine
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl unzip \
 && rm -rf /var/lib/apt/lists/*
RUN curl -L -o /cermine.jar \
    https://storage.googleapis.com/cermine-assets/cermine.jar

FROM python:3.11-slim AS runner
WORKDIR /app
# Install Python runtime and pip
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless python3-pip \
 && rm -rf /var/lib/apt/lists/*
# Copy CERMINE jar from the first stage
COPY --from=cermine /cermine.jar /app/cermine.jar
ENV CERMINE_JAR_PATH=/app/cermine.jar
# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
# Copy application code
COPY . .

# Expose HTTP port
EXPOSE 8080

# Launch FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]