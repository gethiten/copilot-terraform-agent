FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .
COPY templates/ templates/

# Create output directory
RUN mkdir -p generated_terraform

# Expose port
EXPOSE 5001

# Run application
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5001
ENV FLASK_DEBUG=False

CMD ["python", "app.py"]
