# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-build
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./
# Build the frontend using Vite
RUN npm run build

# Stage 2: Build the backend (Combined with final stage)
FROM python:3.9-slim

WORKDIR /  # Set working directory to root

# Copy the built frontend from the previous stage
COPY --from=frontend-build /frontend/build /frontend

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg


# Install Python dependencies
RUN pip install --no-cache-dir -r music_bot/requirements.txt

# Create a non-root user
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -m -s /bin/bash appuser

# Change ownership
RUN chown -R appuser:appgroup /frontend /music_bot

# Switch to the new user
USER appuser

# Expose port 8080
EXPOSE 8080

# Define environment variables
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Run the FastAPI app
CMD ["uvicorn", "music_bot.main:app", "--host", "0.0.0.0", "--port", "8080"]