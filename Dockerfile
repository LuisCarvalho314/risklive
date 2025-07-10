FROM python:3.11

LABEL authors="lcarv"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl needed for wait script)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Flask backend and Streamlit dashboard ports
EXPOSE 5000
EXPOSE 8501

# Copy startup script and make executable
COPY start_all.sh /app/start_all.sh
RUN chmod +x /app/start_all.sh

# Run startup script to launch backend and dashboard sequentially
CMD ["/app/start_all.sh"]
