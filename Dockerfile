# Base stage
FROM python:3.12-slim as base
WORKDIR /music_bot
RUN apt-get update && apt-get install -y ffmpeg
COPY music_bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development
RUN pip install debugpy pytest
ENV PYTHONPATH=/music_bot
ENV ENVIRONMENT=development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

# Production stage
FROM base as production
COPY music_bot/ ./
ARG UID=1001
ARG GID=1001
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g appgroup -m -s /bin/bash appuser
RUN chown -R appuser:appgroup /music_bot
USER appuser
EXPOSE 8080
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]