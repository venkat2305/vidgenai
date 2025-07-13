FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port the app will run on
EXPOSE 8000
EXPOSE 10000

# Command to run the application
CMD ["bash", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
