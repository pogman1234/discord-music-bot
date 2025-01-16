# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend (Combine with Stage 3 for efficiency)
FROM python:3.9-slim AS build # Removed unneccessary second build stage

WORKDIR /app

# Copy the built frontend
COPY --from=frontend-build /app/frontend/build /app/frontend/build

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy requirements.txt (for backend and main.py)
COPY music-bot/requirements.txt .
COPY requirements.txt . # Assuming you have one for main.py at project root

# Install Python dependencies
RUN pip install --no-cache-dir -r music-bot/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code (music-bot directory)
COPY music-bot/ /app/music-bot/

# Copy main.py
COPY main.py /app/

# Create a non-root user (moved up for efficiency)
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -m -s /bin/bash appuser

# Change ownership (moved up for efficiency)
RUN chown -R appuser:appgroup /app

# Switch to the new user
USER appuser

# Expose port 8080
EXPOSE 8080

# Define environment variables
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]