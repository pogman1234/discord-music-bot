# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend
FROM python:3.9-slim AS backend-build
WORKDIR /app/musicbot
COPY musicbot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY musicbot/ ./

# Stage 3: Final stage
FROM python:3.9-slim
WORKDIR /app

# Copy the built frontend
COPY --from=frontend-build /app/frontend/dist /app/frontend/build

# Copy the backend
COPY --from=backend-build /app/musicbot /app/musicbot

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Create a non-root user and group with a specific UID and GID
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -m -s /bin/bash appuser

# Change ownership of the /app directory to the new user
RUN chown -R appuser:appgroup /app

# Switch to the new user
USER appuser

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable for the bot token (set this when running the container)
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Run the FastAPI app
CMD ["uvicorn", "musicbot.main:app", "--host", "0.0.0.0", "--port", "8080"]