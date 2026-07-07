# Use an official, lightweight Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's caching mechanism
COPY requirements.txt /app/

# Install the backend dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . /app/

# Expose the port Flask runs on locally
EXPOSE 5000

# Container-level health check, reusing the app's own /health-check route
# (which already verifies real database connectivity). No extra tools
# like curl needed — python is already in this image.
HEALTHCHECK --interval=5s --timeout=3s --retries=5 --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health-check', timeout=3)" || exit 1

# Run Flask without --debug: avoids spawning the Werkzeug reloader as a
# second child process, which removes a startup race that previously
# contributed to health checks hitting "Connection refused".
CMD ["flask", "--app", "app.main", "run", "--host=0.0.0.0", "--port=5000"]