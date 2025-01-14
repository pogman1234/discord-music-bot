# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy the current directory contents into the container at /app
COPY . /app

# Create the music directory
RUN mkdir -p /app/music

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and group with a specific UID and GID
# Using a specific UID and GID helps with consistency and security, especially
# when mounting volumes from the host system.
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

# Run main.py when the container launches
CMD ["python", "music-bot/src/main.py"]