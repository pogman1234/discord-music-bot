# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable for the bot token (set this when running the container)
ENV DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}

# Run main.py when the container launches
CMD ["python", "music-bot/src/main.py"]