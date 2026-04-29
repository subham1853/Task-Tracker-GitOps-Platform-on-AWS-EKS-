# Start from an official slim Python image (small, fast, secure)
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (Docker caching optimization)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .

# Tell Docker this container listens on port 8000
EXPOSE 8000

# The command Docker runs when the container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]