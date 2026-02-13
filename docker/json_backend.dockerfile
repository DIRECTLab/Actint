# Base image
FROM python:3.11


# Set working directory
WORKDIR /app

# Copy dependency file first (better caching)
COPY docker/requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY ./Groundtruth-Simulator/config-generator/server.py .

# Default command
CMD ["python", "server.py"]