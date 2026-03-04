#!/bin/bash

# Start API in background
echo "Starting API..."
python apps/api.py &

# Wait until backend health endpoint is ready
echo "Waiting for API to be ready..."
until curl -s http://localhost:5000/health; do
  echo "API not ready, waiting 2 seconds..."
  sleep 2
done

# Start Streamlit dashboard (foreground)
echo "Starting dashboard..."
streamlit run apps/dashboard.py --server.port=8501 --server.address=0.0.0.0
