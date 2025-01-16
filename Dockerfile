# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the combined backend and bot application
FROM python:3.9-slim-buster

# Set environment variables for Cloud Run
ENV PORT=8080
ENV HOST=0.0.0.0

# Install system dependencies including FFMPEG
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built frontend
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

# Install gunicorn globally so the last CMD can see it
RUN pip install gunicorn

# Copy application code and requirements
COPY app/ /app/app/
RUN mkdir -p /app/app/music && chmod 777 /app/app/music
COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port
EXPOSE 8080

# Start the application using Gunicorn and run the Discord bot
CMD exec gunicorn --bind :$PORT --workers 1 --threads 6 --timeout 0 --worker-class uvicorn.workers.UvicornWorker app.main:app --preload