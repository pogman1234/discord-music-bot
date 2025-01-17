
FROM python:3.12-slim

WORKDIR /music_bot

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

COPY music_bot/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY music_bot/ ./

# Create a non-root user
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -m -s /bin/bash appuser

# Change ownership
RUN chown -R appuser:appgroup /music_bot

# Switch to the new user
USER appuser

# Expose port 8080
EXPOSE 8080

# Define environment variables
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]