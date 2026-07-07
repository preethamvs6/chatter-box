FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn websockets

# Copy application files
COPY backendver1.py .
COPY landing.html .
COPY index.html .
COPY chat.html .

# Expose port 8000
EXPOSE 8000

# Start server
CMD ["uvicorn", "backendver1:app", "--host", "0.0.0.0", "--port", "8000"]
